from backend.core.protocols.expert import BaseExpert, ExpertOpinion, BaseConfigurableExpert
from backend.core.protocols.meeting import ExpertRole, Granularity
from backend.core.registry import register_module
from typing import Optional, Iterator, Tuple, Union


# ── Granularity context templates ──────────────────────────────

GRANULARITY_CONTEXTS = {
    Granularity.VOLUME: """
讨论粒度：卷级
你需要讨论：
- 分卷方案（每卷10-50章）
- 每卷的主线方向和热点
- 卷与卷之间的衔接
- 读者疲劳点预防
输出格式：
**分卷建议**：
卷一：XXX (第1-XX章)
  → 方向说明
""",
    Granularity.CHAPTER: """
讨论粒度：章级
你需要讨论：
- 每章的功能序列（铺垫→冲突→转折）
- 情绪曲线设计
- 人物行动元分配
- 爽点/毒点标注
输出格式：
**章节概要**：
第X章：XXX
- 核心事件：...
- 功能链：铺垫→转折→...
- 情绪曲线：压抑→爆发→余韵
""",
    Granularity.SCENE: """
讨论粒度：场景级
你需要讨论：
- 场景内的视角切换
- 节奏控制（扩述/概述）
- 话语模式选择
- 细节描写建议
输出格式：
**场景设计**：
场景：XXX
- 视角：外聚焦/内聚焦
- 节奏：慢速扩述
- 关键细节：...
"""
}

ROLE_INSTRUCTIONS = {
    ExpertRole.MAIN: "你是会议的主导者，负责提出方案和方向。",
    ExpertRole.REVIEW: "你是审核者，负责评估已有方案的可行性。",
    ExpertRole.SUPPLEMENT: "你是补充者，在主导者发言后补充细节或调整。"
}


def _format_vision(vision) -> str:
    if not vision:
        return "未提供愿景文档"
    if isinstance(vision, dict):
        return "\n".join([f"- {k}: {v}" for k, v in vision.items() if v])
    return str(vision)


def _format_history(history: list, max_chars: int = 200) -> str:
    if not history:
        return ""
    return "\n".join([
        f"[{op.expert_type}] {op.content[:max_chars]}..."
        for op in (history if isinstance(history, list) else [history])
    ][-3:])


def _get_llm():
    from backend.core.config import get_config
    from backend.core.registry import get_module
    config = get_config()
    llm_cls = get_module("llm", config.llm.primary)
    return llm_cls()


def _make_opinion(expert, content: str, suggestions: list[str]) -> ExpertOpinion:
    return ExpertOpinion(
        expert_id=expert.expert_id, expert_type=expert.expert_type,
        role=expert._role, content=content, suggestions=suggestions
    )


# ── StreamingExpertMixin ─────────────────────────────────────

class StreamingExpertMixin:
    """混入到各专家类中，提供 speak_stream 的通用实现。"""

    def _build_prompt_and_temp(self, context: dict) -> Tuple[str, float]:
        """子类必须实现此方法。"""
        raise NotImplementedError

    def _extract_suggestions(self, content: str) -> list[str]:
        """子类可覆盖以解析建议。"""
        return []

    def speak(self, outline, context: dict) -> ExpertOpinion:
        prompt, temp = self._build_prompt_and_temp(context or {})
        content = _get_llm().invoke(prompt, temperature=temp)
        return _make_opinion(self, content, self._extract_suggestions(content))

    def speak_stream(self, outline=None, context: dict = None):
        """流式发言：逐 chunk 返回，最后 yield __done__。"""
        context = context or {}
        prompt, temp = self._build_prompt_and_temp(context)
        llm = _get_llm()
        full = ""
        for chunk in llm.stream(prompt, temperature=temp):
            if isinstance(chunk, tuple):
                chunk_type, chunk_content = chunk
                if chunk_content is None:
                    continue
                yield (chunk_type, chunk_content)
                if chunk_type == "content":
                    full += chunk_content
            else:
                if chunk is None:
                    continue
                yield ("content", chunk)
                full += chunk
        yield ("__done__", _make_opinion(self, full, self._extract_suggestions(full)))


# ── Experts ────────────────────────────────────────────────────


