"""
分层大纲提取器 - 简化测试版

快速测试，使用模拟草稿
"""

import re
import json
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, field

import sys
sys.path.insert(0, str(Path(__file__).parent))


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
    draft_text: str


@dataclass  
class ChapterDraft:
    """章节草稿"""
    chapter_num: int
    chapter_title: str
    segments: List[SegmentDraft] = field(default_factory=list)
    summary: str = ""


def load_and_split_chapters(novel_path: str, max_chapters: int = 3) -> List[Dict]:
    """加载并切片章节"""
    print("\n【第1层：章节切片】")
    
    # 加载小说
    for encoding in ['utf-8', 'gbk']:
        try:
            with open(novel_path, 'r', encoding=encoding) as f:
                text = f.read()
            print(f"  ✓ 加载成功: {len(text)}字符")
            break
        except:
            continue
    
    # 切片章节
    pattern = r'第(\d+)章(.+?)(?=第\d+章|$)'
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    chapters = []
    for i, match in enumerate(matches[:max_chapters]):
        chapter_num = int(match.group(1))
        title = match.group(2).strip().split('\n')[0][:30]
        content = match.group(0).strip()
        
        chapters.append({
            "chapter_num": chapter_num,
            "title": f"第{chapter_num}章 {title}",
            "content": content,
            "word_count": len(content)
        })
    
    print(f"  ✓ 切片: {len(chapters)}章")
    for c in chapters:
        print(f"    - {c['title']}: {c['word_count']}字")
    
    return chapters


def split_to_segments(chapters: List[Dict], segment_size: int = 2000) -> List[TextSegment]:
    """分段"""
    print("\n【第2层：文本分段】")
    
    segments = []
    for chapter in chapters:
        content = chapter['content']
        chapter_num = chapter['chapter_num']
        
        for i in range(0, len(content), segment_size):
            seg = TextSegment(
                segment_id=f"seg_{chapter_num}_{i//segment_size + 1}",
                chapter_num=chapter_num,
                segment_index=i//segment_size + 1,
                text=content[i:i+segment_size],
                word_count=len(content[i:i+segment_size])
            )
            segments.append(seg)
    
    print(f"  ✓ 分段: {len(segments)}段")
    print(f"  平均: {sum(s.word_count for s in segments)/len(segments):.0f}字/段")
    
    return segments


def create_mock_drafts(segments: List[TextSegment]) -> List[SegmentDraft]:
    """创建模拟草稿（避免LLM超时）"""
    print("\n【第3层：提取草稿】")
    print("  使用模拟草稿（避免LLM超时）")
    
    # 根据章节内容生成相关草稿
    draft_templates = {
        1: [
            "陶东来在机场接机，老同学宁崎到达广州。陶东来神神秘秘，暗示有事相商。",
            "陶东来介绍团队成员：颜楚杰（军人）、白克思（工厂老板）、顾凯（律师）。",
            "晚餐讨论穿越话题，宁崎从历史角度分析可行性。",
            "深夜，陶东来带宁崎到越秀山，展示虫洞控制器。",
            "团队穿越到明朝验证，宁崎看到古城墙和城门，确认是明末时期。"
        ],
        2: [
            "陶东来邀请宁崎加入穿越团队，展示虫洞控制器的剩余使用寿命。",
            "讨论穿越目标地点，确定海南岛榆林港作为主基地。",
            "分析海南岛的优劣势：煤铁资源、人口、军事压力。",
            "团队分工：陶东来负责物资，白克思负责人力，颜楚杰负责安全。",
            "宁崎负责技术资料搜集整理，建立数据库。"
        ],
        3: [
            "团队开始面试新成员，47人参加，23人决定加入。",
            "蒙贺加入团队，带来数据库和加密论坛系统。",
            "成立信息产业部，蒙贺负责IT建设。",
            "吴卓加入，成为军事技术人员，引发蒙贺和颜楚杰的争夺。",
            "团队扩大，各部门开始实质性的筹备工作。"
        ]
    }
    
    drafts = []
    for seg in segments:
        chapter_num = seg.chapter_num
        templates = draft_templates.get(chapter_num, ["章节内容发展"])
        template = templates[min(seg.segment_index - 1, len(templates) - 1)]
        
        draft = SegmentDraft(
            segment_id=seg.segment_id,
            chapter_num=chapter_num,
            draft_text=template
        )
        drafts.append(draft)
    
    print(f"  ✓ 草稿: {len(drafts)}个")
    print(f"  总字数: {sum(len(d.draft_text) for d in drafts)}字")
    
    for i, d in enumerate(drafts[:5], 1):
        print(f"    {i}. {d.draft_text[:40]}...")
    
    return drafts


def merge_drafts(drafts: List[SegmentDraft], chapters: List[Dict]) -> List[ChapterDraft]:
    """按章节合并草稿"""
    print("\n【第4层：汇总草稿】")
    
    chapter_drafts = []
    
    for chapter in chapters:
        chapter_num = chapter['chapter_num']
        
        # 该章节的所有草稿
        seg_drafts = [d for d in drafts if d.chapter_num == chapter_num]
        
        if not seg_drafts:
            continue
        
        # 合并
        merged = "\n".join(d.draft_text for d in seg_drafts)
        
        cd = ChapterDraft(
            chapter_num=chapter_num,
            chapter_title=chapter['title'],
            segments=seg_drafts,
            summary=merged
        )
        
        chapter_drafts.append(cd)
    
    print(f"  ✓ 汇总: {len(chapter_drafts)}章")
    
    return chapter_drafts


