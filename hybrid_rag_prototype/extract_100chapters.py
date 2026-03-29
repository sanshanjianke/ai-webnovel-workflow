"""
分层大纲提取器 - 100章版本（修正版）

流程：
1. 100章文本按5-10章切分成序列
2. 序列提交给LLM生成草稿
3. 草稿按50-100kb汇聚成序列
4. 提交给LLM处理成L2格式
"""

import re
import json
import time
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, field

import sys
sys.path.insert(0, str(Path(__file__).parent))

from utils import create_llm


@dataclass
class ChapterSequence:
    """章节序列（5-10章）"""
    seq_id: int
    start_chapter: int
    end_chapter: int
    chapters: List[Dict]
    total_words: int = 0


@dataclass
class DraftSequence:
    """草稿序列"""
    seq_id: int
    draft_text: str
    char_count: int


@dataclass
class MergedBlock:
    """汇聚块（50-100kb）"""
    block_id: int
    sequences: List[DraftSequence]
    merged_text: str
    char_count: int


class LayeredExtractor100:
    """分层大纲提取器（100章版本）"""
    
    def __init__(self, output_dir: str = "output_100chapters_v2"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        (self.output_dir / "01_chapters").mkdir(exist_ok=True)
        (self.output_dir / "02_sequences").mkdir(exist_ok=True)
        (self.output_dir / "03_drafts").mkdir(exist_ok=True)
        (self.output_dir / "04_merged_blocks").mkdir(exist_ok=True)
        (self.output_dir / "05_outline").mkdir(exist_ok=True)
        
        self.llm = None
        self.chapters = []
        self.sequences = []
        self.drafts = []
        self.merged_blocks = []
        self.final_outline = None
    
    def run(self, novel_path: str, max_chapters: int = 100, 
            chapters_per_seq: int = 7, merge_size_kb: int = 70):
        """
        运行完整流程
        
        Args:
            novel_path: 小说文件路径
            max_chapters: 最大章节数
            chapters_per_seq: 每个序列包含的章节数（默认7，范围5-10）
            merge_size_kb: 汇聚块大小KB（默认70，范围50-100）
        """
        print("\n" + "="*70)
        print(f"  分层大纲提取器 - {max_chapters}章版本")
        print("="*70)
        print(f"  参数: 每序列{chapters_per_seq}章, 汇聚块{merge_size_kb}KB")
        
        start_time = time.time()
        
        # 初始化LLM
        print("\n【初始化LLM】")
        self.llm = create_llm(temperature=0.3)
        if not self.llm:
            print("  ✗ LLM初始化失败")
            return None
        print("  ✓ LLM初始化成功")
        
        # 第0步：加载小说
        print("\n【加载小说】")
        text = self._load_novel(novel_path)
        if not text:
            return None
        
        # 第1步：章节切片
        self.chapters = self._split_chapters(text, max_chapters)
        self._save_chapters()
        
        # 第2步：按5-10章切分成序列
        self.sequences = self._create_sequences(chapters_per_seq)
        self._save_sequences()
        
        # 第3步：LLM生成草稿
        self.drafts = self._generate_drafts()
        self._save_drafts()
        
        # 第4步：按50-100kb汇聚草稿
        self.merged_blocks = self._merge_drafts(merge_size_kb * 1024)
        self._save_merged_blocks()
        
        # 第5步：LLM生成L2大纲
        self.final_outline = self._generate_l2_outline()
        self._save_outline()
        
        elapsed = time.time() - start_time
        self._print_summary(elapsed)
        
        return self.final_outline
    
    def _load_novel(self, novel_path: str) -> str:
        """加载小说"""
        for encoding in ['utf-8', 'gbk', 'gb2312']:
            try:
                with open(novel_path, 'r', encoding=encoding) as f:
                    text = f.read()
                print(f"  ✓ 加载成功: {len(text):,}字符")
                return text
            except:
                continue
        print("  ✗ 加载失败")
        return None
    
    def _split_chapters(self, text: str, max_chapters: int) -> List[Dict]:
        """切片章节"""
        print("\n【第1步：章节切片】")
        
        # 支持 "第X章" 和 "第X节" 两种格式
        pattern = r'第(\d+)(章|节)(.+?)(?=第\d+(章|节)|$)'
        matches = list(re.finditer(pattern, text, re.DOTALL))
        
        print(f"  找到章节: {len(matches)}章")
        print(f"  处理章节: 前{max_chapters}章")
        
        chapters = []
        for i, match in enumerate(matches[:max_chapters]):
            chapter_num = int(match.group(1))
            unit = match.group(2)  # 章 或 节
            title = match.group(3).strip().split('\n')[0][:30]
            content = match.group(0).strip()
            
            chapters.append({
                "chapter_num": chapter_num,
                "title": f"第{chapter_num}{unit} {title}",
                "content": content,
                "word_count": len(content)
            })
        
        total_words = sum(c['word_count'] for c in chapters)
        avg_words = total_words / len(chapters) if chapters else 0
        
        print(f"  ✓ 切片完成: {len(chapters)}章")
        print(f"  总字数: {total_words:,}字")
        print(f"  平均每章: {avg_words:.0f}字")
        
        return chapters
    
    def _save_chapters(self):
        """保存章节"""
        for c in self.chapters:
            filepath = self.output_dir / "01_chapters" / f"chapter_{c['chapter_num']:04d}.txt"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(c['content'])
        
        index = [{"chapter_num": c['chapter_num'], "title": c['title'], 
                  "word_count": c['word_count']} for c in self.chapters]
        with open(self.output_dir / "01_chapters" / "index.json", 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 章节已保存: {len(self.chapters)}章")
    
    def _create_sequences(self, chapters_per_seq: int) -> List[ChapterSequence]:
        """按5-10章切分成序列"""
        print(f"\n【第2步：创建章节序列】")
        print(f"  每序列章节数: {chapters_per_seq}章")
        
        sequences = []
        total_chapters = len(self.chapters)
        
        for i in range(0, total_chapters, chapters_per_seq):
            end_idx = min(i + chapters_per_seq, total_chapters)
            seq_chapters = self.chapters[i:end_idx]
            
            seq = ChapterSequence(
                seq_id=len(sequences) + 1,
                start_chapter=seq_chapters[0]['chapter_num'],
                end_chapter=seq_chapters[-1]['chapter_num'],
                chapters=seq_chapters,
                total_words=sum(c['word_count'] for c in seq_chapters)
            )
            sequences.append(seq)
        
        print(f"  ✓ 序列创建完成: {len(sequences)}个")
        for seq in sequences[:3]:
            print(f"    序列{seq.seq_id}: 第{seq.start_chapter}-{seq.end_chapter}章 ({seq.total_words:,}字)")
        if len(sequences) > 3:
            print(f"    ... 共{len(sequences)}个序列")
        
        return sequences
    
    def _save_sequences(self):
        """保存序列"""
        for seq in self.sequences:
            filepath = self.output_dir / "02_sequences" / f"sequence_{seq.seq_id:02d}.txt"
            content = "\n\n".join([
                f"【{c['title']}】\n{c['content']}" 
                for c in seq.chapters
            ])
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        index = [{
            "seq_id": s.seq_id,
            "chapters": f"{s.start_chapter}-{s.end_chapter}",
            "word_count": s.total_words
        } for s in self.sequences]
        with open(self.output_dir / "02_sequences" / "index.json", 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 序列已保存: {len(self.sequences)}个")
    
    def _generate_drafts(self) -> List[DraftSequence]:
        """LLM生成草稿"""
        print(f"\n【第3步：LLM生成草稿】")
        
        drafts = []
        
        # 检查是否已有草稿（断点续传）
        draft_dir = self.output_dir / "03_drafts"
        existing_drafts = {}
        for f in draft_dir.glob("draft_*.txt"):
            seq_id = int(f.stem.split("_")[1])
            content = f.read_text(encoding='utf-8')
            if not content.startswith("[生成失败"):
                existing_drafts[seq_id] = content
                print(f"  已加载草稿: 序列{seq_id}")
        
        if existing_drafts:
            print(f"  发现已有草稿: {len(existing_drafts)}个，将跳过")
        
        prompt_template = """你是一个专业的网文编辑。请将以下章节内容缩减为草稿版本。

要求：
1. 输出总字数约5000字（7章合计），每章约700字
2. 保留：人物性格特征、话语模式、关键对话原文、事件细节、决策过程、冲突结果、设定、伏笔
3. 删除：过于冗长的环境描写、无关的过渡段落
4. 保持连贯：缩减后剧情逻辑完整，人物形象鲜明

章节内容：
{content}

直接输出缩减后的文本，每章用【第X章】分隔。确保总字数约5000字。"""

        for i, seq in enumerate(self.sequences):
            if seq.seq_id in existing_drafts:
                draft = DraftSequence(
                    seq_id=seq.seq_id,
                    draft_text=existing_drafts[seq.seq_id],
                    char_count=len(existing_drafts[seq.seq_id])
                )
                drafts.append(draft)
                continue
            
            print(f"  处理序列 {i+1}/{len(self.sequences)}: 第{seq.start_chapter}-{seq.end_chapter}章...")
            
            seq_content = "\n".join([
                f"【{c['title']}】\n{c['content'][:3000]}" 
                for c in seq.chapters
            ])
            
            prompt = prompt_template.format(content=seq_content)
            
            try:
                response = self.llm.invoke(prompt)
                draft_text = response.content
                
                draft = DraftSequence(
                    seq_id=seq.seq_id,
                    draft_text=draft_text,
                    char_count=len(draft_text)
                )
                drafts.append(draft)
                
                filepath = self.output_dir / "03_drafts" / f"draft_{seq.seq_id:02d}.txt"
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(draft_text)
                
                print(f"    ✓ 完成: {draft.char_count}字")
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    ✗ 失败: {e}")
                draft = DraftSequence(
                    seq_id=seq.seq_id,
                    draft_text=f"[生成失败: {e}]",
                    char_count=0
                )
                drafts.append(draft)
        
        total_chars = sum(d.char_count for d in drafts)
        print(f"  ✓ 草稿生成完成: {len(drafts)}个, 共{total_chars:,}字")
        
        return drafts
    
    def _save_drafts(self):
        """保存草稿"""
        for draft in self.drafts:
            filepath = self.output_dir / "03_drafts" / f"draft_{draft.seq_id:02d}.txt"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(draft.draft_text)
        
        index = [{
            "seq_id": d.seq_id,
            "char_count": d.char_count
        } for d in self.drafts]
        with open(self.output_dir / "03_drafts" / "index.json", 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 草稿已保存: {len(self.drafts)}个")
    
    def _merge_drafts(self, target_size: int) -> List[MergedBlock]:
        """按50KB分割草稿为多个块"""
        print(f"\n【第4步：分割草稿块】")
        print(f"  目标块大小: {target_size//1024}KB")
        
        blocks = []
        all_text = ""
        current_seqs = []
        current_size = 0
        
        for draft in self.drafts:
            # 如果当前块加上新草稿超过目标大小，且当前块不为空
            if current_size + draft.char_count > target_size and current_seqs:
                # 保存当前块
                block = MergedBlock(
                    block_id=len(blocks) + 1,
                    sequences=current_seqs,
                    merged_text=all_text,
                    char_count=current_size
                )
                blocks.append(block)
                print(f"    块{block.block_id}: {block.char_count//1024}KB")
                
                # 重置
                all_text = ""
                current_seqs = []
                current_size = 0
            
            all_text += f"\n\n{draft.draft_text}"
            current_seqs.append(draft)
            current_size += draft.char_count
        
        # 处理剩余内容
        if current_seqs:
            block = MergedBlock(
                block_id=len(blocks) + 1,
                sequences=current_seqs,
                merged_text=all_text,
                char_count=current_size
            )
            blocks.append(block)
            print(f"    块{block.block_id}: {block.char_count//1024}KB")
        
        print(f"  ✓ 分割完成: {len(blocks)}个块")
        return blocks
    
    def _save_merged_blocks(self):
        """保存汇聚块"""
        for block in self.merged_blocks:
            filepath = self.output_dir / "04_merged_blocks" / f"block_{block.block_id:02d}.txt"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(block.merged_text)
        
        index = [{
            "block_id": b.block_id,
            "char_count": b.char_count,
            "sequences": [s.seq_id for s in b.sequences]
        } for b in self.merged_blocks]
        with open(self.output_dir / "04_merged_blocks" / "index.json", 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 汇聚块已保存: {len(self.merged_blocks)}个")
    
    def _generate_l2_outline(self) -> Dict:
        """LLM生成L2格式大纲 - 按150KB递交，前后各50KB做上下文"""
        print(f"\n【第5步：LLM生成L2大纲】")
        
        context_size = 50 * 1024  # 50KB上下文
        focus_size = 50 * 1024    # 50KB重点处理
        
        # 合并所有块文本
        all_text = ""
        for block in self.merged_blocks:
            all_text += block.merged_text + "\n\n"
        
        total_size = len(all_text)
        print(f"  总文本: {total_size//1024}KB")
        
        all_chapters = []
        processed = 0
        
        # 滑动窗口处理，每次移动50KB
        start = 0
        while start < total_size:
            # 窗口范围：前50KB + 中间50KB + 后50KB = 150KB
            window_start = max(0, start - context_size)
            window_end = min(total_size, start + focus_size + context_size)
            
            window_text = all_text[window_start:window_end]
            
            # 构建prompt，明确区分上下文和重点区域
            if start == 0:
                # 第一段，没有前文
                prompt = f"""你是一个专业的网文大纲编辑。请为以下内容生成L2格式大纲。

重点关注区域（开头部分）：
{window_text[:focus_size]}

后续背景：
{window_text[focus_size:]}

请为重点关注区域生成详细的大纲，包含：
1. 每章标题
2. 摘要（1-2句话）
3. 序列信息（名称、功能类型、情绪走向、爽点类型）

输出JSON格式：
{{"chapters": [{{"chapter_num": 1, "title": "...", "summary": "...", "sequences": [{{"name": "...", "functions": [], "emotion": "...", "appeal_type": "..."}}]}}]}}"""
            else:
                # 中间段，有前后文
                context_before = all_text[max(0, start - context_size):start]
                focus_text = all_text[start:start + focus_size]
                context_after = all_text[start + focus_size:start + focus_size + context_size]
                
                prompt = f"""你是一个专业的网文大纲编辑。请为以下内容生成L2格式大纲。

【前文背景】：
{context_before}

【重点关注区域】：
{focus_text}

【后续背景】：
{context_after}

请为重点关注区域生成详细的大纲，注意与前文和后文的连贯性。

输出JSON格式：
{{"chapters": [{{"chapter_num": N, "title": "...", "summary": "...", "sequences": [{{"name": "...", "functions": [], "emotion": "...", "appeal_type": "..."}}]}}]}}"""
            
            print(f"  处理位置 {start//1024}KB/{total_size//1024}KB...")
            
            try:
                response = self.llm.invoke(prompt)
                content = response.content
                
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    try:
                        block_outline = json.loads(json_match.group())
                        if 'chapters' in block_outline:
                            all_chapters.extend(block_outline['chapters'])
                            print(f"    ✓ 累计章节: {len(all_chapters)}章")
                    except json.JSONDecodeError:
                        print(f"    ⚠ JSON解析失败")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"    ✗ 失败: {e}")
            
            # 移动窗口
            start += focus_size
        
        outline = {
            "novel_name": "都市剑说",
            "author": "未知",
            "genre": "都市修仙",
            "total_chapters": len(all_chapters),
            "chapters": all_chapters
        }
        
        print(f"  ✓ L2大纲生成完成: {len(all_chapters)}章")
        return outline
    
    def _save_outline(self):
        """保存最终大纲"""
        if not self.final_outline:
            print("  ✗ 无大纲数据")
            return
        
        json_path = self.output_dir / "05_outline" / "outline.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.final_outline, f, ensure_ascii=False, indent=2)
        print(f"  ✓ JSON保存: {json_path}")
        
        md_lines = [f"# {self.final_outline.get('novel_name', '未命名')} - L2大纲\n"]
        md_lines.append(f"作者: {self.final_outline.get('author', '未知')}")
        md_lines.append(f"类型: {self.final_outline.get('genre', '未知')}")
        md_lines.append(f"总章节: {self.final_outline.get('total_chapters', 0)}章\n")
        
        chapters = self.final_outline.get('chapters', [])
        for ch in chapters:
            md_lines.append(f"## {ch.get('title', '未知章节')}")
            md_lines.append(f"{ch.get('summary', '无摘要')}\n")
            
            for seq in ch.get('sequences', []):
                md_lines.append(f"- 序列: {seq.get('name', '未知')}")
                md_lines.append(f"  - 功能: {', '.join(seq.get('functions', []))}")
                md_lines.append(f"  - 情绪: {seq.get('emotion', '未知')}")
                md_lines.append(f"  - 爽点: {seq.get('appeal_type', '未知')}")
            md_lines.append("")
        
        md_path = self.output_dir / "05_outline" / "outline.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        print(f"  ✓ Markdown保存: {md_path}")
    
    def _print_summary(self, elapsed: float):
        """打印总结"""
        print("\n" + "="*70)
        print("  处理完成")
        print("="*70)
        
        print(f"\n【统计信息】")
        print(f"  原始章节: {len(self.chapters)}章")
        print(f"  章节序列: {len(self.sequences)}个")
        print(f"  草稿序列: {len(self.drafts)}个")
        print(f"  汇聚块: {len(self.merged_blocks)}个")
        print(f"  最终章节: {len(self.final_outline.get('chapters', [])) if self.final_outline else 0}章")
        print(f"  耗时: {elapsed:.1f}秒")
        
        print(f"\n【输出目录】")
        print(f"  {self.output_dir}/")
        print(f"  ├── 01_chapters/      # 章节原文")
        print(f"  ├── 02_sequences/     # 章节序列")
        print(f"  ├── 03_drafts/        # 草稿序列")
        print(f"  ├── 04_merged_blocks/ # 汇聚块")
        print(f"  └── 05_outline/       # L2大纲")


if __name__ == "__main__":
    extractor = LayeredExtractor100(output_dir="output_dsjianshuo")
    
    novel_path = "/home/ssjk/talk/都市剑说.txt"
    
    outline = extractor.run(
        novel_path=novel_path,
        max_chapters=100,
        chapters_per_seq=7,
        merge_size_kb=70
    )
    
    if outline:
        print("\n处理完成！")
    else:
        print("\n处理失败！")