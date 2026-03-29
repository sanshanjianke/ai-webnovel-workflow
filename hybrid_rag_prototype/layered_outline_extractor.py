"""
分层大纲提取器

流程：
1. 小说 → 章节切片（正则表达式）
2. 章节 → 分段（2000字/段）
3. 分段 → 草稿（LLM提取，200-500字）
4. 草稿汇总 → 完整L2大纲
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

import sys
sys.path.insert(0, str(Path(__file__).parent))

from utils import create_llm


@dataclass
class TextSegment:
    """文本分段"""
    segment_id: str
    chapter_num: int
    segment_index: int
    text: str
    word_count: int


@dataclass
class SegmentDraft:
    """分段草稿"""
    segment_id: str
    chapter_num: int
    draft_text: str  # 200-500字
    key_events: List[str] = field(default_factory=list)
    characters: List[str] = field(default_factory=list)


@dataclass
class ChapterDraft:
    """章节草稿"""
    chapter_num: int
    chapter_title: str
    segments: List[SegmentDraft] = field(default_factory=list)
    summary: str = ""
    sequences: List[Dict] = field(default_factory=list)


class LayeredOutlineExtractor:
    """分层大纲提取器"""
    
    def __init__(self, llm=None):
        self.llm = llm or create_llm()
        self.chapters = []
        self.segments = []
        self.segment_drafts = []
        self.chapter_drafts = []
    
    # ==================== 第1层：章节切片 ====================
    
    def split_by_chapters(self, text: str, max_chapters: int = None) -> List[Dict]:
        """按章节切片"""
        print("\n" + "="*70)
        print("  第1层：章节切片")
        print("="*70)
        
        chapter_pattern = r'第(\d+)章(.+?)(?=第\d+章|$)'
        matches = list(re.finditer(chapter_pattern, text, re.DOTALL))
        
        print(f"  找到章节: {len(matches)}章")
        
        chapters = []
        for i, match in enumerate(matches):
            if max_chapters and i >= max_chapters:
                break
            
            chapter_num = int(match.group(1))
            chapter_title = match.group(2).strip().split('\n')[0][:30]
            chapter_content = match.group(0).strip()
            
            chapter = {
                "chapter_num": chapter_num,
                "title": f"第{chapter_num}章 {chapter_title}",
                "content": chapter_content,
                "word_count": len(chapter_content)
            }
            
            chapters.append(chapter)
        
        self.chapters = chapters
        print(f"  切片完成: {len(chapters)}章")
        
        for c in chapters[:5]:
            print(f"    - {c['title']}: {c['word_count']}字")
        
        return chapters
    
    # ==================== 第2层：文本分段 ====================
    
    def split_chapters_to_segments(
        self, 
        chapters: List[Dict], 
        segment_size: int = 2000
    ) -> List[TextSegment]:
        """将章节分段"""
        print("\n" + "="*70)
        print("  第2层：文本分段")
        print("="*70)
        
        segments = []
        
        for chapter in chapters:
            chapter_num = chapter['chapter_num']
            content = chapter['content']
            
            # 按segment_size分段
            for i in range(0, len(content), segment_size):
                segment_text = content[i:i+segment_size]
                
                segment = TextSegment(
                    segment_id=f"seg_{chapter_num}_{i//segment_size + 1}",
                    chapter_num=chapter_num,
                    segment_index=i//segment_size + 1,
                    text=segment_text,
                    word_count=len(segment_text)
                )
                
                segments.append(segment)
        
        self.segments = segments
        
        print(f"  分段完成: {len(segments)}段")
        print(f"  平均每段: {sum(s.word_count for s in segments) / len(segments):.0f}字")
        
        return segments
    
    # ==================== 第3层：提取草稿 ====================
    
    def extract_segment_draft(
        self, 
        segment: TextSegment
    ) -> Optional[SegmentDraft]:
        """提取分段草稿"""
        
        if not self.llm:
            return None
        
        # 简化的Prompt，快速提取
        prompt = f"""分析以下小说片段，提取关键信息（200-500字）：

{segment.text[:1500]}

请输出：
1. 主要事件（2-3个）
2. 涉及人物
3. 情绪变化
4. 功能作用

