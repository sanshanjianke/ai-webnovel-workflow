"""
小说转大纲驱动程序

将完整网文小说转换为L2层格式的大纲/细纲

核心功能：
1. 读取小说文本
2. 使用LLM提取剧情结构
3. 识别序列、功能、人物、爽点
4. 生成L2格式的大纲/细纲
5. 输出结构化数据
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

sys.path.insert(0, str(Path(__file__).parent))

from utils import create_llm
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL


@dataclass
class Sequence:
    """序列"""
    sequence_id: str
    name: str
    description: str
    functions: List[Dict] = field(default_factory=list)
    emotion_curve: str = ""
    characters: List[str] = field(default_factory=list)


@dataclass
class ChapterOutline:
    """章节大纲"""
    chapter_id: str
    title: str
    sequences: List[Sequence] = field(default_factory=list)
    summary: str = ""
    word_count: int = 0


@dataclass
class Outline:
    """完整大纲"""
    novel_name: str
    author: str
    genre: str = ""
    protagonist: str = ""
    golden_finger: str = ""
    core_appeal: str = ""
    chapters: List[ChapterOutline] = field(default_factory=list)
    characters: Dict = field(default_factory=dict)


class NovelToOutlineDriver:
    """小说转大纲驱动"""
    
    def __init__(self, llm=None):
        self.llm = llm or create_llm()
        self.chunks = []
        
    def load_novel(self, novel_path: str, chunk_size: int = 3000) -> str:
        """加载小说并分块"""
        path = Path(novel_path)
        
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
        text = None
        
        for encoding in encodings:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    text = f.read()
                print(f"✓ 小说加载成功（编码: {encoding}）")
                break
            except:
                continue
        
        if not text:
            raise Exception("无法读取小说文件")
        
        # 分块
        self.chunks = []
        for i in range(0, len(text), chunk_size):
            self.chunks.append(text[i:i+chunk_size])
        
        print(f"✓ 小说分块完成: {len(self.chunks)}个块")
        return text
    
    def extract_basic_info(self, text: str) -> Dict:
        """提取小说基本信息"""
        prompt = f"""分析以下小说片段，提取基本信息：

{text[:2000]}

请以JSON格式返回：
{{
    "novel_name": "小说名",
    "author": "作者",
    "genre": "类型",
    "protagonist": "主角名",
    "golden_finger": "金手指/核心能力",
    "core_appeal": "核心爽点",
    "world_setting": "世界观设定"
}}
"""
        
        response = self.llm.invoke(prompt)
        
        try:
            # 尝试解析JSON
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            info = json.loads(content.strip())
            return info
        except:
            return {
                "novel_name": "未知",
                "author": "未知",
                "genre": "未知",
                "protagonist": "未知",
                "golden_finger": "未知",
                "core_appeal": "未知"
            }
    
    def extract_chapter_outline(self, chunk: str, chapter_num: int) -> Optional[ChapterOutline]:
        """从文本块提取章节大纲"""
        prompt = f"""分析以下小说片段，提取章节大纲：

{chunk}

请识别：
1. 章节标题（如有）
2. 剧情序列（每个序列包含： 名称、功能链、情绪曲线）
3. 涉及人物
4. 爽点类型

以JSON格式返回：
{{
    "chapter_title": "章节标题",
    "sequences": [
        {{
            "name": "序列名称",
            "functions": ["功能1", "功能2", "功能3"],
            "emotion_curve": "压抑→爆发→余韵",
            "characters": ["人物1", "人物2"],
            "appeal_type": "爽点类型（如：装逼打脸、升级获得、危机解除等）"
        }}
    ],
    "summary": "章节概要（50字以内）"
}}

注意：
- 每个序列应该是一个完整的故事单元
- 功能链描述剧情推进的逻辑
- 情绪曲线遵循"压抑-爆发-余韵"模式
"""
        
        try:
            response = self.llm.invoke(prompt)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            # 构建ChapterOutline
            sequences = []
            for i, seq_data in enumerate(data.get("sequences", [])):
                seq = Sequence(
                    sequence_id=f"seq_{chapter_num}_{i+1}",
                    name=seq_data.get("name", f"序列{i+1}"),
                    description="",
                    functions=[{"name": f, "emotion": ""} for f in seq_data.get("functions", [])],
                    emotion_curve=seq_data.get("emotion_curve", ""),
                    characters=seq_data.get("characters", [])
                )
                sequences.append(seq)
            
            outline = ChapterOutline(
                chapter_id=f"chapter_{chapter_num}",
                title=data.get("chapter_title", f"第{chapter_num}章"),
                sequences=sequences,
                summary=data.get("summary", ""),
                word_count=len(chunk)
            )
            
            return outline
            
        except Exception as e:
            print(f"  警告: 解析失败 - {e}")
            return None
    
    def extract_characters(self, text: str) -> Dict:
        """提取人物信息"""
        prompt = f"""分析以下小说片段，提取主要人物信息：

{text[:3000]}

