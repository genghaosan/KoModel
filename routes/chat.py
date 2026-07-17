"""对话路由 — 支持流式输出和多轮对话"""

import json
import uuid
from flask import Blueprint, request, jsonify, Response, session
from services.ollama_service import ollama_service
from services.lancedb_service import lancedb_service

chat_bp = Blueprint("chat", __name__)

# 简易对话历史存储（生产环境应使用 Redis/DB）
# ponytail: in-memory dict, 重启即丢失，实验项目够用
conversations: dict[str, list[dict]] = {}


@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    """
    RAG 对话接口（非流式）
    请求体: {"question": "你的问题", "conversation_id": "可选"}
    """
    data = request.get_json()
    question = data.get("question", "")
    conv_id = data.get("conversation_id", "")

    if not question:
        return jsonify({"error": "请输入问题"}), 400

    # 1. 检索相关知识
    context_docs = lancedb_service.search(question, top_k=3)
    context_text = "\n".join([doc["text"] for doc in context_docs])

    # 2. 获取对话历史
    history = []
    if conv_id and conv_id in conversations:
        history = conversations[conv_id]

    # 3. 调用大模型
    answer = ollama_service.chat(question, context=context_text, history=history)

    # 4. 保存对话历史
    if not conv_id:
        conv_id = str(uuid.uuid4())
    if conv_id not in conversations:
        conversations[conv_id] = []
    conversations[conv_id].append({"role": "user", "content": question})
    conversations[conv_id].append({"role": "assistant", "content": answer})

    return jsonify({
        "conversation_id": conv_id,
        "question": question,
        "answer": answer,
        "references": context_docs
    })


@chat_bp.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """
    RAG 对话接口（流式输出 — SSE）
    请求体: {"question": "你的问题", "conversation_id": "可选"}
    返回: text/event-stream
    """
    data = request.get_json()
    question = data.get("question", "")
    conv_id = data.get("conversation_id", "")

    if not question:
        return jsonify({"error": "请输入问题"}), 400

    # 1. 检索相关知识
    context_docs = lancedb_service.search(question, top_k=3)
    context_text = "\n".join([doc["text"] for doc in context_docs])

    # 2. 获取对话历史
    history = []
    if conv_id and conv_id in conversations:
        history = conversations[conv_id]

    # 3. 生成新 conversation_id
    if not conv_id:
        conv_id = str(uuid.uuid4())

    def generate():
        # 先发送 conversation_id 和 references
        meta = {
            "conversation_id": conv_id,
            "references": context_docs
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        # 4. 流式调用大模型
        full_answer = ""
        for chunk in ollama_service.chat_stream(question, context=context_text, history=history):
            if chunk:
                full_answer += chunk
                yield f"data: {json.dumps({'token': chunk}, ensure_ascii=False)}\n\n"

        # 5. 发送结束标记
        yield f"data: {json.dumps({'done': True})}\n\n"

        # 6. 保存对话历史
        if conv_id not in conversations:
            conversations[conv_id] = []
        conversations[conv_id].append({"role": "user", "content": question})
        conversations[conv_id].append({"role": "assistant", "content": full_answer})

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@chat_bp.route("/api/chat/history", methods=["POST"])
def get_history():
    """获取指定对话的历史记录"""
    data = request.get_json()
    conv_id = data.get("conversation_id", "")
    if conv_id in conversations:
        return jsonify({"history": conversations[conv_id]})
    return jsonify({"history": []})
