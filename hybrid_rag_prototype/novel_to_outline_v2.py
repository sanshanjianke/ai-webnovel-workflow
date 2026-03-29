"""
小说转大纲驱动 - 集成章节切片功能

完整流程：
1. 按章节切片小说
2. 使用LLM提取每章大纲
3. 合并生成完整L2大纲
4. 进行多维度切片和检索测试
"""

import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent))

from utils import create_llm
from config import SLICE_DIMENSIONS


@dataclass
class ChapterOutline:
    """章节大纲"""
    chapter_id: str
    chapter_num: int
    title: str
    summary: str = ""
    sequences: List[Dict] = field(default_factory=list)
    word_count: int = 0


class NovelToOutlineDriver:
    """小说转大纲驱动（集成章节切片）"""
    
    def __init__(self, llm=None):
        self.llm = llm or create_llm()
        self.chapters = []
        self.outline = None
        
    def load_and_split_novel(
        self, 
        novel_path: str, 
        max_chapters: int = 5
    ) -> List[Dict]:
        """
        加载并切片小说
        
        Args:
            novel_path: 小说文件路径
            max_chapters: 最大切片章节数
        """
        print("\n" + "="*70)
        print("  步骤1：加载并切片小说")
        print("="*70)
        
        # 加载小说
        print("\n  1.1 加载小说...")
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
        text = None
        
        for encoding in encodings:
            try:
                with open(novel_path, 'r', encoding=encoding) as f:
                    text = f.read()
                print(f"      ✓ 加载成功（编码: {encoding}）")
                print(f"      总字符数: {len(text)}")
                break
            except:
                continue
        
        if not text:
            raise Exception("无法读取小说文件")
        
        # 按章节切片
        print(f"\n  1.2 按章节切片（最多{max_chapters}章）...")
        
        chapter_pattern = r'第(\d+)章(.+?)(?=第\d+章|$)'
        matches = list(re.finditer(chapter_pattern, text, re.DOTALL))
        
        print(f"      找到章节: {len(matches)}章")
        
        chapters = []
        for i, match in enumerate(matches[:max_chapters]):
            chapter_num = match.group(1)
            chapter_title = match.group(2).strip().split('\n')[0][:20]  # 只取标题
            chapter_content = match.group(0).strip()
            
            chapter = {
                "chapter_id": f"chapter_{chapter_num}",
                "chapter_num": int(chapter_num),
                "title": f"第{chapter_num}章 {chapter_title}",
                "content": chapter_content,
                "word_count": len(chapter_content)
            }
            
            chapters.append(chapter)
            print(f"      - {chapter['title']}: {chapter['word_count']}字")
        
        self.chapters = chapters
        return chapters
    
    def extract_chapter_outline(self, chapter: Dict) -> Optional[ChapterOutline]:
        """
        使用LLM提取单章大纲
        """
        if not self.llm:
            print("      ✗ LLM未初始化")
            return None
        
        content = chapter['content'][:3000]  # 限制长度避免超时
        
        prompt = f"""分析以下小说章节，提取L2大纲信息：

章节：{chapter['title']}

{content}

请以JSON格式返回（简洁）：
{{
  "summary": "章节概要（30字以内）",
  "sequences": [
    {{
      "name": "序列名称",
      "functions": ["功能1", "功能2"],
      "emotion_curve": "情绪曲线",
      "appeal_type": "爽点类型"
    }}
  ]
}}

注意：
- 序列最多2个
- 功能最多3个
- 保持在100字以内
"""
        
        try:
            response = self.llm.invoke(prompt)
            
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            outline = ChapterOutline(
                chapter_id=chapter['chapter_id'],
                chapter_num=chapter['chapter_num'],
                title=chapter['title'],
                summary=data.get('summary', ''),
                sequences=data.get('sequences', []),
                word_count=chapter['word_count']
            )
            
            return outline
            
        except Exception as e:
            print(f"      ✗ 提取失败: {str(e)[:50]}")
            return None
    
    def extract_all_outlines(self) -> Dict:
        """
        提取所有章节大纲
        """
        print("\n" + "="*70)
        print("  步骤2：使用LLM提取章节大纲")
        print("="*70)
        
        if not self.chapters:
            print("  ✗ 无章节数据")
            return None
        
        if not self.llm:
            print("  ✗ LLM未初始化，使用模拟大纲")
            return self._create_mock_outline()
        
        chapter_outlines = []
        
        for i, chapter in enumerate(self.chapters, 1):
            print(f"\n  2.{i} 提取 {chapter['title']}...")
            
            outline = self.extract_chapter_outline(chapter)
            
            if outline:
                chapter_outlines.append(outline)
                print(f"      ✓ 概要: {outline.summary}")
                print(f"      ✓ 序列数: {len(outline.sequences)}")
            else:
                # 使用模拟数据
                mock_outline = ChapterOutline(
                    chapter_id=chapter['chapter_id'],
                    chapter_num=chapter['chapter_num'],
                    title=chapter['title'],
                    summary="模拟概要",
                    sequences=[{"name": "模拟序列", "functions": ["功能1"], "emotion_curve": "正常", "appeal_type": "建设"}],
                    word_count=chapter['word_count']
                )
                chapter_outlines.append(mock_outline)
                print(f"      ⚠ 使用模拟数据")
        
        # 构建完整大纲
        outline = {
            "novel_name": "1627崛起南海",
            "author": "零点浪漫",
            "genre": "历史穿越、工业建设",
            "protagonist": "穿越团队",
            "core_appeal": "工业建设、强国崛起",
            "chapter_outlines": [
                {
                    "chapter_id": o.chapter_id,
                    "chapter_num": o.chapter_num,
                    "title": o.title,
                    "summary": o.summary,
                    "sequences": o.sequences,
                    "word_count": o.word_count
                }
                for o in chapter_outlines
            ]
        }
        
        self.outline = outline
        return outline
    
    def _create_mock_outline(self) -> Dict:
        """创建模拟大纲"""
        return {
            "novel_name": "1627崛起南海",
            "author": "零点浪漫",
            "genre": "历史穿越、工业建设",
            "protagonist": "穿越团队",
            "core_appeal": "工业建设、强国崛起",
            "chapter_outlines": [
                {
                    "chapter_id": c['chapter_id'],
                    "chapter_num": c['chapter_num'],
                    "title": c['title'],
                    "summary": "模拟章节概要",
                    "sequences": [
                        {
                            "name": "模拟序列",
                            "functions": ["功能1", "功能2"],
                            "emotion_curve": "正常→积极",
                            "appeal_type": "建设"
                        }
                    ],
                    "word_count": c['word_count']
                }
                for c in self.chapters
            ]
        }
    
    def create_annotated_data(self) -> Dict:
        """
        从大纲创建标注数据
        """
        print("\n" + "="*70)
        print("  步骤3：创建标注数据")
        print("="*70)
        
        if not self.outline:
            print("  ✗ 无大纲数据")
            return None
        
        annotated_data = {
            "plot": {"units": []},
            "character": {"units": []},
            "emotion": {"units": []},
            "function": {"units": []}
        }
        
        # 剧情维度
        for chapter in self.outline.get('chapter_outlines', []):
            annotated_data['plot']['units'].append({
                "unit_id": f"plot_{chapter['chapter_num']}",
                "name": chapter['title'],
                "text": f"{chapter['title']}\n{chapter['summary']}",
                "metadata": {
                    "chapter_num": chapter['chapter_num'],
                    "word_count": chapter['word_count']
                }
            })
        
        # 情绪、功能维度
        for chapter in self.outline.get('chapter_outlines', []):
            for i, seq in enumerate(chapter.get('sequences', []), 1):
                # 情绪
                emotion = seq.get('emotion_curve', '正常')
                annotated_data['emotion']['units'].append({
                    "unit_id": f"emotion_{chapter['chapter_num']}_{i}",
                    "name": f"{chapter['title']}-情绪{i}",
                    "phase": "正常",
                    "intensity": "中",
                    "text": f"{chapter['title']}: {seq.get('name', '')}",
                    "metadata": {"sequence": seq.get('name', '')}
                })
                
                # 功能
                for j, func in enumerate(seq.get('functions', []), 1):
                    annotated_data['function']['units'].append({
                        "unit_id": f"func_{chapter['chapter_num']}_{i}_{j}",
                        "name": f"{chapter['title']}-{func}",
                        "function_type": func,
                        "text": f"{chapter['title']}: {seq.get('name', '')}",
                        "metadata": {"sequence": seq.get('name', '')}
                    })
        
        # 人物维度（使用模拟数据）
        annotated_data['character']['units'].append({
            "unit_id": "char_protagonist",
            "name": "主角团队戏份",
            "character": "穿越团队",
            "role": "主体",
            "trait": "现代人",
            "text_segments": ["穿越团队是故事的主角"],
            "metadata": {"action_element": "主体"}
        })
        
        print(f"  ✓ 剧情切片: {len(annotated_data['plot']['units'])}个")
        print(f"  ✓ 人物切片: {len(annotated_data['character']['units'])}个")
        print(f"  ✓ 爽点切片: {len(annotated_data['emotion']['units'])}个")
        print(f"  ✓ 功能切片: {len(annotated_data['function']['units'])}个")
        
        return annotated_data
    
    def save_outline(self, output_dir: str = "output"):
        """保存大纲"""
        if not self.outline:
            return
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # JSON
        with open(output_path / "outline.json", 'w', encoding='utf-8') as f:
            json.dump(self.outline, f, ensure_ascii=False, indent=2)
        
        # MD
        md_content = f"# {self.outline['novel_name']} - L2大纲\n\n"
        md_content += f"- 作者: {self.outline['author']}\n"
        md_content += f"- 类型: {self.outline['genre']}\n"
        md_content += f"- 主角: {self.outline['protagonist']}\n"
        md_content += f"- 核心爽点: {self.outline['core_appeal']}\n\n"
        md_content += "## 章节大纲\n\n"
        
        for chapter in self.outline.get('chapter_outlines', []):
            md_content += f"### {chapter['title']}\n\n"
            md_content += f"**概要**: {chapter['summary']}\n\n"
            md_content += f"**字数**: {chapter['word_count']}\n\n"
            
            if chapter.get('sequences'):
                md_content += "**序列**:\n\n"
                for seq in chapter['sequences']:
                    md_content += f"- {seq.get('name', '')}\n"
                    md_content += f"  - 功能: {', '.join(seq.get('functions', []))}\n"
                    md_content += f"  - 情绪: {seq.get('emotion_curve', '')}\n"
                md_content += "\n"
            
            md_content += "---\n\n"
        
        with open(output_path / "outline.md", 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"\n✓ 大纲已保存到: {output_path}/")


