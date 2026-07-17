import lancedb
import os
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
    
    # ponytail: LanceDB 默认使用余弦距离（cosine distance）计算相似度
    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """根据查询文本搜索相似文档"""
        try:
            query_embedding = ollama_service.get_embedding(query)
            results = (
                self.table
                .search(query_embedding)
                .limit(top_k)
                .to_list()
            )
            # ponytail: O(n²) 去重，top_k 很小，性能无影响
            seen = set()
            deduped = []
            for r in results:
                if r["text"] != "初始化占位数据" and r["text"] not in seen:
                    seen.add(r["text"])
                    deduped.append({"text": r["text"], "source": r["source"]})
            return deduped
        except Exception as e:
            print(f"搜索失败: {e}")
            return []

# 实例化
lancedb_service = LanceDBService()