先下载uv
`pip install uv`

创建虚拟环境
`uv venv`

启动虚拟环境
```cmd
.venv\Scripts\activate
```
下载依赖
`uv sync`

安装模型

`ollama pull deepseek-r1:7b`
`ollama pull nomic-embed-text`
> 模型文件夹models记得挪到KoModel目录下

导入知识库
`python import_docs.py`

启动项目
`uv run python app.py`

