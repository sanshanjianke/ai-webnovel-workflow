from backend.core.protocols.expert import BaseExpert, ExpertOpinion, Outline
from backend.core.registry import register_module
from typing import Optional


ARCHITECT_PROMPT = """你是剧情架构师，负责故事的"骨架"。你是理性的逻辑构建者，只关注逻辑通顺与结构完整。

核心职责：
1. 将故事拆解为**功能**与**序列**
2. 构建因果闭环，修补逻辑漏洞
3. 确保情节链条完整

核心概念：
- **功能**：最小叙事单位（获得功能、禁令功能、违背功能、斗争功能、胜利功能、失败功能）
- **序列**：功能组成的完整叙事句子
  - 链状：A → B → C（顺序执行）
  - 嵌入：A → [B → C] → D（大序列套小序列）
  - 并列：A | B | C（多线并行）
- **情节类型**：线型（单线/复线/环形）、非线型（开放/淡化）

当前故事愿景：
{vision}

当前世界书状态：
{worldbook}

请根据上述信息，拆解出序列和功能。输出格式：

【剧情架构师发言】

基于愿景文档，我拆解出以下序列：

**序列一：[名称]**
- 功能链：[功能A] → [功能B] → [功能C]
- 逻辑说明：[为什么这样安排]
- 潜在问题：[如有逻辑漏洞需修补]

**序列二：[名称]**
...

请网络编辑和人物设计师补充。
"""


@register_module("expert")
class PlotArchitectV1(BaseExpert):
    def __init__(self, llm=None):
        self.llm = llm
    
    @property
    def expert_id(self) -> str:
        return "architect_v1"
    
    @property
    def expert_type(self) -> str:
        return "剧情架构师"
    
    def speak(self, outline: Optional[Outline], context: dict) -> ExpertOpinion:
        from backend.core.config import get_config
        from backend.core.registry import get_module
        
        if self.llm is None:
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            self.llm = llm_cls()
        
        vision = context.get("vision", {})
        worldbook = context.get("worldbook", "暂无")
        
        vision_text = self._format_vision(vision)
        
        prompt = ARCHITECT_PROMPT.format(
            vision=vision_text,
            worldbook=worldbook
        )
        
        response = self.llm.invoke(prompt)
        
        return ExpertOpinion(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            content=response,
            suggestions=self._extract_suggestions(response)
        )
    
    def _format_vision(self, vision: dict) -> str:
        if not vision:
            return "未提供愿景文档"
        
        parts = []
        for key, value in vision.items():
            if value:
                parts.append(f"- {key}: {value}")
        return "\n".join(parts) if parts else "未提供愿景文档"
    
    def _extract_suggestions(self, response: str) -> list[str]:
        import re
        suggestions = []
        lines = response.split("\n")
        for line in lines:
            if "建议" in line or "应" in line:
                suggestions.append(line.strip())
        return suggestions[:5]
