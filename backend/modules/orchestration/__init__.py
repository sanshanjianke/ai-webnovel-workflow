from backend.core.protocols.meeting import (
    MeetingConfig,
    ExpertConfig,
    ExpertRole,
    Granularity,
    ConfigurableMeetingProtocol,
    ExpertOpinion
)
from backend.core.registry import get_module, MODULE_REGISTRY
from typing import Optional, Generator
import re


MENTION_RE = re.compile(r'@([^\s,，。！？…\n]{1,20})')


class MeetingEngine:
    """统一专家会议引擎 —— 支持 @提及点名、灵活退出"""

    def __init__(self, config: MeetingConfig):
        self.config = config
        self._experts = {}
        self._meeting_history: list[ExpertOpinion] = []
        self._round_idx = 0
        self._speech_count = 0
        self._protocol = ConfigurableMeetingProtocol(config)
        self._state = "idle"
        self._force_next_expert: Optional[str] = None
        self._stop_requested = False

    @property
    def current_round(self) -> int:
        return self._round_idx

    @property
    def speech_count(self) -> int:
        return self._speech_count

    @property
    def meeting_history(self) -> list[ExpertOpinion]:
        return self._meeting_history

    @property
    def state(self) -> str:
        return self._state

    @property
    def max_speeches(self) -> int:
        return getattr(self.config, 'max_speeches', 0) or self.config.max_rounds * len(self.config.experts)

    def get_expert(self, expert_id: str, role: ExpertRole = ExpertRole.MAIN):
        cache_key = f"{expert_id}_{role.value}"
        if cache_key not in self._experts:
            expert_cls = get_module("expert", expert_id)
            if expert_cls is None:
                raise ValueError(f"Expert '{expert_id}' not found in registry")
            expert = expert_cls(role=role, granularity=self.config.granularity)
            self._experts[cache_key] = expert
        return self._experts[cache_key]

    def _build_speaker_pool(self) -> list[tuple[str, ExpertRole]]:
        """构建发言者池，返回 [(expert_id, role), ...]"""
        speaking_order = self._protocol.get_speaking_order()
        return [(eid, ExpertRole(role)) for eid, role in speaking_order]

    def _should_exit(self) -> bool:
        if self._stop_requested:
            return True
        if self.max_speeches > 0 and self._speech_count >= self.max_speeches:
            return True
        return False

    def _detect_mention(self, text: str, speaker_pool: list[tuple[str, ExpertRole]], 
                        container_map: dict = None) -> Optional[str]:
        """检测专家输出中的 @提及，返回匹配的 expert_id（限定同容器内）"""
        names_to_id = {}
        for eid, role in speaker_pool:
            expert = self.get_expert(eid, role)
            names_to_id[expert.expert_type] = eid
            names_to_id[eid] = eid

        matches = MENTION_RE.findall(text)
        for name in matches:
            if name in names_to_id:
                return names_to_id[name]
        return None

    def _find_expert_in_pool(self, expert_id: str, pool: list[tuple[str, ExpertRole]]) -> Optional[tuple[str, ExpertRole]]:
        for eid, role in pool:
            if eid == expert_id:
                return (eid, role)
        return None

    def _handle_force_next(self, pool: list[tuple[str, ExpertRole]]) -> Optional[tuple[str, ExpertRole]]:
        """处理强制下一位发言人（来自@提及或用户调用）"""
        if self._force_next_expert:
            match = self._find_expert_in_pool(self._force_next_expert, pool)
            self._force_next_expert = None
            if match:
                return match
            # expert not in pool, try to add as supplement
            return (self._force_next_expert, ExpertRole.SUPPLEMENT)
        return None

    def run(
        self,
        context_input: dict,
        worldbook_text: str = "",
        rag_context: str = "",
        human_feedback=None,
        containers: dict = None
    ) -> Generator[dict, None, Optional[dict]]:
        self._meeting_history = []
        self._round_idx = 0
        self._speech_count = 0
        self._state = "running"
        self._force_next_expert = None
        self._stop_requested = False

        speaker_pool = self._build_speaker_pool()
        pool_idx = 0

        while not self._should_exit():
            # 判断下一位发言人
            forced = self._handle_force_next(speaker_pool)
            if forced:
                expert_id, role = forced
            else:
                expert_id, role = speaker_pool[pool_idx % len(speaker_pool)]
                pool_idx += 1

            # 轮次播报
            if pool_idx % len(speaker_pool) == 1:
                self._round_idx += 1
                yield {
                    "type": "round_start",
                    "round": self._round_idx,
                    "speech_count": self._speech_count,
                    "max_speeches": self.max_speeches,
                    "meeting_name": self.config.meeting_name
                }

            expert_config = self._get_expert_config(expert_id, role)
            expert = self.get_expert(expert_id, role)

            context = {
                "vision": context_input,
                "worldbook": worldbook_text,
                "rag": rag_context,
                "round": self._round_idx,
                "speech_count": self._speech_count,
                "history": self._meeting_history.copy()
            }

            self._inject_history_context(context)

            if expert_config and expert_config.custom_prompt:
                context["custom_prompt"] = expert_config.custom_prompt

            yield {
                "type": "expert_start",
                "expert_id": expert_id,
                "expert_type": expert.expert_type,
                "role": role.value,
                "round": self._round_idx,
                "speech_count": self._speech_count
            }

            opinion = expert.speak(None, context)
            opinion.role = role
            self._meeting_history.append(opinion)
            self._speech_count += 1

            # 检测 @提及
            mention_target = self._detect_mention(opinion.content, speaker_pool, containers)

            yield {
                "type": "expert_speak",
                "expert_id": opinion.expert_id,
                "expert_type": opinion.expert_type,
                "role": opinion.role.value,
                "content": opinion.content,
                "suggestions": opinion.suggestions,
                "speech_count": self._speech_count,
                "mention": mention_target
            }

            # @提及点名
            if mention_target:
                self._force_next_expert = mention_target
                yield {"type": "mention_detected", "from": opinion.expert_type, "to": mention_target}

            # 半自动：等用户反馈
            if self.config.collaboration_mode in ("semi_auto", "manual") and human_feedback:
                yield {"type": "waiting_user", "speech_count": self._speech_count}
                feedback = human_feedback()
                if feedback:
                    action = feedback.get("action", "")
                    if action == "stop":
                        self._stop_requested = True
                        self._state = "stopped"
                        output = self._format_output()
                        yield {"type": "output_ready", "output": output, "speech_count": self._speech_count, "reason": "user_stopped"}
                        return output
                    elif action == "approve":
                        yield {"type": "meeting_complete", "reason": "user_approved"}
                        output = self._format_output()
                        self._state = "completed"
                        yield {"type": "output_ready", "output": output, "speech_count": self._speech_count}
                        return output
                    elif action == "modify":
                        context["user_feedback"] = feedback.get("message", "")
                    elif action == "call_expert":
                        called = feedback.get("expert_id", "")
                        if called:
                            self._force_next_expert = called
                            yield {"type": "user_call_expert", "expert_id": called}
                    elif action == "restart":
                        self._meeting_history = []
                        self._speech_count = 0
                        self._round_idx = 0
                        self._force_next_expert = None
                        pool_idx = 0
                        yield {"type": "meeting_restarted"}

        output = self._format_output()
        self._state = "completed"
        yield {"type": "output_ready", "output": output, "speech_count": self._speech_count, "rounds": self._round_idx}
        return output

    def _get_expert_config(self, expert_id: str, role: ExpertRole) -> Optional[ExpertConfig]:
        for ec in self.config.experts:
            if ec.expert_id == expert_id and ec.role == role:
                return ec
        for ec in self.config.experts:
            if ec.expert_id == expert_id:
                return ec
        return None

    def _inject_history_context(self, context: dict):
        for op in reversed(self._meeting_history):
            if op.expert_type in ("资深作者", "剧情架构师", "章节拆分师") and "author_proposal" not in context:
                context["author_proposal"] = op.content
        for op in reversed(self._meeting_history):
            if op.expert_type == "读者代表" and "reader_opinion" not in context:
                context["reader_opinion"] = op.content
        for op in reversed(self._meeting_history):
            if op.expert_type in ("网络编辑",) and "editor_opinion" not in context:
                context["editor_opinion"] = op.content
        for op in reversed(self._meeting_history):
            if op.expert_type in ("剧情架构师",) and "architect_proposal" not in context:
                context["architect_proposal"] = op.content

    def _format_output(self) -> dict:
        outline = self._protocol.format_output(self._meeting_history)

        meeting_summary = "\n\n---\n\n".join([
            f"### {op.expert_type} ({op.role.value})\n\n{op.content}"
            for op in self._meeting_history
        ])

        suggestions = []
        for op in self._meeting_history:
            suggestions.extend(op.suggestions)

        return {
            "meeting_name": self.config.meeting_name,
            "granularity": self.config.granularity.value,
            "sequences": outline.sequences,
            "characters": outline.characters,
            "world_notes": outline.world_notes,
            "meeting_summary": meeting_summary,
            "suggestions": suggestions,
            "total_rounds": self._round_idx,
            "total_speeches": self._speech_count
        }


# ── 预置模板 ────────────────────────────────────────────────

PRESET_CONFIGS = {
    "quick_review": {
        "meeting_name": "方案审核",
        "granularity": "chapter",
        "experts": [
            {"expert_id": "web_editor_v1", "role": "main"},
        ],
        "collaboration_mode": "full_auto",
        "max_speeches": 3
    },
    "volume_planning": {
        "meeting_name": "卷纲编排",
        "granularity": "volume",
        "experts": [
            {"expert_id": "senior_author_v1", "role": "main"},
            {"expert_id": "reader_representative_v1", "role": "review"},
            {"expert_id": "senior_author_v1", "role": "supplement"},
        ],
        "collaboration_mode": "semi_auto",
        "max_speeches": 9
    },
    "chapter_design": {
        "meeting_name": "章纲设计",
        "granularity": "chapter",
        "experts": [
            {"expert_id": "plot_architect_v1", "role": "main"},
            {"expert_id": "web_editor_v1", "role": "review"},
            {"expert_id": "character_designer_v1", "role": "supplement"},
        ],
        "collaboration_mode": "semi_auto",
        "max_speeches": 9
    }
}
