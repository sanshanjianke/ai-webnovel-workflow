from abc import ABC, abstractmethod
from typing import Callable, Optional
from pydantic import BaseModel


class Outline(BaseModel):
    sequences: list[dict]
    characters: list[dict]
    world_notes: list[str] = []


class ChapterPlan(BaseModel):
    chapter_name: str
    scenes: list[dict]
    emotion_curve: str = ""
    hooks: list[str] = []


class BaseL3Narrative(ABC):
    @abstractmethod
    def generate_chapter_plan(
        self,
        outline: Outline,
        rag_technique,
        world_book
    ) -> ChapterPlan:
        pass
