"""
步骤1：章节切片

【功能】
从小说全文中按"第X章"标题切分出独立章节

【输入输出】
输入: 小说文件 (如 都市剑说.txt)
输出: 
  - chapter_0001.txt ~ chapter_0300.txt (章节文件)
  - index.json (章节索引)

【切分逻辑】
正则匹配: "第X章 标题" 或 "第X节 标题"
支持中文数字和阿拉伯数字

【用法】
python steps/step1_split_chapters.py 小说.txt --output output/01_chapters --max 100
"""

import re
import json
import argparse
from pathlib import Path


def split_chapters(text: str, max_chapters: int = None):
    """
    切分章节
    
    【匹配规则】
    正则: 第(\d+)(章|节)(.+?)(?=第\d+(章|节)|$)
    - 第(\d+)     : 匹配章节号
    - (章|节)     : 匹配单位
    - (.+?)       : 匹配标题和内容（非贪婪）
    - (?=第\d+)   : 正向预查，遇到下一章停止
    
    【返回格式】
    [
        {
            "num": 1,
            "title": "第一章 穿越归来",
            "content": "完整章节内容...",
            "word_count": 3500
        },
        ...
    ]
    """
    # 正则匹配 "第X章" 或 "第X节"
    pattern = r'第(\d+)(章|节)(.+?)(?=第\d+(章|节)|$)'
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    # 限制章节数（用于测试）
    if max_chapters:
        matches = matches[:max_chapters]
    
    chapters = []
    for match in matches:
        num = int(match.group(1))          # 章节号: 1, 2, 3...
        unit = match.group(2)              # 单位: "章" 或 "节"
        title = match.group(3).strip().split('\n')[0][:30]  # 标题（取第一行，限30字）
        content = match.group(0).strip()   # 完整内容（含标题）
        
        chapters.append({
            "num": num,
            "title": f"第{num}{unit} {title}",
            "content": content,
            "word_count": len(content)
        })
    
    return chapters


def save_chapters(chapters: list, output_dir: Path):
    """
    保存章节到文件
    
    【目录结构】
    output/01_chapters/
    ├── chapter_0001.txt
    ├── chapter_0002.txt
    ├── ...
    └── index.json
    
    【index.json格式】
    [
        {"num": 1, "title": "...", "word_count": 3500},
        ...
    ]
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存每章到独立文件
    for ch in chapters:
        filepath = output_dir / f"chapter_{ch['num']:04d}.txt"
        filepath.write_text(ch['content'], encoding='utf-8')
    
    # 保存索引文件（用于快速查询）
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
    parser.add_argument('--max', '-m', type=int, help='最大章节数（用于测试）')
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("步骤1：章节切片")
    print("="*50)
    
    # 读取小说（尝试多种编码）
    print(f"\n读取小说: {args.novel}")
    for encoding in ['utf-8', 'gbk', 'gb2312']:
        try:
            text = Path(args.novel).read_text(encoding=encoding)
            print(f"  ✓ 加载成功: {len(text):,}字符 (编码: {encoding})")
            break
        except:
            continue
    else:
        print("  ✗ 加载失败：不支持的编码")
        return
    
    # 切分章节
    print(f"\n切分章节...")
    chapters = split_chapters(text, args.max)
    print(f"  ✓ 找到 {len(chapters)} 章")
    
    # 统计信息
    total_words = sum(ch['word_count'] for ch in chapters)
    avg_words = total_words / len(chapters) if chapters else 0
    print(f"  总字数: {total_words:,}")
    print(f"  平均每章: {avg_words:.0f}字")
    
    # 保存文件
    output_dir = Path(args.output)
    save_chapters(chapters, output_dir)
    print(f"\n✓ 保存到: {output_dir}/")


if __name__ == "__main__":
    main()