import os


class Config:
    # Ollama 配置
    OLLAMA_HOST = "http://localhost:11434"
    CHAT_MODEL = "deepseek-r1:7b"
    EMBED_MODEL = "nomic-embed-text"

    # LanceDB 配置
    LANCEDB_PATH = os.path.join(os.path.dirname(__file__), "data", "lancedb_data")
    TABLE_NAME = "knowledge_base"

    # Flask 配置
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    DEBUG = True