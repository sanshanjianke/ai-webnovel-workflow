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


class ContainerConfig(BaseModel):
    container_id: str
    name: str = "容器"
    concurrency: Literal["serial", "parallel"] = "serial"
    speaking_mode: Literal["ordered", "mention_driven"] = "ordered"
    context_layers: Optional[int] = None
    context_tokens: Optional[int] = None
    repeat: int = 1
    interrupt_mode: Optional[str] = None  # None=不覆盖, auto/every_n_msgs/every_n_tokens/on_mention
    interrupt_threshold: int = 1
    exit_mode: Literal["manual", "consensus", "ratio", "gatekeeper"] = "manual"
    exit_ratio: float = 0.6
    exit_gatekeeper: Optional[str] = None
    exit_max_speeches: int = 20
    worldbook_bindings: list[str] = []
    rag_bindings: list[str] = []
    children: list[str] = []
    edges: list[dict] = []


class ExpertConfig(BaseModel):
    expert_id: str
    role: ExpertRole = ExpertRole.MAIN
    custom_prompt: Optional[str] = None
    container_id: Optional[str] = None
    interrupt_mode: Literal["auto", "every_n_msgs", "every_n_tokens", "on_mention"] = "every_n_msgs"
    interrupt_threshold: int = 1  # N messages or ~N tokens


class MeetingConfig(BaseModel):
    meeting_name: str = "专家会议"
    granularity: Granularity = Granularity.CHAPTER
    experts: list[ExpertConfig]
    containers: list[ContainerConfig] = []
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