要求：简洁，200-500字。"""
        
        try:
            response = self.llm.invoke(prompt)
            draft_text = response.content[:500]  # 限制500字
            
            # 简单提取关键信息
            key_events = []
            characters = []
            
            draft = SegmentDraft(
                segment_id=segment.segment_id,
                chapter_num=segment.chapter_num,
                draft_text=draft_text,
                key_events=key_events,
                characters=characters
            )
            
            return draft
            
        except Exception as e:
            print(f"    ⚠ 提取失败: {str(e)[:50]}")
            return None
    
    def extract_all_drafts(
        self, 
        segments: List[TextSegment],
        max_segments: int = None
    ) -> List[SegmentDraft]:
        """提取所有分段草稿"""
        print("\n" + "="*70)
        print("  第3层：提取草稿")
        print("="*70)
        
        if not self.llm:
            print("  ⚠ LLM未初始化，使用模拟草稿")
            return self._create_mock_drafts(segments, max_segments)
        
        drafts = []
        total = min(len(segments), max_segments) if max_segments else len(segments)
        
        print(f"  处理分段: {total}段")
        
        for i, segment in enumerate(segments[:max_segments], 1):
            print(f"    [{i}/{total}] {segment.segment_id}...", end=" ")
            
            draft = self.extract_segment_draft(segment)
            if draft:
                drafts.append(draft)
                print(f"✓ {len(draft.draft_text)}字")
            else:
                print("✗")
        
        self.segment_drafts = drafts
        
        print(f"\n  提取完成: {len(drafts)}个草稿")
        print(f"  总字数: {sum(len(d.draft_text) for d in drafts)}字")
        
        return drafts
    
    def _create_mock_drafts(
        self, 
        segments: List[TextSegment],
        max_segments: int = None
    ) -> List[SegmentDraft]:
        """创建模拟草稿"""
        drafts = []
        
        mock_templates = [
            "主角陶东来接机，与老同学宁崎会面，引出穿越团队招募话题。",
            "陶东来邀请宁崎加入穿越团队，展示虫洞控制器，穿越到明朝验证。",
            "团队确定穿越地点为海南岛榆林港，分工合作准备物资。",
            "新成员加入团队，各部门开始筹备工作。",
            "团队扩大，成立信息产业部，IT系统建设启动。"
        ]
        
        for i, segment in enumerate(segments[:max_segments], 1):
            template = mock_templates[i % len(mock_templates)]
            
            draft = SegmentDraft(
                segment_id=segment.segment_id,
                chapter_num=segment.chapter_num,
                draft_text=template,
                key_events=[],
                characters=[]
            )
            
            drafts.append(draft)
        
        return drafts
    
    # ==================== 第4层：汇总草稿 ====================
    
    def merge_drafts_by_chapter(
        self,
        drafts: List[SegmentDraft],
        chapters: List[Dict]
    ) -> List[ChapterDraft]:
        """按章节合并草稿"""
        print("\n" + "="*70)
        print("  第4层：汇总草稿")
        print("="*70)
        
        chapter_drafts = []
        
        for chapter in chapters:
            chapter_num = chapter['chapter_num']
            
            # 找到该章节的所有草稿
            chapter_segments = [d for d in drafts if d.chapter_num == chapter_num]
            
            if not chapter_segments:
                continue
            
            # 合并草稿文本
            merged_text = "\n".join(d.draft_text for d in chapter_segments)
            
            chapter_draft = ChapterDraft(
                chapter_num=chapter_num,
                chapter_title=chapter['title'],
                segments=chapter_segments,
                summary=merged_text[:500],
                sequences=[]
            )
            
            chapter_drafts.append(chapter_draft)
        
        self.chapter_drafts = chapter_drafts
        
        print(f"  汇总完成: {len(chapter_drafts)}章")
        
        for cd in chapter_drafts[:5]:
            print(f"    - 第{cd.chapter_num}章: {len(cd.segments)}段草稿")
        
        return chapter_drafts
    
    # ==================== 第5层：生成完整大纲 ====================
    
    def generate_complete_outline(
        self,
        chapter_drafts: List[ChapterDraft]
    ) -> Dict:
        """生成完整L2大纲"""
        print("\n" + "="*70)
        print("  第5层：生成完整大纲")
        print("="*70)
        
        if not self.llm:
            print("  ⚠ LLM未初始化，使用模板大纲")
            return self._create_mock_outline(chapter_drafts)
        
        # 汇总所有草稿
        all_drafts_text = "\n\n".join([
            f"【第{cd.chapter_num}章】{cd.chapter_title}\n{cd.summary}"
            for cd in chapter_drafts
        ])
        
        prompt = f"""根据以下章节草稿，生成完整的L2层大纲：

{all_drafts_text}

请生成JSON格式的大纲：
{{
  "novel_name": "小说名",
  "genre": "类型",
  "protagonist": "主角",
  "core_appeal": "核心爽点",
  "chapters": [
    {{
      "chapter_num": 1,
      "title": "章节标题",
      "summary": "章节概要（50字以内）",
      "sequences": [
        {{
          "name": "序列名",
          "functions": ["功能1", "功能2"],
          "emotion": "情绪曲线",
          "appeal_type": "爽点类型"
        }}
      ]
    }}
  ]
}}

