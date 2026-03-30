"""
检索模块 - 混合检索（向量搜索 + 关键词过滤）

支持多种embedding后端：
- DashScope API (text-embedding-v3)
- 本地模型 (qwen3-embedding-4b via llama.cpp)
"""

import re
import chromadb
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class SearchResult:
    """检索结果"""
    id: str
    name: str
    dimension: str
    content: str
    score: float
    match_type: str  # 'vector', 'keyword', 'hybrid'


class EmbeddingBackend(ABC):
    """Embedding后端基类"""
    
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        pass


class DashScopeEmbedding(EmbeddingBackend):
    """DashScope API Embedding"""
    
    def __init__(self, api_key: str, model: str = "text-embedding-v3"):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        
        all_embeddings = []
        for i in range(0, len(texts), 10):  # 每批最多10条
            batch = texts[i:i+10]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch
            )
            all_embeddings.extend([item.embedding for item in response.data])
        
        return all_embeddings


class LocalEmbedding(EmbeddingBackend):
    """本地模型 Embedding (llama.cpp)"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        # TODO: 加载本地模型
        # from llama_cpp import Llama
        # self.llm = Llama(model_path=model_path, embedding=True)
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        # TODO: 实现本地embedding
        raise NotImplementedError("本地embedding待实现")


class HybridRetriever:
    """混合检索器"""
    
    def __init__(
        self,
        vector_db_path: Path,
        embedding_backend: EmbeddingBackend
    ):
        self.client = chromadb.PersistentClient(path=str(vector_db_path))
        self.embedding = embedding_backend
        self.collections = {}
    
    def get_collection(self, dimension: str):
        """获取collection"""
        if dimension not in self.collections:
            self.collections[dimension] = self.client.get_collection(
                name=f"slices_{dimension}"
            )
        return self.collections[dimension]
    
    def extract_keywords(self, query: str) -> List[str]:
        """提取关键词（简单分词）"""
        # 移除标点
        query = re.sub(r'[，。！？、；：""''（）\[\]【】]', ' ', query)
        # 分词（简单按空格）
        words = query.split()
        # 过滤停用词
        stopwords = {'的', '了', '是', '在', '有', '和', '与', '或', '这', '那', '什么', '怎么', '如何'}
        keywords = [w for w in words if w and w not in stopwords and len(w) > 1]
        return keywords
    
    def search(
        self,
        query: str,
        dimension: Optional[str] = None,
        k: int = 5,
        use_keyword: bool = True,
        keyword_weight: float = 0.5
    ) -> List[SearchResult]:
        """
        混合检索
        
        Args:
            query: 查询文本
            dimension: 指定维度（plot/character/emotion/function）
            k: 返回数量
            use_keyword: 是否使用关键词过滤
            keyword_weight: 关键词匹配的权重（0-1）
        
        Returns:
            检索结果列表
        """
        # 1. 生成查询向量
        query_embedding = self.embedding.embed([query])[0]
        
        # 2. 提取关键词
        keywords = self.extract_keywords(query) if use_keyword else []
        
        # 3. 向量搜索
        if dimension:
            collections = [(dimension, self.get_collection(dimension))]
        else:
            # 搜索所有维度
            collections = []
            for coll in self.client.list_collections():
                coll_name = coll.name
                if coll_name.startswith('slices_'):
                    dim = coll_name.replace('slices_', '')
                    collections.append((dim, self.get_collection(dim)))
        
        results = []
        
        for dim, coll in collections:
            # 向量搜索
            vector_results = coll.query(
                query_embeddings=[query_embedding],
                n_results=k * 2  # 多取一些，用于关键词过滤
            )
            
            # 处理结果
            for i, doc_id in enumerate(vector_results['ids'][0]):
                doc_text = vector_results['documents'][0][i]
                metadata = vector_results['metadatas'][0][i]
                distance = vector_results['distances'][0][i] if vector_results.get('distances') else 0
                
                # 关键词匹配度
                keyword_score = 0
                if keywords:
                    matched = sum(1 for kw in keywords if kw in doc_text)
                    keyword_score = matched / len(keywords) if keywords else 0
                
                # 混合得分（距离越小越好，关键词越多越好）
                # distance范围约0.4-1.2，转换为0-1
                vector_score = 1 - min(distance / 1.5, 1)
                hybrid_score = vector_score * (1 - keyword_weight) + keyword_score * keyword_weight
                
                results.append(SearchResult(
                    id=doc_id,
                    name=metadata.get('name', doc_id),
                    dimension=dim,
                    content=doc_text,
                    score=hybrid_score,
                    match_type='hybrid' if keywords else 'vector'
                ))
        
        # 4. 按得分排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:k]
    
    def search_by_tags(
        self,
        tags: Dict[str, str],
        dimension: str = "plot",
        k: int = 10
    ) -> List[SearchResult]:
        """
        按标签精准匹配
        
        Args:
            tags: 标签字典，如 {"functions": "打脸", "characters": "李白"}
            dimension: 维度
            k: 返回数量
        """
        coll = self.get_collection(dimension)
        
        # 获取所有文档
        all_docs = coll.get(include=['documents', 'metadatas'])
        
        results = []
        for i, metadata in enumerate(all_docs['metadatas']):
            # 检查标签匹配
            match = True
            for key, value in tags.items():
                meta_value = metadata.get(key, "")
                if value not in meta_value:
                    match = False
                    break
            
            if match:
                results.append(SearchResult(
                    id=all_docs['ids'][i],
                    name=metadata.get('name', all_docs['ids'][i]),
                    dimension=dimension,
                    content=all_docs['documents'][i],
                    score=1.0,
                    match_type='keyword'
                ))
        
        return results[:k]


def create_retriever(
    vector_db_path: Path,
    embedding_type: str = "dashscope",
    api_key: Optional[str] = None,
    model_path: Optional[str] = None
) -> HybridRetriever:
    """
    创建检索器
    
    Args:
        vector_db_path: 向量库路径
        embedding_type: embedding类型 ("dashscope" 或 "local")
        api_key: DashScope API密钥
        model_path: 本地模型路径
    """
    if embedding_type == "dashscope":
        if not api_key:
            raise ValueError("DashScope需要提供api_key")
        embedding = DashScopeEmbedding(api_key=api_key)
    elif embedding_type == "local":
        if not model_path:
            raise ValueError("本地模型需要提供model_path")
        embedding = LocalEmbedding(model_path=model_path)
    else:
        raise ValueError(f"不支持的embedding类型: {embedding_type}")
    
    return HybridRetriever(vector_db_path, embedding)


if __name__ == "__main__":
    import os
    
    # 测试混合检索
    print("=== 测试混合检索 ===\n")
    
    # 从环境变量获取API key
    api_key = os.getenv("EMBEDDING_API_KEY", "")
    retriever = create_retriever(
        vector_db_path=Path('test_output/07_vector_db'),
        embedding_type='dashscope',
        api_key=api_key
    )
    
    # 测试查询
    queries = [
        "郑屠",
        "李白怎么制服武疯子",
        "打脸爽点",
        "穿越归来"
    ]
    
    for query in queries:
        print(f"\n查询: {query}")
        results = retriever.search(query, k=3, keyword_weight=0.3)
        
        for r in results:
            print(f"  [{r.dimension}] {r.name} (得分: {r.score:.3f}, 方式: {r.match_type})")
    
    # 测试标签搜索
    print("\n\n=== 测试标签搜索 ===\n")
    
    tag_queries = [
        {"appeal_types": "打脸"},
        {"functions": "铺垫"},
        {"characters": "李白"}
    ]
    
    for tags in tag_queries:
        print(f"标签: {tags}")
        results = retriever.search_by_tags(tags, k=3)
        for r in results:
            print(f"  → {r.name}")