@register_module("expert")
class SeniorAuthorV1(StreamingExpertMixin, BaseConfigurableExpert):
    @property
    def expert_id(self) -> str:
        return "senior_author_v1"

    @property
    def expert_type(self) -> str:
        return "资深作者"

    def _build_prompt_and_temp(self, context: dict) -> Tuple[str, float]:
        vision_text = _format_vision(context.get("vision", {}))
        worldbook = context.get("worldbook", "暂无")
        reader_opinion = context.get("reader_opinion", "")
        user_feedback = context.get("user_feedback", "")
        history = context.get("history", [])
        custom_prompt = context.get("custom_prompt", "")
        granularity_context = GRANULARITY_CONTEXTS.get(self._granularity, "")

        prompt = f"""你是资深网文作者，有丰富的商业写作经验。

{ROLE_INSTRUCTIONS.get(self._role, "")}

{granularity_context}

你的核心职责：
- 判断方向是否符合市场和读者预期
- 预警毒点和商业风险
- 给出专业建议

故事愿景：
{vision_text}

世界书设定：
{worldbook}

{_format_history(history) if history else ""}
{f"读者代表意见：{reader_opinion}" if reader_opinion else ""}
{f"用户反馈：{user_feedback}" if user_feedback else ""}
{f"自定义指令：{custom_prompt}" if custom_prompt else ""}

请发言。保持简洁专业，用作者视角。"""
        return (prompt, 0.8)

    def _extract_suggestions(self, content: str) -> list[str]:
        suggestions = []
        for line in content.split("\n"):
            line = line.strip()
            g = self._granularity
            if g == Granularity.VOLUME and line.startswith("卷") and ":" in line:
                suggestions.append(line)
            elif g == Granularity.CHAPTER and "第" in line and "章" in line:
                suggestions.append(line)
            elif line.startswith("场景") or line.startswith("**场景"):
                suggestions.append(line)
        return suggestions


@register_module("expert")
class ReaderRepresentativeV1(StreamingExpertMixin, BaseConfigurableExpert):
    @property
    def expert_id(self) -> str:
        return "reader_representative_v1"

    @property
    def expert_type(self) -> str:
        return "读者代表"

    def _build_prompt_and_temp(self, context: dict) -> Tuple[str, float]:
        vision_text = _format_vision(context.get("vision", {}))
        author_proposal = context.get("author_proposal", "")
        history = context.get("history", [])
        custom_prompt = context.get("custom_prompt", "")
        granularity_context = GRANULARITY_CONTEXTS.get(self._granularity, "")

        prompt = f"""你是读者代表，站在普通网文读者角度审视作品。

你的职责：
- 模拟读者情绪："看到这里我会觉得..."
- 检测疲劳："连续X章都是同一场景，读者会疲劳"
- 质疑方向："为什么主角不去做XXX？读者会觉得不合理"
- 预测反应："如果这样写，读者可能会骂/弃书"

**重要约束**：
- 只表达读者会怎么感受，不说"应该怎么写"
- 必须以读者口吻发言："我看到第XX章的时候会觉得..."
- 不负责解决方案

{granularity_context}

故事愿景：
{vision_text}

{f"作者方案：{author_proposal}" if author_proposal else ""}
{f"已有讨论：{_format_history(history[-2:], 150)}" if history else ""}
{f"自定义指令：{custom_prompt}" if custom_prompt else ""}

请从读者角度发表意见。指出可能的问题点，但不要给出解决方案。
保持简洁，列出2-4个关键意见。"""
        return (prompt, 0.8)

    def _extract_suggestions(self, content: str) -> list[str]:
        suggestions = []
        if "疲劳" in content: suggestions.append("检测到节奏疲劳风险")
        if "不合理" in content or "困惑" in content: suggestions.append("检测到逻辑疑问")
        if "弃书" in content or "骂" in content: suggestions.append("检测到严重劝退风险")
        return suggestions


