from flask import Blueprint, request, jsonify
from services.lancedb_service import lancedb_service

knowledge_bp = Blueprint("knowledge", __name__)

@knowledge_bp.route("/api/knowledge/add", methods=["POST"])
def add_knowledge():
    """
    添加知识文档
    请求体: {"text": "文档内容", "source": "来源（可选）"}
    """
    data = request.get_json()
    text = data.get("text", "")
    source = data.get("source", "api_upload")
    
    if not text:
        return jsonify({"error": "文档内容不能为空"}), 400
    
    # 支持按段落分割存入（可选优化）
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    
    success_count = 0
    for para in paragraphs:
        if lancedb_service.add_document(para, source):
            success_count += 1
    
    return jsonify({
        "message": f"成功添加 {success_count}/{len(paragraphs)} 条文档",
        "total": len(paragraphs)
    })

@knowledge_bp.route("/api/knowledge/search", methods=["POST"])
def search_knowledge():
    """搜索知识库"""
    data = request.get_json()
    query = data.get("query", "")
    top_k = data.get("top_k", 3)
    
    results = lancedb_service.search(query, top_k=top_k)
    return jsonify({"results": results})