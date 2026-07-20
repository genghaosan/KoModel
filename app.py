from flask import Flask, render_template

try:
    from flask_cors import CORS

    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("⚠️ flask-cors 未安装，CORS 功能已禁用")

from config import Config
from routes.chat import chat_bp
from routes.knowledge import knowledge_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 启用 CORS（如果可用）
    if CORS_AVAILABLE:
        CORS(app)

    # 注册蓝图
    app.register_blueprint(chat_bp)
    app.register_blueprint(knowledge_bp)

    # 首页
    @app.route("/")
    def index():
        return render_template("index.html") if app.jinja_loader else \
            "<h1>🚀 Flask + Ollama + LanceDB RAG API 已启动！</h1>"

    # 健康检查
    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "RAG API"}

    # 知识库统计
    @app.route("/api/stats")
    def stats():
        from services.lancedb_service import lancedb_service
        return lancedb_service.get_stats()

    return app


if __name__ == "__main__":
    app = create_app()
    print("=" * 50)
    print("🤖 RAG 服务启动中...")
    print(f"   生成模型: {Config.CHAT_MODEL}")
    print(f"   嵌入模型: {Config.EMBED_MODEL}")
    print(f"   向量库:   {Config.LANCEDB_PATH}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)