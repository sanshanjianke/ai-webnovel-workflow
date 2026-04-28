import json
from typing import Callable, Optional, Generator
from datetime import datetime
from pathlib import Path

from backend.core.protocols.l2 import Outline
from backend.core.protocols.expert import ExpertOpinion
from backend.core.protocols.worldbook import BaseWorldBook
from backend.core.protocols.rag import BaseRAGAgent
from backend.core.config import get_config
from backend.core.registry import get_module


class ExpertMeetingL2:
    def __init__(
        self,
        protocol_id: str = "plot_driven",
        collaboration_mode: str = "semi_auto",
        max_rounds: int = 3
    ):
        self.protocol_id = protocol_id
        self.collaboration_mode = collaboration_mode
        self.max_rounds = max_rounds
        
        self._protocol = None
        self._experts = {}
        self._meeting_history = []
        self._current_round = 0
        self._consensus = 0.0
    
    @property
    def protocol(self):
        if self._protocol is None:
            self._protocol = get_module("meeting_protocol", self.protocol_id)()
        return self._protocol
    
    def get_expert(self, expert_type: str):
        if expert_type not in self._experts:
            expert_map = {
                "architect": "plot_architect_v1",
                "editor": "web_editor_v1",
                "character": "character_designer_v1"
            }
            expert_cls = get_module("expert", expert_map.get(expert_type, expert_type))
            self._experts[expert_type] = expert_cls()
        return self._experts[expert_type]
    
    def generate_outline(
        self,
        vision: dict,
        world_book: BaseWorldBook,
        rag_history: Optional[BaseRAGAgent] = None,
        rag_technique: Optional[BaseRAGAgent] = None,
        human_feedback: Optional[Callable] = None
    ) -> Generator[dict, None, Outline]:
        self._meeting_history = []
        self._current_round = 0
        self._consensus = 0.0
        
        worldbook_entries = world_book.list_all_entries()
        worldbook_text = "\n".join([
            f"- {e.keys[0]}: {e.content[:100]}..."
            for e in worldbook_entries[:10]
        ]) if worldbook_entries else "暂无条目"
        
        while self.protocol.should_continue(self._current_round, self._consensus):
            self._current_round += 1
            
            yield {
                "type": "round_start",
                "round": self._current_round,
                "max_rounds": self.max_rounds
            }
            
            speaking_order = self.protocol.get_speaking_order({"vision": vision})
            
            context = {
                "vision": vision,
                "worldbook": worldbook_text,
                "round": self._current_round
            }
            
            for expert_type, speak_type in speaking_order:
                expert = self.get_expert(expert_type)
                
                if expert_type == "architect" and self._meeting_history:
                    context["architect_proposal"] = self._meeting_history[-1].content
                
                if expert_type == "editor" and self._meeting_history:
                    for op in reversed(self._meeting_history):
                        if op.expert_type == "剧情架构师":
                            context["architect_proposal"] = op.content
                            break
                
                if expert_type == "character" and len(self._meeting_history) >= 2:
                    for op in reversed(self._meeting_history):
                        if op.expert_type == "网络编辑":
                            context["editor_opinion"] = op.content
                            break
                    for op in reversed(self._meeting_history):
                        if op.expert_type == "剧情架构师":
                            context["architect_proposal"] = op.content
                            break
                
                yield {
                    "type": "expert_start",
                    "expert_id": expert.expert_id,
                    "expert_type": expert.expert_type,
                    "speak_type": speak_type
                }
                
                opinion = expert.speak(None, context)
                self._meeting_history.append(opinion)
                
                yield {
                    "type": "expert_speak",
                    "expert_id": opinion.expert_id,
                    "expert_type": opinion.expert_type,
                    "content": opinion.content,
                    "suggestions": opinion.suggestions
                }
                
                if self.collaboration_mode == "semi_auto" and human_feedback:
                    yield {"type": "waiting_user"}
                    feedback = human_feedback()
                    if feedback:
                        if feedback.get("action") == "approve":
                            self._consensus = 1.0
                        elif feedback.get("action") == "modify":
                            context["user_feedback"] = feedback.get("message", "")
                        elif feedback.get("action") == "reject":
                            yield {"type": "user_reject", "message": feedback.get("message", "")}
                            break
            
            if self.collaboration_mode == "manual" and human_feedback:
                yield {"type": "waiting_user"}
                feedback = human_feedback()
                if feedback and feedback.get("action") == "approve":
                    self._consensus = 1.0
        
        outline = self.protocol.format_output(self._meeting_history)
        
        yield {
            "type": "outline_ready",
            "outline": outline.model_dump(),
            "rounds": self._current_round,
            "consensus": self._consensus
        }
        
        return outline
    
    def get_meeting_history(self) -> list[ExpertOpinion]:
        return self._meeting_history
