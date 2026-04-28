from backend.core.protocols.l1 import BaseSeedGenerator, VisionDocument
from backend.core.registry import register_module


L1_PROMPT = """你是一位创作顾问，帮助用户梳理创意愿景，产出清晰的故事种子文档。

请根据用户提供的以下信息，生成一份结构化的《故事愿景文档》：

用户输入：
{user_input}

请按以下格式输出：

# 故事愿景文档

## 核心梗
[一句话概括故事核心创意]

## 阅读契约
- 目标读者：[男频/女频/年龄层]
- 核心爽点：[装逼/升级/恋爱/悬疑等]
- 风格基调：[轻松/暗黑/热血/治愈等]

## 粗略大纲
1. 开篇：[...]
2. 发展：[...]
3. 高潮：[...]
4. 结局：[...]

## 核心设定
- 世界观：[...]
- 主角人设：[...]
- 金手指/核心道具：[...]

## 热点/潮流元素（如有）
- 热点：[...]
- 融合方式：[...]
- 时效性评估：[...]

## 预期字数
[长篇/中篇/短篇，预估字数]

注意：
- 不评判创意好坏，只负责结构化
- 如果用户信息不足，根据上下文合理补充
- 输出要简洁，不超过500字
"""


@register_module("l1")
class GuidedFormGenerator(BaseSeedGenerator):
    def __init__(self, llm=None):
        self.llm = llm

    def generate(self, user_input: dict) -> VisionDocument:
        from backend.core.config import get_config
        from backend.core.registry import get_module
        
        if self.llm is None:
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            self.llm = llm_cls()
        
        input_text = self._format_input(user_input)
        prompt = L1_PROMPT.format(user_input=input_text)
        
        response = self.llm.invoke(prompt)
        
        return self._parse_response(response, user_input)

    def _format_input(self, user_input: dict) -> str:
        parts = []
        for key, value in user_input.items():
            if value:
                parts.append(f"- {key}: {value}")
        return "\n".join(parts) if parts else "用户未提供具体信息，请根据创意方向生成"

    def _parse_response(self, response: str, original_input: dict) -> VisionDocument:
        core_idea = self._extract_section(response, "核心梗")
        target_readers = ""
        core_appeal = ""
        style = ""
        
        contract = self._extract_section(response, "阅读契约")
        if contract:
            lines = contract.split("\n")
            for line in lines:
                if "目标读者" in line:
                    target_readers = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                elif "核心爽点" in line:
                    core_appeal = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                elif "风格基调" in line:
                    style = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
        
        rough_outline = self._extract_section(response, "粗略大纲")
        
        setting = self._extract_section(response, "核心设定")
        world_setting = ""
        protagonist = ""
        golden_finger = ""
        if setting:
            lines = setting.split("\n")
            for line in lines:
                if "世界观" in line:
                    world_setting = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                elif "主角人设" in line:
                    protagonist = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                elif "金手指" in line or "核心道具" in line:
                    golden_finger = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
        
        hot_elements = self._extract_section(response, "热点/潮流元素")
        expected_length = self._extract_section(response, "预期字数")
        
        return VisionDocument(
            core_idea=core_idea or original_input.get("idea", ""),
            target_readers=target_readers or original_input.get("target_readers", ""),
            core_appeal=core_appeal or original_input.get("core_appeal", ""),
            style=style or original_input.get("style", ""),
            rough_outline=rough_outline or original_input.get("rough_outline", "") or original_input.get("outline", ""),
            world_setting=world_setting or original_input.get("world_setting", ""),
            protagonist=protagonist or original_input.get("protagonist", ""),
            golden_finger=golden_finger or original_input.get("golden_finger", ""),
            hot_elements=hot_elements or original_input.get("hot_elements", ""),
            expected_length=expected_length or original_input.get("expected_length", "")
        )

    def _extract_section(self, text: str, section_name: str) -> str:
        import re
        pattern = rf"##\s*{re.escape(section_name)}[^\n]*\n(.*?)(?=##|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