请识别主要人物（最多5个），以JSON格式返回：
{{
    "characters": [
        {{
            "name": "人物名",
            "role": "主角/反派/配角",
            "trait": "性格特点",
            "action_element": "行动元（主体/客体/敌对者/帮助者）",
            "first_appear": "首次出场章节"
        }}
    ]
}}
"""
        
        try:
            response = self.llm.invoke(prompt)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            return {c["name"]: c for c in data.get("characters", [])}
        except:
            return {}
    
    def convert_novel_to_outline(
        self, 
        novel_path: str, 
        max_chapters: int = 10,
        chunk_size: int = 3000
    ) -> Outline:
        """
        将小说转换为大纲
        
        Args:
            novel_path: 小说文件路径
            max_chapters: 最大处理章节数（用于测试）
            chunk_size: 每块字符数
        """
        print("\n" + "="*60)
        print("  小说转大纲驱动")
        print("="*60)
        
        # 1. 加载小说
        print("\n【步骤1】加载小说...")
        text = self.load_novel(novel_path, chunk_size)
        
        # 2. 提取基本信息
        print("\n【步骤2】提取基本信息...")
        basic_info = self.extract_basic_info(text)
        print(f"  小说名: {basic_info.get('novel_name')}")
        print(f"  作者: {basic_info.get('author')}")
        print(f"  类型: {basic_info.get('genre')}")
        print(f"  主角: {basic_info.get('protagonist')}")
        
        # 3. 提取人物信息
        print("\n【步骤3】提取人物信息...")
        characters = self.extract_characters(text)
        print(f"  主要人物: {len(characters)}个")
        for name, info in list(characters.items())[:5]:
            print(f"    - {name}: {info.get('role', '未知')}")
        
        # 4. 提取章节大纲
        print(f"\n【步骤4】提取章节大纲（共{min(len(self.chunks), max_chapters)}块）...")
        
        chapters = []
        for i, chunk in enumerate(self.chunks[:max_chapters], 1):
            print(f"\n  处理第{i}块...")
            chapter = self.extract_chapter_outline(chunk, i)
            if chapter:
                chapters.append(chapter)
                print(f"    ✓ 章节: {chapter.title}")
                print(f"    ✓ 序列数: {len(chapter.sequences)}")
                print(f"    ✓ 字数: {chapter.word_count}")
            else:
                print(f"    ✗ 提取失败")
        
        # 5. 构建完整大纲
        outline = Outline(
            novel_name=basic_info.get('novel_name', '未知'),
            author=basic_info.get('author', '未知'),
            genre=basic_info.get('genre', ''),
            protagonist=basic_info.get('protagonist', ''),
            golden_finger=basic_info.get('golden_finger', ''),
            core_appeal=basic_info.get('core_appeal', ''),
            chapters=chapters,
            characters=characters
        )
        
        print("\n" + "="*60)
        print("  转换完成")
        print("="*60)
        print(f"\n  总章节数: {len(chapters)}")
        print(f"  总序列数: {sum(len(c.sequences) for c in chapters)}")
        print(f"  总人物数: {len(characters)}")
        
        return outline
    
    def save_outline(self, outline: Outline, output_path: str):
        """保存大纲到文件"""
        # 转换为字典
        outline_dict = {
            "novel_name": outline.novel_name,
            "author": outline.author,
            "genre": outline.genre,
            "protagonist": outline.protagonist,
            "golden_finger": outline.golden_finger,
            "core_appeal": outline.core_appeal,
            "chapters": [
                {
                    "chapter_id": c.chapter_id,
                    "title": c.title,
                    "summary": c.summary,
                    "word_count": c.word_count,
                    "sequences": [
                        {
                            "sequence_id": s.sequence_id,
                            "name": s.name,
                            "functions": s.functions,
                            "emotion_curve": s.emotion_curve,
                            "characters": s.characters
                        }
                        for s in c.sequences
                    ]
                }
                for c in outline.chapters
            ],
            "characters": outline.characters
        }
        
        # 保存JSON
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(outline_dict, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 大纲已保存到: {output_file}")
        
        # 保存MD格式
        md_file = output_file.with_suffix('.md')
        self.save_outline_as_md(outline, md_file)
    
    def save_outline_as_md(self, outline: Outline, output_path: Path):
        """保存为MD格式"""
        md_content = f"""# {outline.novel_name} - 大纲

**作者**: {outline.author}
**类型**: {outline.genre}
**主角**: {outline.protagonist}
**金手指**: {outline.golden_finger}
**核心爽点**: {outline.core_appeal}

---

## 人物列表

"""
        for name, info in outline.characters.items():
            md_content += f"### {name}\n"
            md_content += f"- 角色: {info.get('role', '未知')}\n"
            md_content += f"- 性格: {info.get('trait', '未知')}\n"
            md_content += f"- 行动元: {info.get('action_element', '未知')}\n\n"
        
        md_content += "---\n\n## 章节大纲\n\n"
        
        for chapter in outline.chapters:
            md_content += f"### {chapter.title}\n\n"
            md_content += f"**概要**: {chapter.summary}\n\n"
            md_content += f"**字数**: {chapter.word_count}\n\n"
            
            if chapter.sequences:
                md_content += "**序列**:\n\n"
                for seq in chapter.sequences:
                    md_content += f"#### {seq.name}\n"
                    md_content += f"- 情绪曲线: {seq.emotion_curve}\n"
                    md_content += f"- 涉及人物: {', '.join(seq.characters)}\n"
                    if seq.functions:
                        md_content += f"- 功能链:\n"
                        for func in seq.functions:
                            md_content += f"  - {func.get('name', func) if isinstance(func, dict) else func}\n"
                    md_content += "\n"
            
            md_content += "---\n\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"✓ 大纲已保存到: {output_path}")


def test_driver():
    """测试驱动程序"""
    print("\n" + "="*60)
    print("  测试小说转大纲驱动")
    print("="*60)
    
    # 初始化
    driver = NovelToOutlineDriver()
    
    if not driver.llm:
        print("\n✗ LLM未初始化，测试失败")
        return None
    
    # 转换小说
    novel_path = "/home/ssjk/talk/1627崛起南海.txt"
    outline = driver.convert_novel_to_outline(
        novel_path,
        max_chapters=3,  # 测试用，只处理3块
        chunk_size=2000
    )
    
    # 保存
    output_path = Path("output/outline.json")
    driver.save_outline(outline, str(output_path))
    
    return outline


if __name__ == "__main__":
    test_driver()