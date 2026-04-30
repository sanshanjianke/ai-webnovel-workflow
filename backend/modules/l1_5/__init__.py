from backend.core.protocols.expert import BaseExpert, ExpertOpinion
from backend.core.registry import register_module


@register_module("expert")
class SeniorAuthorV1(BaseExpert):
    @property
    def expert_id(self) -> str:
        return "senior_author_v1"
    
    @property
    def expert_type(self) -> str:
        return "资深作者"
    
    def speak(self, outline, context: dict) -> ExpertOpinion:
        from backend.core.registry import get_module
        from backend.core.config import get_config
        
        config = get_config()
        llm_cls = get_module("llm", config.llm.primary)
        llm = llm_cls()
        
        vision = context.get("vision", {})
        worldbook = context.get("worldbook", "暂无世界书")
        user_feedback = context.get("user_feedback", "")
        reader_opinion = context.get("reader_opinion", "")
        
        vision_text = ""
        if isinstance(vision, dict):
            vision_text = "\n".join([f"- {k}: {v}" for k, v in vision.items() if v])
        else:
            vision_text = str(vision)
        
        prompt = f"""你是资深网文作者，有丰富的商业写作经验。现在是L1.5情节编排会议。

你的职责：
- 根据故事愿景，提出分卷方案
- 判断每卷的方向、热点、读者预期
- 给出章节方向建议（每卷10-50章）
- 预警毒点和市场风险

故事愿景：
{vision_text}

世界书设定：
{worldbook}

{f"读者代表意见：{reader_opinion}" if reader_opinion else ""}
{f"用户反馈：{user_feedback}" if user_feedback else ""}

请提出分卷方案。格式：
**分卷建议**：
卷一：XXX (第1-XX章)
  → 方向说明
卷二：XXX (第XX-XX章)
  → 方向说明

**关键决策**：
1. ...
2. ...

保持简洁专业，用作者视角发言。"""
        
        content = llm.invoke(prompt, temperature=0.8)
        
        suggestions = []
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("卷") and ":" in line:
                suggestions.append(line.strip())
        
        return ExpertOpinion(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            content=content,
            suggestions=suggestions
        )


@register_module("expert")
class ReaderRepresentativeV1(BaseExpert):
    @property
    def expert_id(self) -> str:
        return "reader_representative_v1"
    
    @property
    def expert_type(self) -> str:
        return "读者代表"
    
    def speak(self, outline, context: dict) -> ExpertOpinion:
        from backend.core.registry import get_module
        from backend.core.config import get_config
        
        config = get_config()
        llm_cls = get_module("llm", config.llm.primary)
        llm = llm_cls()
        
        vision = context.get("vision", {})
        author_proposal = context.get("author_proposal", "暂无作者方案")
        
        vision_text = ""
        if isinstance(vision, dict):
            vision_text = "\n".join([f"- {k}: {v}" for k, v in vision.items() if v])
        else:
            vision_text = str(vision)
        
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

故事愿景：
{vision_text}

资深作者的分卷方案：
{author_proposal}

请从读者角度发表意见。指出可能的问题点，但不要给出解决方案。
保持简洁，列出2-4个关键意见。"""
        
        content = llm.invoke(prompt, temperature=0.8)
        
        suggestions = []
        if "疲劳" in content:
            suggestions.append("检测到节奏疲劳风险")
        if "不合理" in content or "困惑" in content:
            suggestions.append("检测到逻辑疑问")
        
        return ExpertOpinion(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            content=content,
            suggestions=suggestions
        )
