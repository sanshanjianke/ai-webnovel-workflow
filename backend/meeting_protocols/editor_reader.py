from typing import Optional
from backend.core.protocols.meeting import (
    BaseMeetingProtocol, 
    ExpertOpinion, 
    Outline,
    ExpertRole,
    Granularity
)
from backend.core.registry import register_module


@register_module("meeting_protocol")
class EditorReaderDriven(BaseMeetingProtocol):
    """L1.5 两专家会议协议 - 卷纲编排"""
    
    @property
    def protocol_id(self) -> str:
        return "editor_reader"
    
    def get_speaking_order(self, context: dict = None) -> list[tuple[str, str]]:
        return [
            ("senior_author_v1", "main"),
            ("reader_representative_v1", "review"),
        ]
    
    def should_continue(self, rounds: int, consensus: float) -> bool:
        return rounds < 3
    
    def format_output(self, history: list[ExpertOpinion]) -> Outline:
        sequences = []
        characters = []
        world_notes = []
        
        for opinion in history:
            if opinion.expert_type == "资深作者":
                for suggestion in opinion.suggestions:
                    if suggestion.startswith("卷") or "卷" in suggestion:
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