def generate_outline(chapter_drafts: List[ChapterDraft]) -> Dict:
    """生成完整大纲"""
    print("\n【第5层：生成大纲】")
    
    outline = {
        "novel_name": "1627崛起南海",
        "author": "零点浪漫",
        "genre": "历史穿越、工业建设",
        "protagonist": "穿越团队",
        "core_appeal": "工业建设、强国崛起",
        "chapters": []
    }
    
    for cd in chapter_drafts:
        # 从草稿提取序列
        sequences = extract_sequences_from_draft(cd)
        
        chapter_data = {
            "chapter_num": cd.chapter_num,
            "title": cd.chapter_title,
            "summary": cd.summary[:150],
            "sequences": sequences
        }
        
        outline["chapters"].append(chapter_data)
    
    print(f"  ✓ 大纲: {len(outline['chapters'])}章")
    
    return outline


def extract_sequences_from_draft(chapter_draft: ChapterDraft) -> List[Dict]:
    """从草稿提取序列"""
    
    # 基于章节号和草稿内容的规则提取
    sequence_rules = {
        1: [
            {
                "name": "穿越团队招募",
                "functions": ["接机会面", "团队介绍", "穿越验证"],
                "emotion": "好奇→震惊→相信",
                "appeal_type": "开篇钩子"
            }
        ],
        2: [
            {
                "name": "团队分工筹备",
                "functions": ["确定目标", "资源分析", "分工合作"],
                "emotion": "决心→规划→行动",
                "appeal_type": "建设准备"
            }
        ],
        3: [
            {
                "name": "团队扩大建设",
                "functions": ["面试招募", "部门成立", "系统建设"],
                "emotion": "困难→突破→扩展",
                "appeal_type": "团队成长"
            }
        ]
    }
    
    return sequence_rules.get(chapter_draft.chapter_num, [])


def save_results(outline: Dict, chapter_drafts: List[ChapterDraft], segments: List[TextSegment]):
    """保存结果"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # JSON大纲
    with open(output_dir / "outline.json", 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    
    # Markdown大纲
    md = f"""# {outline['novel_name']} - L2大纲

## 基本信息
- 作者: {outline['author']}
- 类型: {outline['genre']}
- 主角: {outline['protagonist']}
- 核心爽点: {outline['core_appeal']}

## 章节大纲

"""
    for chapter in outline['chapters']:
        md += f"""### {chapter['title']}

**概要**: {chapter['summary']}

**序列**:
"""
        for seq in chapter['sequences']:
            md += f"- **{seq['name']}**\n"
            md += f"  - 功能: {' → '.join(seq['functions'])}\n"
            md += f"  - 情绪: {seq['emotion']}\n"
            md += f"  - 爽点: {seq['appeal_type']}\n"
        
        md += "\n---\n\n"
    
    with open(output_dir / "outline.md", 'w', encoding='utf-8') as f:
        f.write(md)
    
    # 草稿文件
    drafts_data = [
        {
            "segment_id": d.segment_id,
            "chapter": d.chapter_num,
            "draft": d.draft_text
        }
        for d in chapter_drafts[0].segments if chapter_drafts
    ]
    
    with open(output_dir / "drafts.json", 'w', encoding='utf-8') as f:
        json.dump(drafts_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 已保存到: {output_dir}")


def main():
    """主流程"""
    print("\n" + "="*70)
    print("  分层大纲提取器 - 简化测试")
    print("="*70)
    
    novel_path = "/home/ssjk/talk/1627崛起南海.txt"
    
    # 第1层：章节切片
    chapters = load_and_split_chapters(novel_path, max_chapters=3)
    
    # 第2层：文本分段
    segments = split_to_segments(chapters, segment_size=2000)
    
    # 第3层：提取草稿（模拟）
    drafts = create_mock_drafts(segments)
    
    # 第4层：汇总
    chapter_drafts = merge_drafts(drafts, chapters)
    
    # 第5层：生成大纲
    outline = generate_outline(chapter_drafts)
    
    # 保存
    save_results(outline, chapter_drafts, segments)
    
    # 总结
    print("\n" + "="*70)
    print("  流程总结")
    print("="*70)
    print(f"\n  章节数: {len(chapters)}")
    print(f"  分段数: {len(segments)}")
    print(f"  草稿数: {len(drafts)}")
    print(f"  大纲章节数: {len(outline['chapters'])}")
    
    print("\n【章节草稿预览】")
    for cd in chapter_drafts:
        print(f"\n  第{cd.chapter_num}章: {len(cd.segments)}段草稿")
        print(f"  概要: {cd.summary[:80]}...")
    
    print("\n" + "="*70)
    print("  ✅ 完成")
    print("="*70)


if __name__ == "__main__":
    main()