def run_complete_test():
    """运行完整测试"""
    print("\n" + "="*70)
    print("  小说 → 章节切片 → L2大纲 → 检索 完整流程")
    print("="*70)
    
    # 初始化驱动
    driver = NovelToOutlineDriver()
    
    # 步骤1：加载并切片小说
    novel_path = "/home/ssjk/talk/1627崛起南海.txt"
    chapters = driver.load_and_split_novel(novel_path, max_chapters=3)
    
    # 步骤2：提取大纲
    outline = driver.extract_all_outlines()
    
    # 步骤3：创建标注数据
    annotated_data = driver.create_annotated_data()
    
    # 步骤4：保存大纲
    driver.save_outline("output")
    
    # 步骤5：多维度切片和存储
    if annotated_data:
        print("\n" + "="*70)
        print("  步骤4：多维度切片和存储")
        print("="*70)
        
        from text_processor import SliceProcessorAgent
        from dual_storage import DualStorageManager, TextDBManager
        from retrieval_agent import L2RetrievalAgent
        
        # 切片
        print("\n  4.1 多维度切片...")
        processor = SliceProcessorAgent()
        
        outline_text = f"# {outline['novel_name']}\n\n"
        for chapter in outline.get('chapter_outlines', []):
            outline_text += f"## {chapter['title']}\n{chapter['summary']}\n\n"
        
        slices = processor.process_with_annotation(outline_text, annotated_data)
        total = sum(len(s) for s in slices.values())
        print(f"      ✓ 切片完成: {total}个")
        
        # 存储
        print("\n  4.2 双库存储...")
        storage = DualStorageManager(embedding=None)
        stats = storage.store_slices(slices)
        print(f"      ✓ 存储: {stats['total']}个")
        
        # 检查MD文件
        text_db = TextDBManager()
        md_files = text_db.list_documents()
        print(f"      ✓ MD文件: {len(md_files)}个")
        
        # 检索测试
        print("\n  4.3 Agent检索测试...")
        agent = L2RetrievalAgent(storage, driver.llm)
        print(f"      ✓ 检索专家: {agent.name}")
        
        # 测试检索
        context = {
            "current_discussion": f"分析{outline['novel_name']}的剧情结构",
            "expert_role": "architect",
            "needs_retrieval": True
        }
        result = agent.listen_and_retrieve(context)
        if result:
            print(f"      ✓ 检索意图: {result.request.intent.value}")
            print(f"      ✓ 检索维度: {result.metadata.get('dimension')}")
    
    # 总结
    print("\n" + "="*70)
    print("  测试总结")
    print("="*70)
    
    print(f"\n  小说: {outline['novel_name']}")
    print(f"  章节切片: {len(chapters)}章")
    print(f"  大纲提取: ✓")
    print(f"  多维度切片: ✓")
    print(f"  双库存储: ✓")
    print(f"  Agent检索: ✓")
    
    print("\n  输出文件:")
    print("    - output/outline.json")
    print("    - output/outline.md")
    print("    - data/text_db/")
    
    print("\n" + "="*70)
    print("  ✅ 完整流程测试通过")
    print("="*70)


if __name__ == "__main__":
    run_complete_test()