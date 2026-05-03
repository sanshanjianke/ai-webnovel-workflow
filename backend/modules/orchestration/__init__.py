from backend.core.protocols.meeting import (
    MeetingConfig,
    ExpertConfig,
    ContainerConfig,
    ExpertRole,
    Granularity,
    ConfigurableMeetingProtocol,
    ExpertOpinion
)
from backend.core.registry import get_module, MODULE_REGISTRY
from typing import Optional, Generator
import re
import asyncio


MENTION_RE = re.compile(r'@([^\s,，。！？…\n]{1,20})')


class MeetingEngine:
    """统一专家会议引擎 —— 支持 @提及点名、容器、群聊/并行/循环/总结"""

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

        # 容器状态机
        self._container_map: dict[str, ContainerConfig] = {}
        self._expert_containers: dict[str, str] = {}  # expert_id(unique) -> container_id
        self._container_histories: dict[str, list[ExpertOpinion]] = {}
        self._container_rounds: dict[str, int] = {}
        self._container_exit_requested: set = set()

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

    def _init_containers(self):
        """初始化容器索引"""
        self._container_map.clear()
        self._expert_containers.clear()
        self._container_histories.clear()
        self._container_rounds.clear()
        self._container_exit_requested.clear()

        for c in self.config.containers:
            self._container_map[c.container_id] = c
            self._container_histories[c.container_id] = []
            self._container_rounds[c.container_id] = 0
            for child_id in c.children:
                self._expert_containers[child_id] = c.container_id

    def _get_expert_unique_id(self, expert_id: str, role: ExpertRole) -> str:
        return f"{expert_id}_{role.value}"

    def get_expert(self, expert_id: str, role: ExpertRole = ExpertRole.MAIN):
        cache_key = self._get_expert_unique_id(expert_id, role)
        if cache_key not in self._experts:
            expert_cls = get_module("expert", expert_id)
            if expert_cls is None:
                raise ValueError(f"Expert '{expert_id}' not found in registry")
            expert = expert_cls(role=role, granularity=self.config.granularity)
            self._experts[cache_key] = expert
        return self._experts[cache_key]

    def _build_speaker_pool(self) -> list[tuple[str, ExpertRole, Optional[str]]]:
        """构建发言者池，返回 [(expert_id, role, container_id), ...]"""
        speaking_order = self._protocol.get_speaking_order()
        result = []
        for eid, role_str in speaking_order:
            container_id = self._expert_containers.get(self._get_expert_unique_id(eid, ExpertRole(role_str)))
            # also check by expert_id alone (for experts registered only by id)
            if not container_id:
                for key, cid in self._expert_containers.items():
                    if key.startswith(eid):
                        container_id = cid
                        break
            result.append((eid, ExpertRole(role_str), container_id))
        return result

    def _should_exit(self) -> bool:
        if self._stop_requested:
            return True
        if self.max_speeches > 0 and self._speech_count >= self.max_speeches:
            return True
        return False

    def _detect_mention(self, text: str, container_id: Optional[str] = None) -> Optional[str]:
        """检测专家输出中的 @提及，若 mention_isolation 则限定同容器内"""
        names_to_id = {}
        all_experts = set()
        for ec in self.config.experts:
            expert = self.get_expert(ec.expert_id, ec.role)
            names_to_id[expert.expert_type] = ec.expert_id
            names_to_id[ec.expert_id] = ec.expert_id
            all_experts.add(ec.expert_id)

        matches = MENTION_RE.findall(text)
        for name in matches:
            if name not in names_to_id:
                continue
            target_id = names_to_id[name]
            if container_id:
                container = self._container_map.get(container_id)
                if container and container.mention_isolation:
                    # check if target is in same container
                    target_container = self._expert_containers.get(
                        self._get_expert_unique_id(target_id, ExpertRole.MAIN))
                    if not target_container:
                        # try any role
                        for key, cid in self._expert_containers.items():
                            if key.startswith(target_id):
                                target_container = cid
                                break
                    if target_container != container_id:
                        continue
            return target_id
        return None

    def _find_expert_in_pool(self, expert_id: str, pool: list) -> Optional[tuple]:
        for item in pool:
            eid, role, cid = item
            if eid == expert_id:
                return item
        return None

    def _handle_force_next(self, pool: list) -> Optional[tuple]:
        if self._force_next_expert:
            match = self._find_expert_in_pool(self._force_next_expert, pool)
            self._force_next_expert = None
            if match:
                return match
            return (self._force_next_expert, ExpertRole.SUPPLEMENT, None)
        return None

    def _get_container_speaker_pool(self, container: ContainerConfig) -> list[tuple[str, ExpertRole]]:
        """构建容器内部的发言者池"""
        pool = []

        # Build order from container edges
        edge_targets = {}
        all_children = set(container.children)
        in_degree = {c: 0 for c in all_children}
        out_edges = {c: [] for c in all_children}

        for edge in container.edges:
            src, tgt = edge.get("source"), edge.get("target")
            if src in all_children and tgt in all_children:
                in_degree[tgt] = in_degree.get(tgt, 0) + 1
                out_edges[src] = out_edges.get(src, []) + [tgt]

        # Topological sort
        queue = [c for c in all_children if in_degree.get(c, 0) == 0]
        order = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for tgt in out_edges.get(current, []):
                in_degree[tgt] -= 1
                if in_degree[tgt] == 0:
                    queue.append(tgt)

        # If edges don't cover all, add remaining
        for c in all_children:
            if c not in order:
                order.append(c)

        # Map child ids to expert configs
        for child_id in order:
            for ec in self.config.experts:
                uid = self._get_expert_unique_id(ec.expert_id, ec.role)
                if uid == child_id or ec.expert_id == child_id:
                    pool.append((ec.expert_id, ec.role))
                    break

        return pool

    def run(
        self,
        context_input: dict,
        worldbook_text: str = "",
        rag_context: str = "",
        human_feedback=None,
    ) -> Generator[dict, None, Optional[dict]]:
        self._meeting_history = []
        self._round_idx = 0
        self._speech_count = 0
        self._state = "running"
        self._force_next_expert = None
        self._stop_requested = False
        self._init_containers()

        speaker_pool = self._build_speaker_pool()
        pool_idx = 0

        while not self._should_exit():
            forced = self._handle_force_next(speaker_pool)
            if forced:
                expert_id, role, container_id = forced
            else:
                expert_id, role, container_id = speaker_pool[pool_idx % len(speaker_pool)]
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

            # 容器上下文注入
            container_context = ""
            if container_id:
                container = self._container_map.get(container_id)
                if container:
                    container_context = f"\n[你在容器「{container.name}」中，当前模式: {container.chat_mode}]"
                    # 注入容器内历史
                    container_hist = self._container_histories.get(container_id, [])
                    if container.chat_mode == "group" and container_hist:
                        hist_text = "\n".join([
                            f"[{op.expert_type}] {op.content[:200]}..."
                            for op in container_hist[-5:]
                        ])
                        container_context += f"\n\n容器内已有讨论:\n{hist_text}"

            context = {
                "vision": context_input,
                "worldbook": worldbook_text,
                "rag": rag_context,
                "round": self._round_idx,
                "speech_count": self._speech_count,
                "history": self._meeting_history.copy(),
                "container_context": container_context,
                "container_id": container_id,
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
                "speech_count": self._speech_count,
                "container_id": container_id,
            }

            opinion = expert.speak(None, context)
            opinion.role = role
            self._meeting_history.append(opinion)
            self._speech_count += 1

            # 记录到容器历史
            if container_id:
                self._container_histories.setdefault(container_id, []).append(opinion)

            # 检测 @提及（限定容器内）
            mention_target = self._detect_mention(opinion.content, container_id)

            yield {
                "type": "expert_speak",
                "expert_id": opinion.expert_id,
                "expert_type": opinion.expert_type,
                "role": opinion.role.value,
                "content": opinion.content,
                "suggestions": opinion.suggestions,
                "speech_count": self._speech_count,
                "mention": mention_target,
                "container_id": container_id,
            }

            if mention_target:
                self._force_next_expert = mention_target
                yield {"type": "mention_detected", "from": opinion.expert_type, "to": mention_target}

            # 容器循环检查：容器内专家完成一轮发言
            if container_id:
                container = self._container_map.get(container_id)
                if container and container.repeat > 1:
                    container_pool = self._get_container_speaker_pool(container)
                    container_hist = self._container_histories.get(container_id, [])
                    container_rounds = self._container_rounds.get(container_id, 0)
                    if container_hist and len(container_hist) % len(container_pool) == 0:
                        self._container_rounds[container_id] = container_rounds + 1
                        # 容器内一轮完成，触发总结师
                        if container.summarizer == "every_round":
                            yield self._generate_summary(container_id, container)
                        if self._container_rounds[container_id] >= container.repeat:
                            self._container_exit_requested.add(container_id)

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
                        self._container_histories.clear()
                        self._container_rounds.clear()
                        self._container_exit_requested.clear()
                        pool_idx = 0
                        yield {"type": "meeting_restarted"}

        output = self._format_output()
        self._state = "completed"
        yield {"type": "output_ready", "output": output, "speech_count": self._speech_count, "rounds": self._round_idx}
        return output

    def _generate_summary(self, container_id: str, container: ContainerConfig) -> dict:
        """容器内总结师发言"""
        container_hist = self._container_histories.get(container_id, [])
        if not container_hist:
            return {"type": "summarizer", "container_id": container_id, "content": ""}

        llm = self._get_llm()
        hist_text = "\n\n".join([
            f"### {op.expert_type} ({op.role.value})\n{op.content}"
            for op in container_hist[-10:]
        ])

        prompt = f"""你是讨论总结师。请总结以下专家讨论，提炼共识、标注分歧、保持格式规范。

讨论内容：
{hist_text}

请简洁总结（200字以内）：
1. 共识点
2. 分歧点
3. 下一步建议"""

        content = llm.invoke(prompt, temperature=0.5)
        return {
            "type": "summarizer",
            "container_id": container_id,
            "container_name": container.name,
            "content": content
        }

    def _get_llm(self):
        from backend.core.config import get_config
        config = get_config()
        llm_cls = get_module("llm", config.llm.primary)
        return llm_cls()

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
