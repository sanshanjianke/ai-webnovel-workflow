from abc import ABC, abstractmethod
from typing import Callable, Optional
from pydantic import BaseModel


class Outline(BaseModel):
    sequences: list[dict]
    characters: list[dict]
    world_notes: list[str] = []


class BaseL2Architect(ABC):
    @abstractmethod
    def generate_outline(
        self,
        vision: dict,
        world_book,
        rag_history,
        rag_technique,
        llm,
        human_feedback: Callable
    ) -> Outline:
        pass
