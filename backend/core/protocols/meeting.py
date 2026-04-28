from abc import ABC, abstractmethod
from typing import Optional
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


class BaseMeetingProtocol(ABC):
    @property
    @abstractmethod
    def protocol_id(self) -> str:
        pass

    @abstractmethod
    def get_speaking_order(self, context: dict = None) -> list[tuple[str, str]]:
        pass

    @abstractmethod
    def should_continue(self, rounds: int, consensus: float) -> bool:
        pass

    @abstractmethod
    def format_output(self, history: list[ExpertOpinion]) -> Outline:
        pass
