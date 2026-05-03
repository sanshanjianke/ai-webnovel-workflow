from abc import ABC, abstractmethod
from typing import Optional, Literal
from pydantic import BaseModel
from enum import Enum


class ExpertRole(str, Enum):
    MAIN = "main"
    REVIEW = "review"
    SUPPLEMENT = "supplement"


class Granularity(str, Enum):
    VOLUME = "volume"
    CHAPTER = "chapter"
    SCENE = "scene"


class ExpertOpinion(BaseModel):
    expert_id: str
    expert_type: str
    role: ExpertRole = ExpertRole.MAIN
    content: str
    suggestions: list[str] = []


class Outline(BaseModel):
    sequences: list[dict]
    characters: list[dict]
    world_notes: list[str] = []


class BaseExpert(ABC):
    """专家基类"""
    
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


class BaseConfigurableExpert(BaseExpert):
    """可配置专家基类 - 支持不同粒度和角色"""
    
    def __init__(
        self, 
        role: ExpertRole = ExpertRole.MAIN, 
        granularity: Granularity = Granularity.CHAPTER
    ):
        self._role = role
        self._granularity = granularity
    
    @property
    def role(self) -> ExpertRole:
        return self._role
    
    @property
    def granularity(self) -> Granularity:
        return self._granularity
    
    def speak_stream(self, outline=None, context: dict = None):
        """流式发言。yield (chunk_type, content) 元组，最后 yield ("__done__", ExpertOpinion)。
        默认实现委托给 speak() 并一次性返回全部内容。
        """
        opinion = self.speak(outline, context or {})
        # 分块返回，模拟流式
        text = opinion.content
        chunk_size = 10
        for i in range(0, len(text), chunk_size):
            yield ("content", text[i:i+chunk_size])
        yield ("__done__", opinion)
