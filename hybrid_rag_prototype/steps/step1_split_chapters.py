"""
步骤1：章节切片

功能：从小说文本中切分出章节

输入：小说文件路径
输出：output/01_chapters/*.txt

用法：
    python steps/step1_split_chapters.py 小说.txt --output output --max 100
"""

import re
import json
import argparse
from pathlib import Path


def split_chapters(text: str, max_chapters: int = None):
    """
    切分章节
    
    支持 "第X章" 和 "第X节" 两种格式
    
    Args:
        text: 小说全文
        max_chapters: 最大章节数，None表示全部
    
    Returns:
        章节列表: [{"num": 1, "title": "...", "content": "..."}]
    """
    # 正则匹配 "第X章" 或 "第X节"
    pattern = r'第(\d+)(章|节)(.+?)(?=第\d+(章|节)|$)'
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    if max_chapters:
        matches = matches[:max_chapters]
    
    chapters = []
    for match in matches:
        num = int(match.group(1))          # 章节号
        unit = match.group(2)              # "章" 或 "节"
        title = match.group(3).strip().split('\n')[0][:30]  # 标题
        content = match.group(0).strip()   # 完整内容
        
        chapters.append({
            "num": num,
            "title": f"第{num}{unit} {title}",
            "content": content,
            "word_count": len(content)
        })
    
    return chapters


def save_chapters(chapters: list, output_dir: Path):
    """保存章节到文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存每章
    for ch in chapters:
        filepath = output_dir / f"chapter_{ch['num']:04d}.txt"
        filepath.write_text(ch['content'], encoding='utf-8')
    
    # 保存索引
    index = [{
        "num": ch['num'],
        "title": ch['title'],
        "word_count": ch['word_count']
    } for ch in chapters]
    
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def main():
    parser = argparse.ArgumentParser(description='步骤1：章节切片')
    parser.add_argument('novel', help='小说文件路径')
    parser.add_argument('--output', '-o', default='output/01_chapters', help='输出目录')
    parser.add_argument('--max', '-m', type=int, help='最大章节数')
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("步骤1：章节切片")
    print("="*50)
    
    # 读取小说
    print(f"\n读取小说: {args.novel}")
    for encoding in ['utf-8', 'gbk', 'gb2312']:
        try:
            text = Path(args.novel).read_text(encoding=encoding)
            print(f"  ✓ 加载成功: {len(text):,}字符")
            break
        except:
            continue
    else:
        print("  ✗ 加载失败")
        return
    
    # 切分章节
    print(f"\n切分章节...")
    chapters = split_chapters(text, args.max)
    print(f"  ✓ 找到 {len(chapters)} 章")
    
    # 统计
    total_words = sum(ch['word_count'] for ch in chapters)
    avg_words = total_words / len(chapters) if chapters else 0
    print(f"  总字数: {total_words:,}")
    print(f"  平均每章: {avg_words:.0f}字")
    
    # 保存
    output_dir = Path(args.output)
    save_chapters(chapters, output_dir)
    print(f"\n✓ 保存到: {output_dir}/")


if __name__ == "__main__":
    main()