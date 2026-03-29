"""
双库存储模块 - 笔记6核心实现

实现双库分离：
1. 向量数据库：存储摘要+标签+指针（用于快速检索）
2. MD文本库：存储完整切片文本（用于提供完整上下文）

支持两种模式：
- 完整模式：使用LangChain的Multi-Vector Retriever（需要安装langchain）
- 简化模式：使用纯Python实现（无需依赖）
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import hashlib
import json

# 尝试导入LangChain，失败则使用简化实现
try:
    from langchain_core.documents import Document
    from langchain_core.vectorstores import VectorStore
    from langchain_chroma import Chroma
    from langchain.storage import InMemoryStore, LocalFileStore
    from langchain.retrievers.multi_vector import MultiVectorRetriever
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    # 简化实现
    class Document:
        """简化Document类"""
        def __init__(self, page_content: str, metadata: dict = None):
            self.page_content = page_content
            self.metadata = metadata or {}

from config import VECTOR_DB_PATH, TEXT_DB_PATH, EMBEDDING_MODEL, VECTOR_DB_TYPE
from text_processor import SliceUnit


# 简化实现（无LangChain时使用）
class SimpleVectorStore:
    """简化向量存储（仅用于演示，无实际向量检索功能）"""
    
    def __init__(self):
        self.documents = []
        self.ids = []
    
    def add_documents(self, documents: List[Document], ids: List[str] = None):
        """添加文档"""
        self.documents.extend(documents)
        if ids:
            self.ids.extend(ids)
        else:
            self.ids.extend([f"doc_{i}" for i in range(len(documents))])
    
    def similarity_search(self, query: str, k: int = 5, filter: dict = None) -> List[Document]:
        """模拟相似度搜索（简化版：返回前k个文档）"""
        results = []
        for doc in self.documents[:k]:
            if filter:
                # 简单过滤
                match = all(doc.metadata.get(k) == v for k, v in filter.items())
                if match:
                    results.append(doc)
            else:
                results.append(doc)
        return results
    
    def _collection_count(self):
        """返回文档数量"""
        return len(self.documents)


class SimpleDocStore:
    """简化文档存储"""
    
    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path
        self.documents = {}  # 内存存储
        
        if storage_path:
            storage_path.mkdir(parents=True, exist_ok=True)
    
    def mset(self, items: List[tuple]):
        """批量存储"""
        for key, value in items:
            self.documents[key] = value
            
            # 如果有存储路径，也保存到文件
            if self.storage_path:
                # 从value中提取维度和ID
                if hasattr(value, 'metadata'):
                    dim = value.metadata.get('dimension', 'default')
                    unit_id = value.metadata.get('unit_id', key)
                    file_path = self.storage_path / dim / f"{unit_id}.md"
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(value.page_content)
    
    def mget(self, keys: List[str]) -> List[Document]:
        """批量获取"""
        return [self.documents.get(k) for k in keys]


class DualStorageManager:
    """双库存储管理器"""
    
    def __init__(self, embedding=None, use_local_storage=True):
        """
        Args:
            embedding: LangChain Embeddings对象
            use_local_storage: 是否使用本地文件存储（MD文本库）
        """
        self.embedding = embedding
        self.use_local_storage = use_local_storage
        
        # 初始化向量数据库
        self.vector_store = None
        self.doc_store = None
        self.retriever = None
        
        self._init_stores()
    
    def _init_stores(self):
        """初始化存储系统"""
        
        # 向量数据库（Chroma）
        if LANGCHAIN_AVAILABLE and self.embedding:
            self.vector_store = Chroma(
                embedding_function=self.embedding,
                persist_directory=str(VECTOR_DB_PATH),
                collection_name="hybrid_rag_slices"
            )
        else:
            # 如果没有embedding或没有LangChain，使用简化存储
            if not LANGCHAIN_AVAILABLE:
                print("提示: LangChain未安装，使用简化存储模式")
            else:
                print("提示: 未提供embedding，使用简化存储模式")
            self.vector_store = SimpleVectorStore()
        
        # MD文本库（文档存储）
        if self.use_local_storage:
            TEXT_DB_PATH.mkdir(parents=True, exist_ok=True)
            if LANGCHAIN_AVAILABLE:
                self.doc_store = LocalFileStore(str(TEXT_DB_PATH))
            else:
                self.doc_store = SimpleDocStore(TEXT_DB_PATH)
        else:
            if LANGCHAIN_AVAILABLE:
                self.doc_store = InMemoryStore()
            else:
                self.doc_store = SimpleDocStore()
        
        # Multi-Vector Retriever
        if LANGCHAIN_AVAILABLE and self.embedding:
            self.retriever = MultiVectorRetriever(
                vectorstore=self.vector_store,
                docstore=self.doc_store,
                id_key="doc_id"
            )
        else:
            self.retriever = None
    
    def store_slices(self, slices: Dict[str, List[SliceUnit]]) -> Dict:
        """
        存储多维度切片
        
        Args:
            slices: 各维度的切片列表
            
        Returns:
            存储结果统计
        """
        stats = {"total": 0, "by_dimension": {}}
        
        for dimension, slice_list in slices.items():
            dim_stats = self._store_dimension_slices(dimension, slice_list)
            stats["by_dimension"][dimension] = dim_stats
            stats["total"] += dim_stats["count"]
        
        return stats
    
    def _store_dimension_slices(self, dimension: str, slice_list: List[SliceUnit]) -> Dict:
        """存储单个维度的切片"""
        
        stats = {"dimension": dimension, "count": 0, "ids": []}
        
        for slice_unit in slice_list:
            doc_id = self._store_slice(slice_unit)
            stats["ids"].append(doc_id)
            stats["count"] += 1
        
        return stats
    
    def _store_slice(self, slice_unit: SliceUnit) -> str:
        """
        存储单个切片
        
        返回文档ID（用于检索）
        """
        doc_id = slice_unit.metadata.text_hash  # 使用文本hash作为ID
        
        # 1. 向量数据库：存储摘要+标签
        if self.vector_store:
            summary_doc = Document(
                page_content=slice_unit.summary,  # 摘要作为检索内容
                metadata={
                    "doc_id": doc_id,  # 关联键
                    "dimension": slice_unit.metadata.dimension,
                    "unit_id": slice_unit.metadata.unit_id,
                    "name": slice_unit.metadata.name,
                    **slice_unit.metadata.tags  # 所有标签
                }
            )
            
            # 存入向量库
            self.vector_store.add_documents([summary_doc], ids=[doc_id])
        
        # 2. MD文本库：存储完整文本
        if self.doc_store:
            full_text_doc = Document(
                page_content=slice_unit.full_text,
                metadata={
                    "doc_id": doc_id,
                    "dimension": slice_unit.metadata.dimension,
                    "unit_id": slice_unit.metadata.unit_id
                }
            )
            
            # 存入文本库
            self.doc_store.mset([(doc_id, full_text_doc)])
        
        # 3. 额外保存为MD文件（便于查看）
        self._save_as_md_file(slice_unit)
        
        return doc_id
    
    def _save_as_md_file(self, slice_unit: SliceUnit):
        """保存为MD文件（便于查看和调试）"""
        md_dir = TEXT_DB_PATH / slice_unit.metadata.dimension
        md_dir.mkdir(parents=True, exist_ok=True)
        
        md_path = md_dir / f"{slice_unit.metadata.unit_id}.md"
        
        md_content = f"""# {slice_unit.metadata.name}

