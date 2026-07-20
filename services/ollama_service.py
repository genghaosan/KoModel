"""Ollama 模型调用封装"""

import ollama
from config import Config

SYSTEM_PROMPT_TEMPLATE = """你是一位《中华人民共和国劳动法》知识库问答助手。请严格遵守以下规则：

1. **只回答劳动法相关问题**：如果用户问题与《中华人民共和国劳动法》无关（如刑法、民法、交通法规等），请明确回答："本系统仅提供《中华人民共和国劳动法》相关咨询服务，无法回答其他法律领域的问题。"
2. **必须基于参考资料**：只根据提供的"参考资料"回答。如果参考资料中没有相关内容，请回答："根据现有知识库资料，无法找到该问题的答案。"
3. **禁止编造**：不要编造法条内容，不要使用预训练知识补充，不要在中文回答中混入无意义的英文单词或符号。
4. **引用规范**：回答时引用具体条款号，格式如"根据劳动法第X条规定..."。
5. **回答风格**：使用中文回答，条理清晰，简洁准确。只复述参考资料中的原文内容。"""


class OllamaService:
    """Ollama 模型调用封装"""

    @staticmethod
    def chat(prompt: str, context: str = "", history: list = None) -> str:
        if history is None:
            history = []

        messages = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE}]

        if context:
            messages.append({
                "role": "user",
                "content": f"以下是知识库中检索到的参考资料：\n\n{context}\n\n请基于以上资料回答我的问题。如果问题与劳动法无关，请拒绝回答。"
            })
            messages.append({
                "role": "assistant",
                "content": "我已阅读参考资料。我将只根据劳动法相关内容回答您的问题，如果问题超出劳动法范围，我会明确告知。"
            })
        else:
            messages.append({
                "role": "user",
                "content": f"用户问题：{prompt}\n\n注意：如果没有找到相关的参考资料，请回答'根据现有知识库资料，无法找到该问题的答案。'"
            })

        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        response = ollama.chat(
            model=Config.CHAT_MODEL,
            messages=messages
        )
        return response["message"]["content"]

    @staticmethod
    def chat_stream(prompt: str, context: str = "", history: list = None):
        if history is None:
            history = []

        messages = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE}]

        if context:
            messages.append({
                "role": "user",
                "content": f"以下是知识库中检索到的参考资料：\n\n{context}\n\n请基于以上资料回答我的问题。如果问题与劳动法无关，请拒绝回答。"
            })
            messages.append({
                "role": "assistant",
                "content": "我已阅读参考资料。我将只根据劳动法相关内容回答您的问题，如果问题超出劳动法范围，我会明确告知。"
            })
        else:
            messages.append({
                "role": "user",
                "content": f"用户问题：{prompt}\n\n注意：如果没有找到相关的参考资料，请回答'根据现有知识库资料，无法找到该问题的答案。'"
            })

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
    def get_embedding(text: str) -> list:
        """获取文本的向量嵌入"""
        response = ollama.embed(
            model=Config.EMBED_MODEL,
            input=text
        )
        return response["embeddings"][0]


# 实例化
ollama_service = OllamaService()