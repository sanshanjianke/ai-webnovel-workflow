from typing import Iterator
from backend.core.protocols.l4 import BaseL4Renderer, ChapterPlan, GeneratedText
from backend.core.registry import register_module


L4_PROMPT = """你是L4渲染层，负责根据L3的细纲生成正文文本。

写作约束：
{constraints}

场景要求：
{scene_requirements}

请严格按照约束生成正文。注意：
1. 视角约束：{perspective}
2. 节奏：{pace}
3. 话语模式：{discourse_mode}
4. 目标字数：{word_count}字左右

写作禁忌：
- 不要翻译腔
- 不要过度修饰
- 不要说教
- 外聚焦时禁止心理描写

直接输出正文，不要输出任何其他内容。
"""


@register_module("l4")
class ConstrainedRenderer(BaseL4Renderer):
    def __init__(self, llm=None):
        self.llm = llm
    
    def render(
        self,
        chapter_plan: ChapterPlan,
        rag_technique=None,
        world_book=None
    ) -> GeneratedText:
        from backend.core.config import get_config
        from backend.core.registry import get_module
        
        if self.llm is None:
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            self.llm = llm_cls()
        
        full_text = ""
        for scene in chapter_plan.scenes:
            scene_text = self._render_scene(scene, chapter_plan, rag_technique, world_book)
            full_text += scene_text + "\n\n"
        
        word_count = len(full_text.replace(" ", "").replace("\n", ""))
        
        return GeneratedText(
            chapter_name=chapter_plan.chapter_name,
            content=full_text.strip(),
            word_count=word_count
        )
    
    def stream_render(
        self,
        chapter_plan: ChapterPlan,
        rag_technique=None,
        world_book=None
    ) -> Iterator[str]:
        from backend.core.config import get_config
        from backend.core.registry import get_module
        
        if self.llm is None:
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            self.llm = llm_cls()
        
        yield f"# {chapter_plan.chapter_name}\n\n"
        
        for scene in chapter_plan.scenes:
            constraints = self._build_constraints(scene)
            scene_requirements = self._build_scene_requirements(scene)
            
            prompt = L4_PROMPT.format(
                constraints=constraints,
                scene_requirements=scene_requirements,
                perspective=scene.get("perspective", "外聚焦"),
                pace=scene.get("pace", "等述"),
                discourse_mode=scene.get("discourse_mode", "对话+动作"),
                word_count=scene.get("word_count", 500)
            )
            
            for chunk in self.llm.stream(prompt):
                yield chunk
    
    def _render_scene(self, scene: dict, chapter_plan: ChapterPlan, rag_technique, world_book) -> str:
        constraints = self._build_constraints(scene)
        scene_requirements = self._build_scene_requirements(scene)
        
        prompt = L4_PROMPT.format(
            constraints=constraints,
            scene_requirements=scene_requirements,
            perspective=scene.get("perspective", "外聚焦"),
            pace=scene.get("pace", "等述"),
            discourse_mode=scene.get("discourse_mode", "对话+动作"),
            word_count=scene.get("word_count", 500)
        )
        
        return self.llm.invoke(prompt)
    
    def _build_constraints(self, scene: dict) -> str:
        constraints = []
        
        perspective = scene.get("perspective", "外聚焦")
        if "内聚焦" in perspective:
            constraints.append("使用内聚焦视角，只写该人物能看到/想到的内容")
        elif "外聚焦" in perspective:
            constraints.append("使用外聚焦视角，只写可观察的动作/对话/环境，不写任何人物心理")
        elif "自由间接" in perspective:
            constraints.append("使用自由间接引语，无引号，混合叙述者与人物声音")
        
        pace = scene.get("pace", "等述")
        if "扩述" in pace:
            constraints.append("慢速扩述：详细描写、感官展开、对话延伸")
        elif "概述" in pace:
            constraints.append("快速概述：省略细节，快速推进")
        else:
            constraints.append("中速等述：动作+简短描写，不过度展开")
        
        return "\n".join(constraints)
    
    def _build_scene_requirements(self, scene: dict) -> str:
        requirements = []
        requirements.append(f"场景名称：{scene.get('name', '未命名场景')}")
        requirements.append(f"目标字数：{scene.get('word_count', 500)}字")
        
        if scene.get("content_points"):
            requirements.append("内容要点：")
            for point in scene.get("content_points", []):
                requirements.append(f"  - {point}")
        
        return "\n".join(requirements)
