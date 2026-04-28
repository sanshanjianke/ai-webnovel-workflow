from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class Entry(BaseModel):
    id: str
    keys: list[str]
    content: str
    secondary_keys: list[str] = []
    constant: bool = False
    priority: int = 10
    position: str = "before_char"
    metadata: dict = {}


class BaseWorldBook(ABC):
    @abstractmethod
    def get_active_entries(self, context_tokens: list[str]) -> list[Entry]:
        pass

    @abstractmethod
    def get_entry(self, entry_id: str) -> Optional[Entry]:
        pass

    @abstractmethod
    def update_entry(self, entry_id: str, data: dict) -> None:
        pass

    @abstractmethod
    def create_entry(self, entry: Entry) -> None:
        pass

    @abstractmethod
    def delete_entry(self, entry_id: str) -> None:
        pass

    @abstractmethod
    def commit(self, message: str) -> str:
        pass

    @abstractmethod
    def revert(self, commit_hash: str) -> None:
        pass

    @abstractmethod
    def list_commits(self) -> list[dict]:
        pass
