"""Ollama 模型调用封装"""

import ollama
from config import Config

# 系统提示词模板 — 角色设定 + 回答约束
SYSTEM_PROMPT_TEMPLATE = """你是一个智能知识助手，严格遵循以下规则：

1. 必须基于提供的"上下文信息"来回答用户问题。
2. 如果上下文信息不足以回答问题，请明确说"根据现有知识库，我无法回答这个问题"。
3. 不要编造不存在的信息，不要使用你自己的预训练知识补充（除非上下文中有）。
4. 回答时引用相关上下文来源（如果有）。
5. 使用中文回答，保持简洁准确。"""


class OllamaService:
    """Ollama 模型调用封装"""

    @staticmethod
    def chat(prompt: str, context: str = "", history: list[dict] | None = None) -> str:
        """
        与模型对话（非流式）
        history: [{"role": "user"/"assistant", "content": "..."}]
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE}]

        # ponytail: simple approach — pass context as a user message before history
        if context:
            messages.append({
                "role": "user",
                "content": f"以下是知识库中检索到的参考资料（请严格基于此回答）：\n{context}"
            })

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})

        response = ollama.chat(
            model=Config.CHAT_MODEL,
            messages=messages
        )
        return response["message"]["content"]

    @staticmethod
    def chat_stream(prompt: str, context: str = "", history: list[dict] | None = None):
        """
        与模型对话（流式），返回生成器，逐块产出文本
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE}]

        if context:
            messages.append({
                "role": "user",
                "content": f"以下是知识库中检索到的参考资料（请严格基于此回答）：\n{context}"
            })

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})

        stream = ollama.chat(
            model=Config.CHAT_MODEL,
            messages=messages,
            stream=True
        )
        for chunk in stream:
            if "content" in chunk["message"]:
                yield chunk["message"]["content"]

    @staticmethod
    def get_embedding(text: str) -> list[float]:
        """获取文本的向量嵌入"""
        response = ollama.embed(
            model=Config.EMBED_MODEL,
            input=text
        )
        return response["embeddings"][0]


# 实例化
ollama_service = OllamaService()
