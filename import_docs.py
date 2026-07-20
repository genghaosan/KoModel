"""
知识库导入脚本 — 修复版
支持多种文档格式: .txt .md .docx 等
"""
import os
import re
import subprocess
import time
from services.lancedb_service import lancedb_service

DOCS_DIR = "./docs"
MD_CACHE_DIR = os.path.join(DOCS_DIR, "md")
OFFICE_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".pptx", ".html", ".htm"}


def convert_office_to_md(filepath):
    """将办公文档转为 .md 缓存"""
    basename = os.path.splitext(os.path.basename(filepath))[0]
    md_path = os.path.join(MD_CACHE_DIR, basename + ".md")

    if os.path.exists(md_path):
        print(f"  已转换过，跳过: {basename}.md")
        return md_path

    print(f"  正在转换: {os.path.basename(filepath)}")
    try:
        result = subprocess.run(
            ["markitdown", filepath],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and result.stdout.strip():
            os.makedirs(MD_CACHE_DIR, exist_ok=True)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(result.stdout)
            print(f"  转换完成: {basename}.md")
            return md_path

        print(f"  转换失败: {os.path.basename(filepath)}")
        return None

    except FileNotFoundError:
        print("  未找到 markitdown 命令，请安装: pip install markitdown")
        raise
    except Exception as e:
        print(f"  转换失败 [{os.path.basename(filepath)}]: {e}")
        return None


def read_text_file(filepath):
    """读取文本文件"""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def chunk_text(text, source, max_chars=800):
    """
    以"第X条"为边界分割法律文本，确保法条完整性
    """
    text = text.replace('\r\n', '\n')

    # 章节标题正则
    chapter_pattern = re.compile(r'^第[一二三四五六七八九十百千]+章[　\s]*.+$', re.MULTILINE)
    # 法条开头正则
    article_pattern = re.compile(r'^第[一二三四五六七八九十百千零\d]+条[　\s]')

    chunks = []
    current_chapter = ""

    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 章节标题
        if chapter_pattern.match(line):
            current_chapter = line
            chunks.append({"text": line, "source": source, "type": "chapter"})
            i += 1
            continue

        # 法条开头
        if article_pattern.match(line):
            article_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                # 遇到下一条或新章节就停止
                if article_pattern.match(next_line) or chapter_pattern.match(next_line):
                    break
                if next_line:
                    article_lines.append(next_line)
                i += 1

            article_text = '\n'.join(article_lines)

            # 如果法条太长，按子项切分但保留上下文
            if len(article_text) > max_chars:
                # 尝试按（一）（二）等子项切分
                sub_items = re.split(r'(?=（[一二三四五六七八九十]+）)', article_text)
                current_chunk = sub_items[0]

                for sub in sub_items[1:]:
                    candidate = current_chunk + sub
                    if len(candidate) <= max_chars * 1.5:
                        current_chunk = candidate
                    else:
                        if current_chunk:
                            prefix = f"【{current_chapter}】" if current_chapter else ""
                            chunks.append({
                                "text": prefix + current_chunk.strip(),
                                "source": source,
                                "type": "article"
                            })
                        current_chunk = sub

                if current_chunk:
                    prefix = f"【{current_chapter}】" if current_chapter else ""
                    chunks.append({
                        "text": prefix + current_chunk.strip(),
                        "source": source,
                        "type": "article"
                    })
            else:
                prefix = f"【{current_chapter}】" if current_chapter else ""
                chunks.append({
                    "text": prefix + article_text,
                    "source": source,
                    "type": "article"
                })
            continue

        # 其他内容（前言、目录等）
        if line and len(line) > 5:
            prefix = f"【{current_chapter}】" if current_chapter else ""
            chunks.append({
                "text": prefix + line,
                "source": source,
                "type": "other"
            })

        i += 1

    return chunks


def collect_import_files():
    """收集需要导入的文件"""
    all_office = []
    all_text = []

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

    # 转换办公文档
    os.makedirs(MD_CACHE_DIR, exist_ok=True)
    for fp in sorted(all_office):
        convert_office_to_md(fp)

    # 收集所有待导入文件
    import_files = []
    cached_names = set()

    if os.path.isdir(MD_CACHE_DIR):
        for f in sorted(os.listdir(MD_CACHE_DIR)):
            if f.lower().endswith(".md"):
                import_files.append(os.path.join(MD_CACHE_DIR, f))
                cached_names.add(f)

    for fp in sorted(all_text):
        if os.path.basename(fp) not in cached_names:
            import_files.append(fp)

    return import_files


def import_document(filepath):
    """导入单个文档，带重试机制"""
    filename = os.path.basename(filepath)
    print(f"处理: {filename}")

    ext = os.path.splitext(filepath)[1].lower()
    text = read_text_file(filepath) if ext in {".txt", ".md", ".csv"} else ""
    if not text:
        print(f"  跳过（无内容）")
        return 0, 0

    chunks = chunk_text(text, source=filename)
    print(f"  分为 {len(chunks)} 个知识片段")

    total = len(chunks)
    success = 0

    for i, chunk in enumerate(chunks):
        retry = 0
        while retry < 3:
            try:
                if lancedb_service.add_document(chunk["text"], chunk["source"]):
                    success += 1
                    if (i + 1) % 10 == 0:
                        print(f"  ... 已导入 {i+1}/{total}")
                    break
            except Exception as e:
                print(f"  片段 {i+1} 导入失败（重试 {retry+1}/3）: {e}")
                time.sleep(1)
            retry += 1
        else:
            print(f"  片段 {i+1} 最终导入失败")

    print(f"  完成: {success}/{total} 成功")
    return total, success


def verify_import():
    """验证知识库内容"""
    try:
        count = lancedb_service.table.count_rows()
        print(f"\n当前知识库共有 {count} 条记录")

        # 抽样检查
        sample = lancedb_service.table.search().limit(5).to_list()
        print(f"抽样检查前5条:")
        for i, row in enumerate(sample):
            text = row.get("text", "")[:60]
            print(f"   {i+1}. {text}...")
    except Exception as e:
        print(f"验证失败: {e}")


def main():
    # 检查知识库是否已存在数据
    try:
        existing = lancedb_service.table.count_rows()
        if existing > 1:
            print(f"知识库已有 {existing} 条记录")
            response = input("是否清空后重新导入? (y/n): ").strip().lower()
            if response == 'y':
                print("清空知识库...")
                lancedb_service.db.drop_table(Config.TABLE_NAME)
                lancedb_service._init_table()
    except:
        pass

    if not os.path.isdir(DOCS_DIR):
        print(f"目录不存在: {DOCS_DIR}")
        return

    import_files = collect_import_files()
    if not import_files:
        print(f"未找到任何可导入的文档")
        return

    print(f"找到 {len(import_files)} 个文档，开始导入...\n")

    total_chunks = 0
    success_chunks = 0

    for filepath in import_files:
        t, s = import_document(filepath)
        total_chunks += t
        success_chunks += s

    print(f"\n{'='*50}")
    print(f"导入完成！")
    print(f"   总片段数: {total_chunks}")
    print(f"   成功导入: {success_chunks}")
    print(f"   失败: {total_chunks - success_chunks}")

    verify_import()


if __name__ == "__main__":
    from config import Config
    main()