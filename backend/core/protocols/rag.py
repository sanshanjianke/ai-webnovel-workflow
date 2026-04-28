from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class RetrievedDoc(BaseModel):
    id: str
    content: str
    score: float
    metadata: dict = {}


class Document(BaseModel):
    id: str
    content: str
    metadata: dict = {}


class BaseRAGAgent(ABC):
    @abstractmethod
    def retrieve(self, query: str, context: dict = None, k: int = 5) -> list[RetrievedDoc]:
        pass

    @abstractmethod
    def index(self, documents: list[Document]) -> None:
        pass
