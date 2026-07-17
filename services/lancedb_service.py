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
        # nomic-embed-text 输出 768 维向量
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
            if r["text"] != "初始化占位数据" and r["text"] not in seen:
                seen.add(r["text"])
                result.append({"text": r["text"], "source": r["source"]})
        return result

    def _scan_all(self, query_embedding: list) -> List[dict]:
        """获取全量记录（用于关键词扫描）"""
        return self.table.search(query_embedding).limit(10000).to_list()

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        混合搜索：向量检索 + 关键词精确匹配
        
        nomic-embed-text 对中文条款号的嵌入质量有限，
        因此当查询包含具体条款号（如"第四十九条"）时，
        采用全表关键词扫描确保能找到目标条款。
        
        无条款号时，走标准向量检索 + 去重。
        """
        try:
            # 提取查询中的条款号（第X条/第X章/第X节）
            article_nums = re.findall(r'第[一二三四五六七八九十百千零\d]+[条章节]', query)

            query_embedding = ollama_service.get_embedding(query)

            # —— 有条款号：全表关键词扫描 ——
            if article_nums:
                all_records = self._scan_all(query_embedding)
                deduped = self._dedup(all_records)
                # 筛选含条款号的结果，按匹配数降序（匹配越多越精确）
                keyword_matches = [
                    r for r in deduped
                    if any(num in r["text"] for num in article_nums)
                ]
                keyword_matches.sort(
                    key=lambda r: sum(1 for num in article_nums if num in r["text"]),
                    reverse=True
                )
                if keyword_matches:
                    return keyword_matches[:top_k]
                # 关键词没匹配到，回退到向量结果
                return deduped[:top_k]

            # —— 无条款号：标准向量检索 ——
            vector_results = (
                self.table
                .search(query_embedding)
                .limit(top_k * 5)
                .to_list()
            )
            return self._dedup(vector_results)[:top_k]

        except Exception as e:
            print(f"搜索失败: {e}")
            return []

# 实例化
lancedb_service = LanceDBService()