from backend.core.protocols.expert import BaseExpert, ExpertOpinion, Outline
from backend.core.registry import register_module
from typing import Optional


CHARACTER_PROMPT = """你是人物设计师，负责故事的"血肉"。你是导演兼选角导演，确保人物行为真实、关系清晰、人设讨喜。

核心职责：
1. 分配**行动元**（主体/客体/敌对者/帮助者）
2. 根据人设推导行为，防止OOC（Out Of Character）
3. 设计人物互动张力，确保人物服务于剧情

核心概念：
- **行动元模型**：
```
       发送者
          ↓
帮助者 → 主体 → 客体 ← 敌对者
```
  - 主体：追求目标的角色
  - 客体：被追求的目标
  - 发送者：推动主体行动的力量
  - 接收者：获益者（通常与主体重合）
  - 帮助者：协助主体
  - 敌对者：阻碍主体

- **人物类型**：
  - 扁形人物：特性稳定、功能性强、易理解
  - 圆形人物：复杂矛盾、有成长弧光、承载主题

- **人物轴线**：
  - 单一 ↔ 复杂
  - 静态 ↔ 动态
  - 外部 ↔ 内部

- **人设要素**：
  - 核心特性：1-3个形容词锁定
  - 行为逻辑：在[场景]中，因[特性]，会做[行为]
  - 禁忌行为：人设不允许做的事

当前剧情架构师的方案：
{architect_proposal}

网络编辑的评估：
{editor_opinion}

当前故事愿景：
{vision}

请从人物角度审核并补充。输出格式：

【人物设计师发言】

基于剧情架构师和网络编辑的方案，我的补充如下：

**行动元分配**：
- 主体：[主角]
- 客体：[目标]
- 敌对者：[反派/阻碍]
- 帮助者：[协助者]

**人物行为审核**：
- [某人物]：[行为]是否符合人设？
  - ✅/❌ + 理由

**新增人物建议**：
| 角色 | 行动元 | 核心特性 | 功能 |
|------|--------|----------|------|
| ... | ... | ... | ... |

**人设更新**：
[如有需要调整的人设]
"""


@register_module("expert")
class CharacterDesignerV1(BaseExpert):
    def __init__(self, llm=None):
        self.llm = llm
    
    @property
    def expert_id(self) -> str:
        return "character_v1"
    
    @property
    def expert_type(self) -> str:
        return "人物设计师"
    
    def speak(self, outline: Optional[Outline], context: dict) -> ExpertOpinion:
        from backend.core.config import get_config
        from backend.core.registry import get_module
        
        if self.llm is None:
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            self.llm = llm_cls()
        
        architect_proposal = context.get("architect_proposal", "暂无")
        editor_opinion = context.get("editor_opinion", "暂无")
        vision = context.get("vision", {})
        
        vision_text = self._format_vision(vision)
        
        prompt = CHARACTER_PROMPT.format(
            architect_proposal=architect_proposal,
            editor_opinion=editor_opinion,
            vision=vision_text
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
        lines = response.split("\n")
        suggestions = []
        for line in lines:
            if "建议" in line or "应" in line or "新增" in line:
                suggestions.append(line.strip())
        return suggestions[:5]
