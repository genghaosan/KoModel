import lancedb
import os
import re
from config import Config
from services.ollama_service import ollama_service
from typing import List, Dict


class LanceDBService:
    """LanceDB 向量数据库操作封装"""

    def __init__(self):
        os.makedirs(Config.LANCEDB_PATH, exist_ok=True)
        self.db = lancedb.connect(Config.LANCEDB_PATH)
        self.table = None
        self._init_table()

    def _init_table(self):
        """初始化表（如果不存在则创建）"""
        dummy_data = [
            {
                "vector": [0.0] * 768,
                "text": "初始化占位数据",
                "source": "system"
            }
        ]

        if Config.TABLE_NAME in self.db.table_names():
            self.table = self.db.open_table(Config.TABLE_NAME)
        else:
            self.table = self.db.create_table(Config.TABLE_NAME, dummy_data)

    def add_document(self, text: str, source: str = "user_upload") -> bool:
        """添加文档到向量库"""
        try:
            embedding = ollama_service.get_embedding(text)
            data = [{
                "vector": embedding,
                "text": text,
                "source": source
            }]
            self.table.add(data)
            return True
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False

    def _dedup(self, records: List[dict]) -> List[Dict]:
        """去重并过滤占位数据"""
        seen = set()
        result = []
        for r in records:
            text = r.get("text", "")
            if text != "初始化占位数据" and text not in seen:
                seen.add(text)
                result.append({
                    "text": text,
                    "source": r.get("source", "unknown"),
                    "_distance": r.get("_distance", 0)
                })
        return result

    def _get_all_records(self) -> List[dict]:
        """真正的全表扫描 - 使用 to_pandas"""
        try:
            import pandas as pd
            df = self.table.to_pandas()
            records = df.to_dict('records')
            return records
        except Exception as e:
            print(f"全表扫描失败: {e}")
            return []

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        混合搜索策略：
        1. 包含具体条款号 -> 全表关键词精确匹配
        2. 概括性问题 -> 匹配元数据片段
        3. 一般问题 -> 向量语义检索
        """
        try:
            # 提取查询中的条款号
            article_nums = re.findall(r'第[一二三四五六七八九十百千零\d]+[条章节]', query)
            query_embedding = ollama_service.get_embedding(query)

            results = []

            # 策略1: 条款号精确匹配
            if article_nums:
                all_records = self._get_all_records()
                keyword_matches = []

                for r in all_records:
                    text = r.get("text", "")
                    if text == "初始化占位数据":
                        continue

                    match_count = sum(1 for num in article_nums if num in text)
                    if match_count > 0:
                        keyword_matches.append({
                            "text": text,
                            "source": r.get("source", "unknown"),
                            "match_score": match_count * 10,
                            "_distance": 0
                        })

                keyword_matches.sort(key=lambda x: x["match_score"], reverse=True)
                results.extend(keyword_matches[:top_k])

            # 策略2: 概括性问题关键词匹配（新增）
            summary_keywords = ['多少条', '多少章', '总条数', '总章数', '施行日期', '什么时候实施', '共几条', '共几章',
                                '几章几节']
            if any(kw in query for kw in summary_keywords):
                all_records = self._get_all_records()
                for r in all_records:
                    text = r.get("text", "")
                    if "【文档概览】" in text:
                        results.append({
                            "text": text,
                            "source": r.get("source", "unknown"),
                            "match_score": 100,
                            "_distance": 0
                        })
                        break  # 只取元数据片段

            # 策略3: 向量语义检索（补充）
            if len(results) < top_k:
                vector_results = (
                    self.table
                    .search(query_embedding)
                    .limit(top_k * 3)
                    .to_list()
                )

                deduped = self._dedup(vector_results)
                existing_texts = {r["text"] for r in results}

                for r in deduped:
                    if r["text"] not in existing_texts:
                        results.append(r)

            return results[:top_k]

        except Exception as e:
            print(f"搜索失败: {e}")
            return []

    def get_stats(self) -> dict:
        """获取知识库统计信息"""
        try:
            count = self.table.count_rows()
            return {
                "total_records": count,
                "table_name": Config.TABLE_NAME,
                "db_path": Config.LANCEDB_PATH
            }
        except Exception as e:
            return {"error": str(e)}


# 实例化
lancedb_service = LanceDBService()