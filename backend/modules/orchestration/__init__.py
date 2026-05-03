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
import json


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
        """检测 @提及。若在容器内，仅匹配同容器专家。"""
        names_to_id = {}
        for ec in self.config.experts:
            expert = self.get_expert(ec.expert_id, ec.role)
            names_to_id[expert.expert_type] = ec.expert_id
            names_to_id[ec.expert_id] = ec.expert_id

        matches = MENTION_RE.findall(text)
        for name in matches:
            if name not in names_to_id:
                continue
            target_id = names_to_id[name]
            if container_id:
                target_container = self._expert_containers.get(
                    self._get_expert_unique_id(target_id, ExpertRole.MAIN))
                if not target_container:
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

        # 提及驱动模式状态
        mention_driven_containers = {
            cid: c for cid, c in self._container_map.items()
            if c.speaking_mode == "mention_driven"
        }
        container_last_active: dict[str, dict[str, int]] = {
            cid: {} for cid in mention_driven_containers
        }

        while not self._should_exit():
            # 判断下一位发言人
            forced = self._handle_force_next(speaker_pool)
            if forced:
                expert_id, role, container_id = forced
            else:
                expert_id, role, container_id = speaker_pool[pool_idx % len(speaker_pool)]
                pool_idx += 1

            # 提及驱动模式下，若无 @提及且非强制，改由引擎选择下一位
            if container_id and container_id in mention_driven_containers and not forced:
                container = self._container_map[container_id]
                expert_id, role = self._pick_mention_driven_speaker(
                    container, container_last_active.get(container_id, {}))
                # 检查退出条件
                exit_check = self._check_mention_driven_exit(container_id, container)
                if exit_check:
                    yield exit_check
                    break

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
                    container_context = f"\n[你在容器「{container.name}」中，并发模式: {container.concurrency}]"
                    container_hist = self._container_histories.get(container_id, [])
                    if container_hist:
                        recent = self._apply_context_depth(container_hist, container)
                        hist_text = "\n".join([
                            f"[{op.expert_type}] {op.content[:200]}..."
                            for op in recent[-10:]
                        ])
                        container_context += f"\n\n容器内讨论历史:\n{hist_text}"

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

            opinion = ExpertOpinion(expert_id=expert_id, expert_type=expert.expert_type, role=role, content="")
            full_content = ""
            for chunk in expert.speak_stream(None, context):
                if isinstance(chunk, tuple) and chunk[0] == "__done__":
                    opinion = chunk[1]
                elif isinstance(chunk, tuple):
                    chunk_type, chunk_content = chunk
                    if chunk_type == "content":
                        full_content += chunk_content
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
                    if container_hist and len(container_hist) % len(container_pool) == 0:
                        self._container_rounds[container_id] = container_rounds.get(container_id, 0) + 1
                        if self._container_rounds[container_id] >= container.repeat:
                            self._container_exit_requested.add(container_id)

            # 中断判定：根据专家/容器配置决定是否暂停等用户
            interrupt_mode = "every_n_msgs"
            interrupt_threshold = 1
            if expert_config and expert_config.interrupt_mode:
                interrupt_mode = expert_config.interrupt_mode
                interrupt_threshold = expert_config.interrupt_threshold or 1
            if container_id:
                container = self._container_map.get(container_id)
                if container and container.interrupt_mode:
                    interrupt_mode = container.interrupt_mode
                    interrupt_threshold = container.interrupt_threshold or 1

            should_pause = False
            if interrupt_mode == "auto":
                should_pause = False
            elif interrupt_mode == "on_mention":
                should_pause = "@主编" in opinion.content or "@用户" in opinion.content
            elif interrupt_mode == "every_n_msgs":
                # 计数此容器内已连续发言次数
                key = f"{container_id or 'solo'}_msgs"
                count = getattr(self, '_interrupt_counts', {}).get(key, 0) + 1
                if not hasattr(self, '_interrupt_counts'): self._interrupt_counts = {}
                self._interrupt_counts[key] = count
                should_pause = count >= interrupt_threshold
                if should_pause:
                    self._interrupt_counts[key] = 0
            elif interrupt_mode == "every_n_tokens":
                key = f"{container_id or 'solo'}_tokens"
                count = getattr(self, '_interrupt_token_counts', {}).get(key, 0) + len(opinion.content)
                if not hasattr(self, '_interrupt_token_counts'): self._interrupt_token_counts = {}
                self._interrupt_token_counts[key] = count
                should_pause = count >= interrupt_threshold
                if should_pause:
                    self._interrupt_token_counts[key] = 0

            if should_pause and human_feedback:
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

    def _apply_context_depth(self, history: list[ExpertOpinion], container: ContainerConfig) -> list[ExpertOpinion]:
        """根据容器的 context_layers / context_tokens 截断历史"""
        layers = container.context_layers
        tokens = container.context_tokens
        if not layers and not tokens:
            return history

        pool = self._get_container_speaker_pool(container)
        pool_size = len(pool) if pool else 3

        result = history[:]
        if layers:
            cutoff = layers * pool_size
            if len(result) > cutoff:
                result = result[-cutoff:]
        if tokens:
            total = 0
            for i in range(len(result) - 1, -1, -1):
                total += len(result[i].content)
                if total > tokens:
                    result = result[i + 1:]
                    break
        return result

    def _pick_mention_driven_speaker(self, container: ContainerConfig, last_active: dict) -> tuple:
        """提及驱动模式：选择下一位发言人。优先最近 @提及目标，否则选最不活跃的。"""
        if self._force_next_expert:
            eid = self._force_next_expert
            self._force_next_expert = None
            for ec in self.config.experts:
                if ec.expert_id == eid and ec.container_id == container.container_id:
                    return (eid, ec.role)
            return (eid, ExpertRole.MAIN)

        pool = self._get_container_speaker_pool(container)
        if not pool:
            return ("web_editor_v1", ExpertRole.MAIN)

        # 选最不活跃的专家
        now = self._speech_count
        best = pool[0]
        best_score = last_active.get(best[0], -1)
        for eid, role in pool:
            score = last_active.get(eid, -1)
            if score < best_score:
                best = (eid, role)
                best_score = score
        return best

    def _check_mention_driven_exit(self, container_id: str, container: ContainerConfig) -> Optional[dict]:
        """检查提及驱动模式的退出条件"""
        mode = container.exit_mode
        hist = self._container_histories.get(container_id, [])

        # 最大发言兜底
        if container.exit_max_speeches > 0:
            container_speeches = sum(1 for op in hist if op.expert_id in [
                eid for eid, _ in self._get_container_speaker_pool(container)])
            if container_speeches >= container.exit_max_speeches:
                return {"type": "exit_trigger", "reason": "max_speeches", "container_id": container_id}

        if mode == "manual":
            return None

        # 检测最近的发言是否表达了结束意愿
        recent = hist[-3:] if len(hist) >= 3 else hist
        exit_keywords = ["会议结束", "讨论已充分", "可以结束", "没有更多意见", "同意结束", "到此为止"]
        agree_count = 0
        pool_size = max(len(self._get_container_speaker_pool(container)), 1)

        for op in recent:
            if any(kw in op.content for kw in exit_keywords):
                agree_count += 1

        if mode == "consensus" and agree_count >= pool_size:
            return {"type": "exit_trigger", "reason": "consensus", "container_id": container_id}
        if mode == "ratio" and pool_size > 0 and agree_count / pool_size >= container.exit_ratio:
            return {"type": "exit_trigger", "reason": "ratio", "container_id": container_id,
                    "ratio": agree_count / pool_size}
        if mode == "gatekeeper" and container.exit_gatekeeper:
            for op in recent:
                if op.expert_id == container.exit_gatekeeper and any(
                        kw in op.content for kw in exit_keywords):
                    return {"type": "exit_trigger", "reason": "gatekeeper", "container_id": container_id,
                            "gatekeeper": container.exit_gatekeeper}

        return None

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

    def _inject_upstream_context(self, ctx, upstream_outputs, node_map, input_text):
        for up_nid, up_content in upstream_outputs:
            up_experts = node_map.get(up_nid, [])
            if up_experts:
                up_eid = up_experts[0].get("expert_id", "")
                if up_eid in ("senior_author_v1", "plot_architect_v1"):
                    ctx["author_proposal"] = up_content
                elif up_eid == "reader_representative_v1":
                    ctx["reader_opinion"] = up_content
                elif up_eid == "web_editor_v1":
                    ctx["editor_opinion"] = up_content
        if input_text and input_text.strip():
            ctx["custom_prompt"] = (ctx.get("custom_prompt", "") + f"\n\n上游节点产出：\n{input_text}").strip()

    def run_pipeline(
        self,
        context_input: dict,
        worldbook_text: str = "",
        rag_context: str = "",
        human_feedback=None,
    ) -> Generator[dict, None, Optional[dict]]:
        """管道模式：按 DAG 拓扑顺序逐节点处理，数据沿边流动"""
        self._state = "running"
        self._speech_count = 0
        self._init_containers()

        # 构建节点图：vue_node_id → expert_id 映射
        vue_to_expert: dict[str, str] = {}
        node_map: dict[str, list[dict]] = {}
        for ec in self.config.experts:
            vue_id = ec.node_id or ec.expert_id
            key = ec.container_id or vue_id
            if key not in node_map:
                node_map[key] = []
            node_map[key].append({"expert_id": ec.expert_id, "role": ec.role.value if hasattr(ec.role, 'value') else ec.role, "custom_prompt": ec.custom_prompt})
            vue_to_expert[ec.node_id or ec.expert_id] = ec.expert_id

        # 容器节点也加入映射
        for c in self.config.containers:
            vue_to_expert[c.container_id] = c.container_id

        # 用 config.edges 建 DAG，映射 vue node ID → 引擎节点 key
        all_node_ids = set(node_map.keys())
        in_degree: dict[str, int] = {}
        out_edges: dict[str, list[str]] = {}

        for nid in all_node_ids:
            in_degree.setdefault(nid, 0)
            out_edges.setdefault(nid, [])

        for edge in self.config.edges:
            src_vue = edge.get("source", "")
            tgt_vue = edge.get("target", "")
            # 映射到引擎 key
            src = None
            tgt = None
            for ec in self.config.experts:
                if ec.node_id == src_vue:
                    src = ec.container_id or src_vue
                if ec.node_id == tgt_vue:
                    tgt = ec.container_id or tgt_vue
            # 容器节点
            for c in self.config.containers:
                if c.container_id == src_vue:
                    src = c.container_id
                if c.container_id == tgt_vue:
                    tgt = c.container_id
            if src and tgt and src != tgt and src in all_node_ids and tgt in all_node_ids:
                in_degree[tgt] = in_degree.get(tgt, 0) + 1
                out_edges[src].append(tgt)

        # 拓扑排序（层级分组）
        queue = [nid for nid in all_node_ids if in_degree.get(nid, 0) == 0]
        topo_levels = []
        while queue:
            level = list(queue)
            queue.clear()
            topo_levels.append(level)
            for nid in level:
                for tgt in out_edges.get(nid, []):
                    in_degree[tgt] -= 1
                    if in_degree[tgt] == 0:
                        queue.append(tgt)

        # 节点输出缓存
        node_outputs: dict[str, str] = {}

        yield {"type": "pipeline_start", "levels": len(topo_levels), "nodes": len(all_node_ids)}

        for level_idx, level in enumerate(topo_levels):
            yield {"type": "level_start", "level": level_idx + 1, "total_levels": len(topo_levels), "nodes": level}

            for nid in level:
                # 收集上游输入并映射到正确的上下文字段
                upstream_outputs = []
                for other_nid, targets in out_edges.items():
                    if nid in targets and other_nid in node_outputs:
                        upstream_outputs.append((other_nid, node_outputs[other_nid]))

                if not upstream_outputs:
                    input_text = json.dumps(context_input, ensure_ascii=False, indent=2)[:5000]
                else:
                    input_text = "\n\n---\n\n".join(f"[{nid}]:\n{content}" for nid, content in upstream_outputs)

                # 判断是容器还是单独专家
                is_container = nid in self._container_map
                if is_container:
                    container = self._container_map[nid]
                    pool = self._get_container_speaker_pool(container)
                    container_history = []
                    output_parts = []
                    for (eid, role) in pool:
                        expert = self.get_expert(eid, role)
                        ctx = {
                            "vision": context_input,
                            "worldbook": worldbook_text,
                            "rag": rag_context,
                            "history": [ExpertOpinion(expert_id=op[0], expert_type=op[0], role=ExpertRole(op[1]), content=op[2]) for op in container_history],
                            "custom_prompt": ""
                        }
                        self._inject_upstream_context(ctx, upstream_outputs, node_map, input_text)
                        self._inject_history_context(ctx)
                        self._speech_count += 1
                        yield {"type": "expert_start", "expert_id": eid, "expert_type": expert.expert_type, "role": role.value, "container_id": nid, "level": level_idx + 1}
                        full_content = ""
                        for chunk in expert.speak_stream(None, ctx):
                            if isinstance(chunk, tuple) and chunk[0] == "__done__":
                                opinion = chunk[1]
                            elif isinstance(chunk, tuple):
                                chunk_type, chunk_content = chunk
                                yield {"type": "expert_chunk", "chunk_type": chunk_type, "content": chunk_content, "expert_id": eid, "container_id": nid, "level": level_idx + 1}
                                if chunk_type == "content":
                                    full_content += chunk_content
                        opinion.role = role
                        container_history.append((eid, role.value, full_content))
                        output_parts.append(f"### {expert.expert_type}\n{full_content}")
                        yield {"type": "expert_speak", "expert_id": eid, "expert_type": expert.expert_type, "role": role.value, "content": full_content, "suggestions": opinion.suggestions, "container_id": nid, "level": level_idx + 1}
                    node_outputs[nid] = "\n\n".join(output_parts)
                else:
                    # 单独专家节点
                    experts = node_map.get(nid, [])
                    if experts:
                        exp = experts[0]
                        expert = self.get_expert(exp["expert_id"], ExpertRole(exp["role"]))
                        ctx = {
                            "vision": context_input,
                            "worldbook": worldbook_text,
                            "rag": rag_context,
                            "history": [],
                            "custom_prompt": (exp.get("custom_prompt") or "")
                        }
                        self._inject_upstream_context(ctx, upstream_outputs, node_map, input_text)
                        self._speech_count += 1
                        yield {"type": "expert_start", "expert_id": exp["expert_id"], "expert_type": expert.expert_type, "role": exp["role"], "node_id": nid, "level": level_idx + 1}
                        full_content = ""
                        for chunk in expert.speak_stream(None, ctx):
                            if isinstance(chunk, tuple) and chunk[0] == "__done__":
                                opinion = chunk[1]
                            elif isinstance(chunk, tuple):
                                chunk_type, chunk_content = chunk
                                yield {"type": "expert_chunk", "chunk_type": chunk_type, "content": chunk_content, "expert_id": exp["expert_id"], "node_id": nid, "level": level_idx + 1}
                                if chunk_type == "content":
                                    full_content += chunk_content
                        opinion.role = ExpertRole(exp["role"])
                        node_outputs[nid] = full_content
                        yield {"type": "expert_speak", "expert_id": exp["expert_id"], "expert_type": expert.expert_type, "role": exp["role"], "content": full_content, "suggestions": opinion.suggestions, "node_id": nid, "level": level_idx + 1}
                    else:
                        yield {"type": "node_skip", "node_id": nid, "reason": "no expert"}

                if human_feedback:
                    pass  # 管道模式下不阻塞，用户通过停止按钮控制

            yield {"type": "level_complete", "level": level_idx + 1}

        self._state = "completed"
        pipeline_summary = "\n\n---\n\n".join(f"## {nid}\n\n{content}" for nid, content in node_outputs.items())
        output = {"node_outputs": node_outputs, "total_speeches": self._speech_count, "meeting_summary": pipeline_summary}
        yield {"type": "pipeline_complete", "output": output}
        return output


# ── 预置模板 ────────────────────────────────────────────────

PRESET_CONFIGS = {
    "quick_review": {
        "meeting_name": "方案审核",
        "experts": [
            {"expert_id": "web_editor_v1", "role": "main"},
        ]
    },
    "volume_planning": {
        "meeting_name": "卷纲编排",
        "experts": [
            {"expert_id": "senior_author_v1", "role": "main"},
            {"expert_id": "reader_representative_v1", "role": "review"},
            {"expert_id": "senior_author_v1", "role": "supplement"},
        ]
    },
    "chapter_design": {
        "meeting_name": "章纲设计",
        "experts": [
            {"expert_id": "plot_architect_v1", "role": "main"},
            {"expert_id": "web_editor_v1", "role": "review"},
            {"expert_id": "character_designer_v1", "role": "supplement"},
        ]
    }
}
