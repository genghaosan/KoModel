"""
知识库导入脚本
支持多种文档格式: .txt .md .docx .pdf .xlsx .pptx 等
办公文档（.docx/.pdf/.xlsx 等）会自动转为 .md 缓存到 docs/md/ 目录
依赖: 全局 markitdown 命令 (https://github.com/microsoft/markitdown)
用法: python import_docs.py
"""
import os
import re
import subprocess
from services.lancedb_service import lancedb_service

DOCS_DIR = "./docs"
MD_CACHE_DIR = os.path.join(DOCS_DIR, "md")
OFFICE_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".pptx", ".html", ".htm"}


def convert_office_to_md(filepath: str) -> str | None:
    """
    将办公文档转为 .md 缓存到 docs/md/ 目录
    已转换过的直接返回缓存路径（重复检测）
    返回 .md 文件路径，失败返回 None
    """
    basename = os.path.splitext(os.path.basename(filepath))[0]
    md_path = os.path.join(MD_CACHE_DIR, basename + ".md")

    # 重复检测：已转换过则跳过
    if os.path.exists(md_path):
        print(f"  ⏭️  已转换过，跳过: {basename}.md")
        return md_path

    print(f"  🔄 正在转换: {os.path.basename(filepath)}")
    try:
        result = subprocess.run(
            ["markitdown", filepath],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            os.makedirs(MD_CACHE_DIR, exist_ok=True)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(result.stdout)
            print(f"  ✅ 转换完成: {basename}.md")
            return md_path

        if result.returncode != 0:
            print(f"  ❌ markitdown 转换失败 [{os.path.basename(filepath)}], returncode={result.returncode}")
            if result.stderr.strip():
                print(f"     错误信息: {result.stderr.strip()[:200]}")
            return None

        print(f"  ⚠️ markitdown 输出为空 [{os.path.basename(filepath)}]，跳过")
        return None

    except FileNotFoundError:
        print("  ❌ 未找到 markitdown 命令，请确保已安装: pip install markitdown")
        raise
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ 转换超时 [{os.path.basename(filepath)}]，跳过")
        return None
    except Exception as e:
        print(f"  ⚠️ 转换失败 [{os.path.basename(filepath)}]: {e}")
        return None


def read_text_file(filepath: str) -> str:
    """直接读取 .txt/.md/.csv 文件"""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def chunk_text(text: str, source: str, max_chars: int = 500) -> list[dict]:
    """
    将文本分段为知识单元
    策略: 按空行/段落分割，每段作为一个独立知识单元
    """
    # 按两个以上换行分割段落
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # 合并子项（如（一）（二）（三）...）到前一段，避免"（四）就业状况；"变成独立片段
    merged = []
    for p in paragraphs:
        if merged and re.match(r"^（[一二三四五六七八九十百]+）", p):
            merged[-1] += "\n" + p
        else:
            merged.append(p)
    paragraphs = merged

    chunks = []
    current_chapter = ""
    chapter_pattern = re.compile(r"^第[一二三四五六七八九十百千]+章")

    for para in paragraphs:
        if len(para.strip()) < 2:
            continue

        # 检测是否为章节标题，更新当前章节并保留标题作为独立片段
        if chapter_pattern.match(para):
            current_chapter = para.strip()
            chunks.append({"text": para, "source": source})
            continue

        # 给非章节段落加上章节前缀，方便检索定位
        text_with_prefix = f"【{current_chapter}】{para}" if current_chapter else para

        # 如果段落太长，按句子或固定长度切分
        if len(text_with_prefix) > max_chars:
            # 按句号/换行切分（用原始 para 切分，前缀固定在每个子块上）
            sentences = []
            for s in para.replace("\n", "。").split("。"):
                s = s.strip()
                if s:
                    sentences.append(s + "。")
            # 合并成不超过 max_chars 的块
            current = ""
            for s in sentences:
                candidate = current + s
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(
                            {"text": f"【{current_chapter}】{current.strip()}" if current_chapter else current.strip(),
                             "source": source}
                        )
                    current = s
            if current:
                chunks.append(
                    {"text": f"【{current_chapter}】{current.strip()}" if current_chapter else current.strip(),
                     "source": source}
                )
        else:
            chunks.append({"text": text_with_prefix, "source": source})

    return chunks


def collect_import_files() -> list[str]:
    """
    收集需要导入的文件列表
    逻辑：
      1. docs/ 下的办公文档 → 转为 docs/md/*.md（已转换则跳过）
      2. docs/md/ 下的 .md 文件 → 导入
      3. docs/ 下的 .txt/.md/.csv → 直接导入
    """
    all_office = []
    all_text = []

    # 扫描 docs/（不递归进子目录）
    if os.path.isdir(DOCS_DIR):
        for f in os.listdir(DOCS_DIR):
            fp = os.path.join(DOCS_DIR, f)
            if not os.path.isfile(fp):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in OFFICE_EXTENSIONS:
                all_office.append(fp)
            elif ext in {".txt", ".md", ".csv"}:
                all_text.append(fp)

    # 1. 转换办公文档为 .md
    os.makedirs(MD_CACHE_DIR, exist_ok=True)
    for fp in sorted(all_office):
        convert_office_to_md(fp)

    # 2. 收集所有待导入的文件
    import_files = []

    # 从 docs/md/ 取已转换的 .md
    cached_names = set()
    if os.path.isdir(MD_CACHE_DIR):
        for f in sorted(os.listdir(MD_CACHE_DIR)):
            if f.lower().endswith(".md"):
                import_files.append(os.path.join(MD_CACHE_DIR, f))
                cached_names.add(f)

    # 从 docs/ 取原始 .md/.txt/.csv
    # 跳过已被 docs/md/ 缓存覆盖的同名文件，避免重复导入
    for fp in sorted(all_text):
        if os.path.basename(fp) not in cached_names:
            import_files.append(fp)

    return import_files


def import_document(filepath: str) -> tuple[int, int]:
    """导入单个文档，返回 (总片段数, 成功数)"""
    filename = os.path.basename(filepath)
    print(f"📄 处理: {filename}")

    # 读取文本
    ext = os.path.splitext(filepath)[1].lower()
    text = read_text_file(filepath) if ext in {".txt", ".md", ".csv"} else ""
    if not text:
        print(f"  ⏭️  跳过（无内容）")
        return 0, 0

    # 分段
    chunks = chunk_text(text, source=filename)
    print(f"  ✂️  分为 {len(chunks)} 个知识片段")

    # 导入
    total = len(chunks)
    success = 0
    for chunk in chunks:
        if lancedb_service.add_document(chunk["text"], chunk["source"]):
            success += 1

    print(f"  ✅ 完成")
    return total, success


def main():
    if not os.path.isdir(DOCS_DIR):
        print(f"❌ 目录不存在: {DOCS_DIR}")
        return

    import_files = collect_import_files()

    if not import_files:
        print(f"❌ 未找到任何可导入的文档")
        return

    print(f"📂 找到 {len(import_files)} 个文档，开始导入...\n")

    total_chunks = 0
    success_chunks = 0

    for filepath in import_files:
        t, s = import_document(filepath)
        total_chunks += t
        success_chunks += s

    print(f"\n{'='*40}")
    print(f"📊 导入完成！")
    print(f"   总片段数: {total_chunks}")
    print(f"   成功导入: {success_chunks}")
    print(f"   失败: {total_chunks - success_chunks}")


if __name__ == "__main__":
    main()
