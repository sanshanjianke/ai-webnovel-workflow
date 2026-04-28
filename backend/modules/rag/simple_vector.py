from typing import Optional
import chromadb
from chromadb.config import Settings

from backend.core.protocols.rag import BaseRAGAgent, RetrievedDoc, Document
from backend.core.registry import register_module


@register_module("rag")
class SimpleVectorRetriever(BaseRAGAgent):
    def __init__(self, persist_dir: str = None, embedding_fn=None):
        self.persist_dir = persist_dir
        self.embedding_fn = embedding_fn
        
        if persist_dir:
            self.client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.client = chromadb.Client()
        
        self.collection = None
    
    def _get_or_create_collection(self, name: str = "default"):
        if self.collection is None:
            self.collection = self.client.get_or_create_collection(name=name)
        return self.collection
    
    def retrieve(self, query: str, context: dict = None, k: int = 5) -> list[RetrievedDoc]:
        collection = self._get_or_create_collection()
        
        results = collection.query(
            query_texts=[query],
            n_results=k
        )
        
        docs = []
        if results and results.get("ids"):
            ids = results["ids"][0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            for i, doc_id in enumerate(ids):
                docs.append(RetrievedDoc(
                    id=doc_id,
                    content=documents[i] if i < len(documents) else "",
                    score=1.0 - (distances[i] if i < len(distances) else 0.0),
                    metadata=metadatas[i] if i < len(metadatas) else {}
                ))
        
        return docs
    
    def index(self, documents: list[Document]) -> None:
        collection = self._get_or_create_collection()
        
        ids = [doc.id for doc in documents]
        texts = [doc.content for doc in documents]
        metadatas = [doc.metadata if doc.metadata else {"_empty": True} for doc in documents]
        
        collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
    
    def delete(self, ids: list[str]) -> None:
        collection = self._get_or_create_collection()
        collection.delete(ids=ids)
    
    def count(self) -> int:
        collection = self._get_or_create_collection()
        return collection.count()