要求：简洁，每章最多2个序列。"""
        
        try:
            response = self.llm.invoke(prompt)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            outline = json.loads(content.strip())
            
            print("  ✓ LLM大纲生成成功")
            return outline
            
        except Exception as e:
            print(f"  ⚠ LLM处理失败: {str(e)[:50]}")
            return self._create_mock_outline(chapter_drafts)
    
    def _create_mock_outline(self, chapter_drafts: List[ChapterDraft]) -> Dict:
        """创建模拟大纲"""
        outline = {
            "novel_name": "1627崛起南海",
            "author": "零点浪漫",
            "genre": "历史穿越、工业建设",
            "protagonist": "穿越团队",
            "core_appeal": "工业建设、强国崛起",
            "chapters": []
        }
        
        for cd in chapter_drafts:
            chapter_data = {
                "chapter_num": cd.chapter_num,
                "title": cd.chapter_title,
                "summary": cd.summary[:100],
                "sequences": [
                    {
                        "name": f"序列1",
                        "functions": ["铺垫", "发展"],
                        "emotion": "压抑→爆发",
                        "appeal_type": "建设爽点"
                    }
                ]
            }
            outline["chapters"].append(chapter_data)
        
        return outline
    
    # ==================== 完整流程 ====================
    
    def run_complete_pipeline(
        self,
        novel_path: str,
        max_chapters: int = 3,
        segment_size: int = 2000
    ):
        """运行完整流程"""
        print("\n" + "="*70)
        print("  分层大纲提取器 - 完整流程")
        print("="*70)
        
        # 第0步：加载小说
        print("\n【加载小说】")
        encodings = ['utf-8', 'gbk', 'gb2312']
        text = None
        
        for encoding in encodings:
            try:
                with open(novel_path, 'r', encoding=encoding) as f:
                    text = f.read()
                print(f"  ✓ 加载成功（{encoding}）: {len(text)}字符")
                break
            except:
                continue
        
        if not text:
            print("  ✗ 加载失败")
            return None
        
        # 第1层：章节切片
        chapters = self.split_by_chapters(text, max_chapters)
        
        # 第2层：文本分段
        segments = self.split_chapters_to_segments(chapters, segment_size)
        
        # 第3层：提取草稿
        drafts = self.extract_all_drafts(segments, max_segments=10)
        
        # 第4层：汇总草稿
        chapter_drafts = self.merge_drafts_by_chapter(drafts, chapters)
        
        # 第5层：生成完整大纲
        outline = self.generate_complete_outline(chapter_drafts)
        
        # 保存结果
        self.save_results(outline, chapter_drafts, drafts)
        
        # 打印总结
        self.print_summary(outline, chapters, segments, drafts)
        
        return outline
    
    def save_results(self, outline, chapter_drafts, drafts):
        """保存结果"""
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # 保存大纲
        with open(output_dir / "outline.json", 'w', encoding='utf-8') as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        
        # 保存章节草稿
        chapter_drafts_data = [
            {
                "chapter_num": cd.chapter_num,
                "title": cd.chapter_title,
                "summary": cd.summary,
                "segment_count": len(cd.segments)
            }
            for cd in chapter_drafts
        ]
        
        with open(output_dir / "chapter_drafts.json", 'w', encoding='utf-8') as f:
            json.dump(chapter_drafts_data, f, ensure_ascii=False, indent=2)
        
        # 保存分段草稿
        drafts_data = [
            {
                "segment_id": d.segment_id,
                "chapter_num": d.chapter_num,
                "draft_text": d.draft_text
            }
            for d in drafts
        ]
        
        with open(output_dir / "segment_drafts.json", 'w', encoding='utf-8') as f:
            json.dump(drafts_data, f, ensure_ascii=False, indent=2)
        
        # 保存Markdown格式大纲
        md_content = f"""# {outline.get('novel_name', '未知')} - L2大纲

## 基本信息
- 作者: {outline.get('author', '未知')}
- 类型: {outline.get('genre', '未知')}
- 主角: {outline.get('protagonist', '未知')}
- 核心爽点: {outline.get('core_appeal', '未知')}

## 章节大纲

"""
        for chapter in outline.get('chapters', []):
            md_content += f"""### 第{chapter['chapter_num']}章 {chapter.get('title', '')}

**概要**: {chapter.get('summary', '')}

**序列**:
"""
            for seq in chapter.get('sequences', []):
                md_content += f"- {seq.get('name', '')}\n"
                md_content += f"  - 功能: {', '.join(seq.get('functions', []))}\n"
                md_content += f"  - 情绪: {seq.get('emotion', '')}\n"
                md_content += f"  - 爽点: {seq.get('appeal_type', '')}\n"
            
            md_content += "\n"
        
        with open(output_dir / "outline.md", 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"\n✓ 结果已保存到: {output_dir}")
    
    def print_summary(self, outline, chapters, segments, drafts):
        """打印总结"""
        print("\n" + "="*70)
        print("  流程总结")
        print("="*70)
        
        print(f"\n【处理统计】")
        print(f"  章节数: {len(chapters)}")
        print(f"  分段数: {len(segments)}")
        print(f"  草稿数: {len(drafts)}")
        print(f"  草稿总字数: {sum(len(d.draft_text) for d in drafts)}字")
        
        print(f"\n【大纲信息】")
        print(f"  小说: {outline.get('novel_name')}")
        print(f"  类型: {outline.get('genre')}")
        print(f"  章节数: {len(outline.get('chapters', []))}")


def main():
    """主函数"""
    novel_path = "/home/ssjk/talk/1627崛起南海.txt"
    
    extractor = LayeredOutlineExtractor()
    
    # 运行完整流程
    # max_chapters: 处理章节上限
    # segment_size: 每段字数
    outline = extractor.run_complete_pipeline(
        novel_path,
        max_chapters=3,  # 测试时只处理3章
        segment_size=2000  # 每段2000字
    )
    
    return outline


if __name__ == "__main__":
    main()