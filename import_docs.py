"""
知识库导入脚本
支持多种文档格式: .txt .md .docx .pdf .xlsx .pptx 等
依赖: 全局 markitdown 命令 (https://github.com/microsoft/markitdown)
用法: python import_docs.py
"""
import os
import subprocess
from services.lancedb_service import lancedb_service

DOCS_DIR = "./docs"
SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx", ".pdf", ".xlsx", ".pptx", ".html", ".htm", ".csv"}


def convert_to_text(filepath: str) -> str:
    """将各种格式的文件转换为纯文本"""
    ext = os.path.splitext(filepath)[1].lower()

    # 纯文本类直接读取
    if ext in {".txt", ".md", ".csv"}:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    # 使用 markitdown CLI 转换办公文档
    try:
        result = subprocess.run(
            ["markitdown", filepath],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        # ponytail: fallback to stderr if stdout is empty
        if result.stderr.strip():
            print(f"  ⚠️ markitdown 警告 [{os.path.basename(filepath)}]: {result.stderr.strip()}")
            return result.stderr
    except FileNotFoundError:
        print("  ❌ 未找到 markitdown 命令，请确保已安装: pip install markitdown")
        raise
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ 转换超时 [{os.path.basename(filepath)}]，跳过")
        return ""
    except Exception as e:
        print(f"  ⚠️ 转换失败 [{os.path.basename(filepath)}]: {e}")
        return ""

    return ""


def chunk_text(text: str, source: str, max_chars: int = 500) -> list[dict]:
    """
    将文本分段为知识单元
    策略: 按空行/段落分割，每段作为一个独立知识单元
    """
    # 按两个以上换行分割段落
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    for para in paragraphs:
        # 过滤太短或无意义的段落
        if len(para) < 10:
            continue
        # 如果段落太长，按句子或固定长度切分
        if len(para) > max_chars:
            # 按句号/换行切分
            sentences = []
            for s in para.replace("\n", "。").split("。"):
                s = s.strip()
                if s:
                    sentences.append(s + "。")
            # 合并成不超过 max_chars 的块
            current = ""
            for s in sentences:
                if len(current) + len(s) <= max_chars:
                    current += s
                else:
                    if current:
                        chunks.append({"text": current.strip(), "source": source})
                    current = s
            if current:
                chunks.append({"text": current.strip(), "source": source})
        else:
            chunks.append({"text": para, "source": source})

    return chunks


def main():
    if not os.path.isdir(DOCS_DIR):
        print(f"❌ 目录不存在: {DOCS_DIR}")
        return

    all_files = []
    for root, dirs, files in os.walk(DOCS_DIR):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                all_files.append(os.path.join(root, f))

    if not all_files:
        print(f"❌ 在 {DOCS_DIR} 中未找到支持的文档")
        print(f"   支持的格式: {', '.join(SUPPORTED_EXTENSIONS)}")
        return

    print(f"📂 找到 {len(all_files)} 个文档，开始导入...\n")

    total_chunks = 0
    success_chunks = 0

    for filepath in sorted(all_files):
        filename = os.path.basename(filepath)
        print(f"📄 处理: {filename}")

        # 1. 转换为文本
        text = convert_to_text(filepath)
        if not text:
            print(f"  ⏭️  跳过（无内容）")
            continue

        # 2. 分段
        chunks = chunk_text(text, source=filename)
        print(f"  ✂️  分为 {len(chunks)} 个知识片段")

        # 3. 逐个导入（直接写入 LanceDB，不需要启动 Flask）
        for chunk in chunks:
            ok = lancedb_service.add_document(chunk["text"], chunk["source"])
            total_chunks += 1
            if ok:
                success_chunks += 1

        print(f"  ✅ 完成")

    print(f"\n{'='*40}")
    print(f"📊 导入完成！")
    print(f"   总片段数: {total_chunks}")
    print(f"   成功导入: {success_chunks}")
    print(f"   失败: {total_chunks - success_chunks}")


if __name__ == "__main__":
    main()
