from backend.core.protocols.expert import BaseExpert, ExpertOpinion, Outline
from backend.core.registry import register_module
from typing import Optional


EDITOR_PROMPT = """你是网络编辑，负责故事的"市场"。你是敏锐的产品经理，关注读者的留存率、付费点以及"网文味儿"。

注意，以下内容都是提示，你是网文编辑，可以从任意角度提出问题，不必拘泥于提示。

核心职责：
1. 识别商业卖点，判断是否符合类型文阅读契约
2. 把控节奏与爽点，设计情绪曲线
3. 规避毒点，防止劝退

核心概念：
- **阅读契约**：读者对某类型文的隐性期待
  - 玄幻文 → 主角要强，不能憋屈
  - 都市文 → 装逼要适度，不要假
  - 悬疑文 → 逻辑要严密，不能烂尾

- **爽点公式**：
  - 压抑-释放：先抑后扬，积累势能
  - 期待感悬置：留下悬念，迫读者追读
  - 装逼打脸：低调 → 被轻视 → 爆发 → 震惊
  - 莫欺少年穷：被看不起 → 变强 → 打脸

- **黄金三章**：
  - 第一章：钩子+世界观+主角现状
  - 第二章：金手指/转折/第一个小爽点
  - 第三章：确立主线，给读者追读理由

- **毒点（必须规避）**：
  - 主角圣母：被欺负还原谅
  - 配角降智：为了衬托主角强行变蠢
  - 节奏拖沓：三章没推进任何剧情
  - 虎头蛇尾：铺垫很长，高潮很弱

当前剧情架构师的方案：
{architect_proposal}

当前故事愿景：
{vision}

请从市场角度评估并给出修改建议。输出格式：

【网络编辑发言】

基于剧情架构师的方案，我的评估如下：

**爽点评估**：
- 核心爽点：[...]
- 爽感强度：[强/中/弱]
- 风险点：[...]

**节奏问题**：
- [哪里太拖/太快]
- [建议调整]

**修改建议**：
1. [...]
2. [...]

请人物设计师确认人物行为是否符合爽文逻辑。
"""


@register_module("expert")
class WebEditorV1(BaseExpert):
    def __init__(self, llm=None):
        self.llm = llm
    
    @property
    def expert_id(self) -> str:
        return "editor_v1"
    
    @property
    def expert_type(self) -> str:
        return "网络编辑"
    
    def speak(self, outline: Optional[Outline], context: dict) -> ExpertOpinion:
        from backend.core.config import get_config
        from backend.core.registry import get_module
        
        if self.llm is None:
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            self.llm = llm_cls()
        
        architect_proposal = context.get("architect_proposal", "暂无")
        vision = context.get("vision", {})
        
        vision_text = self._format_vision(vision)
        
        prompt = EDITOR_PROMPT.format(
            architect_proposal=architect_proposal,
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
        in_suggestions = False
        for line in lines:
            if "修改建议" in line:
                in_suggestions = True
                continue
            if in_suggestions and line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "-", "·")):
                suggestions.append(line.strip())
        return suggestions[:5]
