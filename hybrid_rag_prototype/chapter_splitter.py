"""
小说章节切片器

使用正则表达式按章节切片小说
"""

import re
from pathlib import Path
from typing import List, Dict
import json


class ChapterSplitter:
    """章节切片器"""
    
    def __init__(self, novel_path: str):
        self.novel_path = Path(novel_path)
        self.chapters = []
        
    def load_novel(self) -> str:
        """加载小说文本"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
        
        for encoding in encodings:
            try:
                with open(self.novel_path, 'r', encoding=encoding) as f:
                    text = f.read()
                print(f"✓ 小说加载成功（编码: {encoding}）")
                print(f"  总字符数: {len(text)}")
                return text
            except:
                continue
        
        raise Exception("无法读取小说文件")
    
    def split_by_chapters(self, text: str, max_chapters: int = None) -> List[Dict]:
        """
        按章节切片
        
        Args:
            text: 小说文本
            max_chapters: 最大切片章节数（用于测试）
        
        Returns:
            章节列表
        """
        print("\n【章节切片】")
        
        # 正则表达式匹配章节标题
        # 格式：第X章XXX
        chapter_pattern = r'第(\d+)章(.+?)(?=第\d+章|$)'
        
        # 查找所有章节
        matches = list(re.finditer(chapter_pattern, text, re.DOTALL))
        
        print(f"  找到章节数: {len(matches)}")
        
        # 提取章节内容
        chapters = []
        for i, match in enumerate(matches):
            if max_chapters and i >= max_chapters:
                break
            
            chapter_num = match.group(1)
            chapter_title = match.group(2).strip()
            chapter_content = match.group(0)
            
            # 清理内容
            chapter_content = chapter_content.strip()
            
            chapter = {
                "chapter_id": f"chapter_{chapter_num}",
                "chapter_num": int(chapter_num),
                "title": f"第{chapter_num}章 {chapter_title}",
                "content": chapter_content,
                "word_count": len(chapter_content)
            }
            
            chapters.append(chapter)
        
        self.chapters = chapters
        
        print(f"  切片完成: {len(chapters)}章")
        
        return chapters
    
    def analyze_chapters(self, chapters: List[Dict]):
        """分析章节统计"""
        print("\n【章节统计】")
        
        if not chapters:
            print("  无章节数据")
            return
        
        total_words = sum(c['word_count'] for c in chapters)
        avg_words = total_words / len(chapters)
        min_words = min(c['word_count'] for c in chapters)
        max_words = max(c['word_count'] for c in chapters)
        
        print(f"  总章节数: {len(chapters)}")
        print(f"  总字数: {total_words}")
        print(f"  平均每章: {avg_words:.0f}字")
        print(f"  最短章节: {min_words}字")
        print(f"  最长章节: {max_words}字")
        
        print("\n【前10章预览】")
        for c in chapters[:10]:
            print(f"  {c['title']}: {c['word_count']}字")
    
    def save_chapters(self, output_dir: str = "output/chapters"):
        """保存章节到文件"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"\n【保存章节】")
        
        for chapter in self.chapters:
            # 保存为单独的文本文件
            filename = f"{chapter['chapter_id']}.txt"
            filepath = output_path / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(chapter['content'])
        
        print(f"  ✓ 保存{len(self.chapters)}个章节到: {output_path}")
        
        # 保存章节索引
        index_data = [
            {
                "chapter_id": c['chapter_id'],
                "chapter_num": c['chapter_num'],
                "title": c['title'],
                "word_count": c['word_count']
            }
            for c in self.chapters
        ]
        
        index_file = output_path / "chapter_index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 章节索引: {index_file}")
    
    def extract_first_n_chapters(self, n: int = 3) -> str:
        """提取前N章的文本（用于LLM分析）"""
        if not self.chapters:
            return ""
        
        text = ""
        for chapter in self.chapters[:n]:
            text += chapter['content'] + "\n\n"
        
        return text


def test_chapter_splitter():
    """测试章节切片器"""
    print("\n" + "="*70)
    print("  小说章节切片器测试")
    print("="*70)
    
    # 初始化
    novel_path = "/home/ssjk/talk/1627崛起南海.txt"
    splitter = ChapterSplitter(novel_path)
    
    # 加载小说
    print("\n【步骤1】加载小说")
    text = splitter.load_novel()
    
    # 切片章节（测试用，只切片前10章）
    print("\n【步骤2】切片章节")
    chapters = splitter.split_by_chapters(text, max_chapters=10)
    
    # 分析统计
    splitter.analyze_chapters(chapters)
    
    # 保存章节
    print("\n【步骤3】保存章节")
    splitter.save_chapters("output/chapters")
    
    # 提取前3章用于后续分析
    print("\n【步骤4】提取前3章文本")
    first_3_chapters = splitter.extract_first_n_chapters(3)
    print(f"  ✓ 前3章文本长度: {len(first_3_chapters)}字符")
    
    # 保存前3章文本
    with open("output/first_3_chapters.txt", 'w', encoding='utf-8') as f:
        f.write(first_3_chapters)
    print(f"  ✓ 保存到: output/first_3_chapters.txt")
    
    return chapters, first_3_chapters


if __name__ == "__main__":
    test_chapter_splitter()