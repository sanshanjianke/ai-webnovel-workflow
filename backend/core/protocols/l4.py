from abc import ABC, abstractmethod
from typing import Iterator
from pydantic import BaseModel


class ChapterPlan(BaseModel):
    chapter_name: str
    scenes: list[dict]
    emotion_curve: str = ""
    hooks: list[str] = []


class GeneratedText(BaseModel):
    chapter_name: str
    content: str
    word_count: int


class BaseL4Renderer(ABC):
    @abstractmethod
    def render(
        self,
        chapter_plan: ChapterPlan,
        rag_technique,
        world_book
    ) -> GeneratedText:
        pass

    @abstractmethod
    def stream_render(
        self,
        chapter_plan: ChapterPlan,
        rag_technique,
        world_book
    ) -> Iterator[str]:
        pass
