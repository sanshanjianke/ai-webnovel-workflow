"""
步骤2：序列分组

功能：将章节按固定数量分组

输入：output/01_chapters/
输出：output/02_sequences/

用法：
    python steps/step2_create_sequences.py --input output/01_chapters --output output/02_sequences --size 7
"""

import json
import argparse
from pathlib import Path


def load_chapters(input_dir: Path):
    """加载章节"""
    index_file = input_dir / "index.json"
    if not index_file.exists():
        print(f"  ✗ 找不到索引文件: {index_file}")
        return []
    
    index = json.loads(index_file.read_text(encoding='utf-8'))
    
    chapters = []
    for item in index:
        chapter_file = input_dir / f"chapter_{item['num']:04d}.txt"
        if chapter_file.exists():
            content = chapter_file.read_text(encoding='utf-8')
            chapters.append({
                "num": item['num'],
                "title": item['title'],
                "content": content,
                "word_count": len(content)
            })
    
    return chapters


def create_sequences(chapters: list, size: int = 7):
    """
    将章节按固定数量分组
    
    Args:
        chapters: 章节列表
        size: 每组章节数
    
    Returns:
        序列列表: [{"seq_id": 1, "chapters": [...], "text": "..."}]
    """
    sequences = []
    
    for i in range(0, len(chapters), size):
        seq_chapters = chapters[i:i+size]
        
        # 合并章节文本
        text = "\n\n".join([
            f"【{ch['title']}】\n{ch['content']}"
            for ch in seq_chapters
        ])
        
        sequences.append({
            "seq_id": len(sequences) + 1,
            "start": seq_chapters[0]['num'],
            "end": seq_chapters[-1]['num'],
            "chapters": [ch['num'] for ch in seq_chapters],
            "word_count": len(text),
            "text": text
        })
    
    return sequences


def save_sequences(sequences: list, output_dir: Path):
    """保存序列"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存每个序列
    for seq in sequences:
        filepath = output_dir / f"sequence_{seq['seq_id']:02d}.txt"
        filepath.write_text(seq['text'], encoding='utf-8')
    
    # 保存索引（不包含text，节省空间）
    index = [{
        "seq_id": seq['seq_id'],
        "start": seq['start'],
        "end": seq['end'],
        "chapters": seq['chapters'],
        "word_count": seq['word_count']
    } for seq in sequences]
    
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def main():
    parser = argparse.ArgumentParser(description='步骤2：序列分组')
    parser.add_argument('--input', '-i', default='output/01_chapters', help='输入目录')
    parser.add_argument('--output', '-o', default='output/02_sequences', help='输出目录')
    parser.add_argument('--size', '-s', type=int, default=7, help='每组章节数')
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("步骤2：序列分组")
    print("="*50)
    
    # 加载章节
    print(f"\n加载章节: {args.input}")
    chapters = load_chapters(Path(args.input))
    if not chapters:
        return
    print(f"  ✓ 加载 {len(chapters)} 章")
    
    # 创建序列
    print(f"\n创建序列 (每组{args.size}章)...")
    sequences = create_sequences(chapters, args.size)
    print(f"  ✓ 创建 {len(sequences)} 个序列")
    
    # 统计
    for seq in sequences[:3]:
        print(f"    序列{seq['seq_id']}: 第{seq['start']}-{seq['end']}章 ({seq['word_count']:,}字)")
    if len(sequences) > 3:
        print(f"    ... 共{len(sequences)}个序列")
    
    # 保存
    output_dir = Path(args.output)
    save_sequences(sequences, output_dir)
    print(f"\n✓ 保存到: {output_dir}/")


if __name__ == "__main__":
    main()