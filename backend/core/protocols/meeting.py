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


class ExpertConfig(BaseModel):
    expert_id: str
    role: ExpertRole = ExpertRole.MAIN
    custom_prompt: Optional[str] = None


class MeetingConfig(BaseModel):
    meeting_name: str = "专家会议"
    granularity: Granularity = Granularity.CHAPTER
    experts: list[ExpertConfig]
    collaboration_mode: Literal["semi_auto", "full_auto", "manual"] = "semi_auto"
    max_rounds: int = 3
    max_speeches: int = 0  # 0 = unlimited, >0 = auto-stop after N speeches


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


class ConfigurableMeetingProtocol(BaseMeetingProtocol):
    """可配置的会议协议 - 支持动态专家队列"""
    
    def __init__(self, config: MeetingConfig):
        self.config = config
        self._experts_cache = {}
    
    @property
    def protocol_id(self) -> str:
        return f"configurable_{self.config.granularity.value}"
    
    def get_speaking_order(self, context: dict = None) -> list[tuple[str, str]]:
        return [
            (e.expert_id, e.role.value)
            for e in self.config.experts
        ]
    
    def should_continue(self, rounds: int, consensus: float) -> bool:
        return rounds < self.config.max_rounds
    
    def format_output(self, history: list[ExpertOpinion]) -> Outline:
        sequences = []
        characters = []
        world_notes = []
        
        granularity = self.config.granularity.value
        
        for opinion in history:
            if opinion.role == ExpertRole.MAIN:
                for suggestion in opinion.suggestions:
                    if granularity == "volume":
                        if suggestion.startswith("卷") or "卷" in suggestion:
                            sequences.append({
                                "name": suggestion,
                                "functions": [],
                                "description": opinion.content
                            })
                    elif granularity == "chapter":
                        if "章" in suggestion or "序列" in suggestion:
                            sequences.append({
                                "name": suggestion,
                                "functions": [],
                                "description": opinion.content
                            })
                    else:
                        sequences.append({
                            "name": suggestion,
                            "functions": [],
                            "description": opinion.content
                        })
        
        return Outline(
            sequences=sequences,
            characters=characters,
            world_notes=world_notes
        )