**维度**: {slice_unit.metadata.dimension}
**ID**: {slice_unit.metadata.unit_id}
**标签**: {json.dumps(slice_unit.metadata.tags, ensure_ascii=False)}

---

## 摘要
{slice_unit.summary}

---

## 完整文本
{slice_unit.full_text}
"""
        
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
    
    def retrieve(
        self, 
        query: str, 
        dimension: Optional[str] = None,
        k: int = 5
    ) -> List[Document]:
        """
        检索
        
        Args:
            query: 查询文本
            dimension: 指定维度（可选）
            k: 返回数量
            
        Returns:
            检索结果（完整文本）
        """
        if not self.retriever:
            print("警告: 检索器未初始化，返回空结果")
            return []
        
        # 如果指定维度，添加过滤条件
        if dimension:
            # Chroma支持的过滤方式
            filter_dict = {"dimension": dimension}
            results = self.retriever.invoke(query, filter=filter_dict, k=k)
        else:
            results = self.retriever.invoke(query, k=k)
        
        return results
    
    def retrieve_by_tags(
        self,
        tags: Dict[str, Any],
        k: int = 5
    ) -> List[Document]:
        """
        通过标签检索
        
        Args:
            tags: 标签字典
            k: 返回数量
            
        Returns:
            检索结果
        """
        if not self.vector_store:
            return []
        
        # 使用Chroma的where过滤
        results = self.vector_store.similarity_search(
            query="",  # 空查询（只用标签过滤）
            k=k,
            filter=tags
        )
        
        # 获取完整文本
        full_docs = []
        for doc in results:
            doc_id = doc.metadata.get("doc_id")
            if doc_id:
                full_doc = self.doc_store.mget([doc_id])[0]
                if full_doc:
                    full_docs.append(full_doc)
        
        return full_docs
    
    def get_slice_by_id(self, doc_id: str) -> Optional[Document]:
        """通过ID获取完整切片"""
        if self.doc_store:
            result = self.doc_store.mget([doc_id])
            return result[0] if result else None
        return None
    
    def get_collection_stats(self) -> Dict:
        """获取存储统计"""
        stats = {
            "vector_store": {
                "type": VECTOR_DB_TYPE,
                "path": str(VECTOR_DB_PATH),
                "count": self.vector_store._collection.count() if self.vector_store else 0
            },
            "doc_store": {
                "type": "LocalFileStore" if self.use_local_storage else "InMemoryStore",
                "path": str(TEXT_DB_PATH) if self.use_local_storage else "memory"
            }
        }
        return stats


class VectorDBManager:
    """向量数据库管理（简化版）"""
    
    def __init__(self, embedding=None):
        """初始化"""
        self.embedding = embedding
        self.vector_store = None
        
        if embedding:
            self.vector_store = Chroma(
                embedding_function=embedding,
                persist_directory=str(VECTOR_DB_PATH),
                collection_name="slices_vector"
            )
    
    def add_documents(self, documents: List[Document]):
        """添加文档"""
        if self.vector_store:
            self.vector_store.add_documents(documents)
    
    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """相似度搜索"""
        if self.vector_store:
            return self.vector_store.similarity_search(query, k=k)
        return []
    
    def similarity_search_with_filter(
        self, 
        query: str, 
        filter_dict: Dict,
        k: int = 5
    ) -> List[Document]:
        """带过滤条件的搜索"""
        if self.vector_store:
            return self.vector_store.similarity_search(query, k=k, filter=filter_dict)
        return []


class TextDBManager:
    """MD文本库管理"""
    
    def __init__(self):
        """初始化"""
        TEXT_DB_PATH.mkdir(parents=True, exist_ok=True)
    
    def save_document(self, doc_id: str, content: str, metadata: Dict):
        """保存文档"""
        dimension = metadata.get("dimension", "default")
        unit_id = metadata.get("unit_id", doc_id)
        
        md_dir = TEXT_DB_PATH / dimension
        md_dir.mkdir(parents=True, exist_ok=True)
        
        md_path = md_dir / f"{unit_id}.md"
        
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    def load_document(self, doc_id: str) -> Optional[str]:
        """加载文档"""
        # 需要知道维度才能找到文件
        # 这里简化处理，搜索所有维度目录
        for dim_dir in TEXT_DB_PATH.iterdir():
            if dim_dir.is_dir():
                for md_file in dim_dir.glob("*.md"):
                    if md_file.stem == doc_id:
                        with open(md_file, "r", encoding="utf-8") as f:
                            return f.read()
        return None
    
    def list_documents(self) -> List[Dict]:
        """列出所有文档"""
        docs = []
        for dim_dir in TEXT_DB_PATH.iterdir():
            if dim_dir.is_dir():
                for md_file in dim_dir.glob("*.md"):
                    docs.append({
                        "dimension": dim_dir.name,
                        "unit_id": md_file.stem,
                        "path": str(md_file)
                    })
        return docs


if __name__ == "__main__":
    # 测试双库存储（不使用embedding）
    print("=== 测试双库存储（无embedding模式） ===")
    
    from sample_data import AUCTION_SEQUENCE, ANNOTATED_SLICES
    from text_processor import SliceProcessorAgent
    
    # 1. 切片处理
    processor = SliceProcessorAgent()
    slices = processor.process_with_annotation(AUCTION_SEQUENCE, ANNOTATED_SLICES)
    
    # 2. 存储（无embedding）
    storage = DualStorageManager(embedding=None)
    stats = storage.store_slices(slices)
    
    print(f"\n存储统计: {stats}")
    print(f"MD文本库路径: {TEXT_DB_PATH}")
    
    # 3. 查看存储的文件
    text_db = TextDBManager()
    docs = text_db.list_documents()
    print(f"\n已存储的MD文件: {len(docs)}")
    for doc in docs[:5]:
        print(f"  - {doc['dimension']}/{doc['unit_id']}.md")