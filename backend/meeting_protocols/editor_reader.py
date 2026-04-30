from typing import Optional
from backend.core.protocols.meeting import BaseMeetingProtocol, ExpertOpinion, Outline
from backend.core.registry import register_module


@register_module("meeting_protocol")
class EditorReaderDriven(BaseMeetingProtocol):
    @property
    def protocol_id(self) -> str:
        return "editor_reader"
    
    def get_speaking_order(self, context: dict = None) -> list[tuple[str, str]]:
        return [
            ("author", "main"),
            ("reader", "review"),
            ("author", "supplement"),
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
                    if suggestion.startswith("卷"):
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