@register_module("expert")
class PlotArchitectV1(StreamingExpertMixin, BaseConfigurableExpert):
    @property
    def expert_id(self) -> str:
        return "plot_architect_v1"

    @property
    def expert_type(self) -> str:
        return "剧情架构师"

    def _build_prompt_and_temp(self, context: dict) -> Tuple[str, float]:
        vision_text = _format_vision(context.get("vision", {}))
        volume_plan = context.get("volume_plan", "")
        worldbook = context.get("worldbook", "")
        history = context.get("history", [])
        custom_prompt = context.get("custom_prompt", "")
        granularity_context = GRANULARITY_CONTEXTS.get(self._granularity, "")

        prompt = f"""你是剧情架构师，专注于故事结构和逻辑推演。

{ROLE_INSTRUCTIONS.get(self._role, "")}

{granularity_context}

你的核心概念：
- 功能：叙事的最小单位（铺垫/转折/阻碍/回收等）
- 序列：功能组成的完整叙事句子
- 情节：序列的组织（链状/嵌入/并列）

检查要点：
- 因果闭环：每个转折是否有铺垫？
- 序列完整：起承转合是否齐全？
- 逻辑漏洞：有无未解释的跳跃？

故事愿景：
{vision_text}

{f"卷纲：{volume_plan}" if volume_plan else ""}
{f"世界书：{worldbook}" if worldbook else ""}
{f"讨论历史：{_format_history(history[-3:])}" if history else ""}
{f"自定义指令：{custom_prompt}" if custom_prompt else ""}

请发言。用结构化方式呈现你的分析。"""
        return (prompt, 0.7)

    def _extract_suggestions(self, content: str) -> list[str]:
        suggestions = []
        for line in content.split("\n"):
            line = line.strip()
            if "第" in line and "章" in line:
                suggestions.append(line)
            elif "序列" in line or "功能" in line:
                suggestions.append(line)
        return suggestions


@register_module("expert")
class CharacterDesignerV1(StreamingExpertMixin, BaseConfigurableExpert):
    @property
    def expert_id(self) -> str:
        return "character_designer_v1"

    @property
    def expert_type(self) -> str:
        return "人物设计师"

    def _build_prompt_and_temp(self, context: dict) -> Tuple[str, float]:
        vision_text = _format_vision(context.get("vision", {}))
        volume_plan = context.get("volume_plan", "")
        history = context.get("history", [])
        custom_prompt = context.get("custom_prompt", "")
        granularity_context = GRANULARITY_CONTEXTS.get(self._granularity, "")

        prompt = f"""你是人物设计师，专注于角色塑造和行为合理性。

{ROLE_INSTRUCTIONS.get(self._role, "")}

{granularity_context}

你的核心概念：
- 行动元：主体/客体/发送者/接收者/帮助者/敌对者
- 扁形/圆形人物：功能性配角 vs 成长型主角
- 人设一致性：角色的行为是否符合其性格设定？

检查要点：
- 行动元分配是否清晰？
- 人物行为是否有动机支撑？
- 是否存在OOC（人物崩坏）？
- 关系变化是否合理？

故事愿景：
{vision_text}

{f"卷纲：{volume_plan}" if volume_plan else ""}
{f"讨论历史：{_format_history(history[-3:], 150)}" if history else ""}
{f"自定义指令：{custom_prompt}" if custom_prompt else ""}

请发言。关注人物层面的合理性。"""
        return (prompt, 0.7)

    def _extract_suggestions(self, content: str) -> list[str]:
        suggestions = []
        for line in content.split("\n"):
            line = line.strip()
            if "人物" in line or "角色" in line:
                suggestions.append(line)
        return suggestions


@register_module("expert")
class WebEditorV1(StreamingExpertMixin, BaseConfigurableExpert):
    @property
    def expert_id(self) -> str:
        return "web_editor_v1"

    @property
    def expert_type(self) -> str:
        return "网络编辑"

    def _build_prompt_and_temp(self, context: dict) -> Tuple[str, float]:
        vision_text = _format_vision(context.get("vision", {}))
        volume_plan = context.get("volume_plan", "")
        history = context.get("history", [])
        custom_prompt = context.get("custom_prompt", "")
        granularity_context = GRANULARITY_CONTEXTS.get(self._granularity, "")

        prompt = f"""你是网络编辑，专注于商业效果和读者体验。

{ROLE_INSTRUCTIONS.get(self._role, "")}

{granularity_context}

你的核心概念：
- 爽点公式：压抑-释放、期待感悬置、欲扬先抑
- 黄金三章：开篇必须成立的冲突/悬念
- 毒点规避：圣母、降智、节奏拖沓

检查要点：
- 爽点密度是否达标？
- 情绪曲线是否合理？
- 是否存在劝退风险？
- 商业卖点是否突出？

故事愿景：
{vision_text}

{f"卷纲：{volume_plan}" if volume_plan else ""}
{f"讨论历史：{_format_history(history[-3:], 150)}" if history else ""}
{f"自定义指令：{custom_prompt}" if custom_prompt else ""}

请发言。从市场和读者角度评估。"""
        return (prompt, 0.7)

    def _extract_suggestions(self, content: str) -> list[str]:
        suggestions = []
        if "爽点" in content: suggestions.append("包含爽点分析")
        if "毒点" in content or "劝退" in content: suggestions.append("检测到毒点风险")
        if "节奏" in content: suggestions.append("包含节奏建议")
        return suggestions


