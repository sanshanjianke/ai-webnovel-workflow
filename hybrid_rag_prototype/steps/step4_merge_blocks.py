"""
步骤4：切分成块

功能：将草稿按固定大小切分成多个块

输入：output/03_drafts/
输出：output/04_blocks/

用法：
    python steps/step4_merge_blocks.py --input output/03_drafts --output output/04_blocks --size 50
"""

import json
import argparse
from pathlib import Path


def load_drafts(input_dir: Path):
    """加载草稿"""
    drafts = []
    
    if not input_dir.exists():
        return drafts
    
    for f in sorted(input_dir.glob("draft_*.txt")):
        seq_id = int(f.stem.split("_")[1])
        text = f.read_text(encoding='utf-8')
        drafts.append({
            "seq_id": seq_id,
            "text": text
        })
    
    return drafts


def merge_and_split(drafts: list, block_size_kb: int = 50):
    """
    合并草稿并按固定大小切分
    
    Args:
        drafts: 草稿列表
        block_size_kb: 块大小KB
    
    Returns:
        块列表: [{"block_id": 1, "text": "..."}]
    """
    # 合并所有草稿
    all_text = "\n\n".join([d['text'] for d in drafts])
    total_chars = len(all_text)
    block_size = block_size_kb * 1024
    
    print(f"  总文本: {total_chars:,}字 ({total_chars//1024}KB)")
    print(f"  块大小: {block_size_kb}KB")
    
    # 切分
    blocks = []
    for i in range(0, total_chars, block_size):
        chunk = all_text[i:i + block_size]
        blocks.append({
            "block_id": len(blocks) + 1,
            "text": chunk,
            "char_count": len(chunk)
        })
    
    return blocks


def save_blocks(blocks: list, output_dir: Path):
    """保存块"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存每个块
    for block in blocks:
        filepath = output_dir / f"block_{block['block_id']:02d}.txt"
        filepath.write_text(block['text'], encoding='utf-8')
    
    # 保存索引
    index = [{
        "block_id": b['block_id'],
        "char_count": b['char_count']
    } for b in blocks]
    
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def main():
    parser = argparse.ArgumentParser(description='步骤4：切分成块')
    parser.add_argument('--input', '-i', default='output/03_drafts', help='输入目录')
    parser.add_argument('--output', '-o', default='output/04_blocks', help='输出目录')
    parser.add_argument('--size', '-s', type=int, default=50, help='块大小KB')
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("步骤4：切分成块")
    print("="*50)
    
    # 加载草稿
    print(f"\n加载草稿: {args.input}")
    drafts = load_drafts(Path(args.input))
    if not drafts:
        print("  ✗ 没有找到草稿")
        return
    print(f"  ✓ 加载 {len(drafts)} 个草稿")
    
    # 切分
    print(f"\n切分成块...")
    blocks = merge_and_split(drafts, args.size)
    
    for block in blocks:
        print(f"  块{block['block_id']}: {block['char_count']//1024}KB")
    
    # 保存
    output_dir = Path(args.output)
    save_blocks(blocks, output_dir)
    print(f"\n✓ 保存到: {output_dir}/ ({len(blocks)}个块)")


if __name__ == "__main__":
    main()