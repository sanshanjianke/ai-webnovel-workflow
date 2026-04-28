from backend.core.protocols.l3 import BaseL3Narrative, ChapterPlan, Outline
from backend.core.registry import register_module
from typing import Optional


L3_PROMPT = """你是L3叙事层，负责将L2的大纲"翻译"为可直接执行的章纲/细纲。

映射规则：

### 情绪 → 视角映射
| 情绪 | 推荐视角 | 理由 |
|------|----------|------|
| 压抑（被嘲讽/轻视） | 反派/路人内聚焦 | 让读者感受傲慢，制造信息差 |
| 爆发（打脸/反转） | 外聚焦 | 客观呈现，不带感情更装逼 |
| 余韵（震惊/膜拜） | 自由间接引语 | 直接展示心理崩溃 |

### 情绪 → 节奏映射
| 情绪 | 推荐节奏 | 实现方式 |
|------|----------|----------|
| 压抑 | 慢速扩述 | 详细描写、大量对话、心理活动 |
| 爆发 | 中速等述 | 动作+环境，篇幅适中 |
| 余韵 | 快速概述 | 简短带过、留白 |

### 场景 → 话语模式映射
| 场景类型 | 推荐模式 | 说明 |
|----------|----------|------|
| 对峙/冲突 | 大量对话+动作 | 推进剧情 |
| 心理活动 | 自由间接引语 | 深入人物内心 |
| 环境烘托 | 环境描写+感官 | 渲染氛围 |
| 战斗爆发 | 短句+动词密集 | 加快节奏 |

输入大纲：
{outline}

请生成章纲/细纲，输出格式：

# 章纲/细纲

## 第X章：[章节名]

### 场景1：[场景名]
- 视角：[具体视角]
- 节奏：[扩述/等述/概述]
- 话语模式：[对话/动作/心理/环境]
- 字数：[预估]
- 内容要点：
  - [...]
  - [...]

### 场景2：[场景名]
...

## 章节情绪曲线
[描述本章的情绪走向]

## 伏笔/钩子
- [本章埋的伏笔]
- [结尾的悬念钩子]
"""


@register_module("l3")
class MappingCompiler(BaseL3Narrative):
    def __init__(self, llm=None):
        self.llm = llm
    
    def generate_chapter_plan(
        self,
        outline: Outline,
        rag_technique=None,
        world_book=None
    ) -> ChapterPlan:
        from backend.core.config import get_config
        from backend.core.registry import get_module
        
        if self.llm is None:
            config = get_config()
            llm_cls = get_module("llm", config.llm.primary)
            self.llm = llm_cls()
        
        outline_text = self._format_outline(outline)
        
        prompt = L3_PROMPT.format(outline=outline_text)
        
        response = self.llm.invoke(prompt)
        
        return self._parse_response(response)
    
    def _format_outline(self, outline: Outline) -> str:
        parts = []
        
        parts.append("序列：")
        for seq in outline.sequences:
            parts.append(f"- {seq.get('name', '未命名序列')}")
        
        parts.append("\n人物：")
        for char in outline.characters:
            parts.append(f"- {char.get('name', '未命名')}: {char.get('role', '')} {char.get('traits', '')}")
        
        if outline.world_notes:
            parts.append("\n世界观备注：")
            for note in outline.world_notes:
                parts.append(f"- {note}")
        
        return "\n".join(parts)
    
    def _parse_response(self, response: str) -> ChapterPlan:
        import re
        
        chapter_match = re.search(r'##\s*第.+章[：:]\s*(.+)', response)
        chapter_name = chapter_match.group(1).strip() if chapter_match else "未命名章节"
        
        scenes = []
        scene_pattern = r'###\s*场景\d+[：:]\s*(.+?)(?=###|##|$)'
        scene_matches = re.findall(scene_pattern, response, re.DOTALL)
        
        for scene_content in scene_matches:
            scene = {"name": scene_content.split("\n")[0].strip()}
            
            perspective_match = re.search(r'视角[：:]\s*(.+)', scene_content)
            if perspective_match:
                scene["perspective"] = perspective_match.group(1).strip()
            
            pace_match = re.search(r'节奏[：:]\s*(.+)', scene_content)
            if pace_match:
                scene["pace"] = pace_match.group(1).strip()
            
            mode_match = re.search(r'话语模式[：:]\s*(.+)', scene_content)
            if mode_match:
                scene["discourse_mode"] = mode_match.group(1).strip()
            
            wordcount_match = re.search(r'字数[：:]\s*(\d+)', scene_content)
            if wordcount_match:
                scene["word_count"] = int(wordcount_match.group(1))
            
            scenes.append(scene)
        
        emotion_match = re.search(r'##\s*章节情绪曲线\s*(.+?)(?=##|$)', response, re.DOTALL)
        emotion_curve = emotion_match.group(1).strip() if emotion_match else ""
        
        hooks = []
        hook_match = re.search(r'##\s*伏笔/钩子\s*(.+?)(?=##|$)', response, re.DOTALL)
        if hook_match:
            hook_content = hook_match.group(1)
            hooks = [
                line.strip().lstrip("- ")
                for line in hook_content.split("\n")
                if line.strip().startswith("-")
            ]
        
        return ChapterPlan(
            chapter_name=chapter_name,
            scenes=scenes,
            emotion_curve=emotion_curve,
            hooks=hooks
        )