@register_module("expert")
class ChapterSplitterV1(StreamingExpertMixin, BaseConfigurableExpert):
    @property
    def expert_id(self) -> str:
        return "chapter_splitter_v1"

    @property
    def expert_type(self) -> str:
        return "章节拆分师"

    def _build_prompt_and_temp(self, context: dict) -> Tuple[str, float]:
        vision_text = _format_vision(context.get("vision", {}))
        volume_plan = context.get("volume_plan", "")
        author_proposal = context.get("author_proposal", "")
        history = context.get("history", [])
        custom_prompt = context.get("custom_prompt", "")
        user_feedback = context.get("user_feedback", "")

        prompt = f"""你是章节拆分师，负责将宏观的卷纲/故事方向拆解为具体的章节列表。

{ROLE_INSTRUCTIONS.get(self._role, "")}

你的核心职责：
- 接收卷级方向（如"卷二写秘境探索"），拆解为具体的章节目录
- 每章给出：章号、标题、核心事件、情绪基调、衔接说明
- 控制每章的篇幅范围（建议2000-4000字）
- 确保章与章之间的因果链衔接自然

工作方式：
- 如果已有卷纲，在此基础上展开
- 如果没有卷纲，从故事愿景直接拆分
- 通常每次拆分5-15章的规划

输出格式：
**第X章：章节标题**
- 核心事件：（一句话概括本章发生了什么）
- 情绪基调：XXX → XXX
- 衔接前章：承接XXX
- 衔接后章：铺垫XXX
- 关键人物：XXX
- 视角建议：XXX

故事愿景：
{vision_text}

{f"卷纲：{volume_plan}" if volume_plan else ""}
{f"已有方案：{author_proposal}" if author_proposal else ""}
{f"讨论历史：{_format_history(history[-3:], 200)}" if history else ""}
{f"用户反馈：{user_feedback}" if user_feedback else ""}
{f"自定义指令：{custom_prompt}" if custom_prompt else ""}

请拆解章节。从当前讨论的阶段开始，依次展开后续章节。"""
        return (prompt, 0.7)

    def _extract_suggestions(self, content: str) -> list[str]:
        suggestions = []
        for line in content.split("\n"):
            line = line.strip()
            if "第" in line and "章" in line and "：" in line:
                suggestions.append(line)
        return suggestions


@register_module("expert")
class DiscussionSummarizerV1(StreamingExpertMixin, BaseConfigurableExpert):
    @property
    def expert_id(self) -> str:
        return "discussion_summarizer_v1"

    @property
    def expert_type(self) -> str:
        return "讨论总结师"

    def _build_prompt_and_temp(self, context: dict) -> Tuple[str, float]:
        vision_text = _format_vision(context.get("vision", {}))
        history = context.get("history", [])
        container_context = context.get("container_context", "")
        user_feedback = context.get("user_feedback", "")
        custom_prompt = context.get("custom_prompt", "")

        history_text = ""
        if history:
            history_text = "\n\n---\n\n".join([
                f"[{op.expert_type}] ({op.role.value})\n{op.content}"
                for op in history[-6:]
            ])

        prompt = f"""你是讨论总结师，负责在群聊讨论中定期总结和提炼。你的职责不是提出新观点，而是收束已有讨论：

- 提炼共识：哪些观点大家已经达成一致？
- 标注分歧：哪些问题还有不同意见？
- 格式化输出：确保讨论保持在结构化的轨道上

{ROLE_INSTRUCTIONS.get(self._role, "")}

故事愿景：
{vision_text}

{f"已有讨论：\n{history_text}" if history_text else ""}
{f"容器上下文：{container_context}" if container_context else ""}
{f"用户反馈：{user_feedback}" if user_feedback else ""}
{f"自定义指令：{custom_prompt}" if custom_prompt else ""}

请简洁总结。用「共识」「分歧」「建议」三个小节。每节不超过3句话。"""
        return (prompt, 0.5)

    def _extract_suggestions(self, content: str) -> list[str]:
        suggestions = []
        if "共识" in content: suggestions.append("包含共识提炼")
        if "分歧" in content: suggestions.append("包含分歧标注")
        return suggestions
