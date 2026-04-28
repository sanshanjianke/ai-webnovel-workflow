from abc import ABC, abstractmethod
from typing import Callable, Optional
from pydantic import BaseModel


class ExpertOpinion(BaseModel):
    expert_id: str
    expert_type: str
    content: str
    suggestions: list[str] = []


class Outline(BaseModel):
    sequences: list[dict]
    characters: list[dict]
    world_notes: list[str] = []


class BaseExpert(ABC):
    @property
    @abstractmethod
    def expert_id(self) -> str:
        pass

    @property
    @abstractmethod
    def expert_type(self) -> str:
        pass

    @abstractmethod
    def speak(self, outline: Optional[Outline], context: dict) -> ExpertOpinion:
        pass
