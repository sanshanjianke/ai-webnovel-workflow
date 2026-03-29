"""
步骤3：LLM生成草稿

功能：调用LLM将序列缩减为草稿

输入：output/02_sequences/
输出：output/03_drafts/

用法：
    python steps/step3_generate_drafts.py --input output/02_sequences --output output/03_drafts

注意：
    - 每章只发送前3000字给LLM（防止超时）
    - 修改 PROMPT_TEMPLATE 可调整输出质量
    - 支持断点续传（已存在的草稿会跳过）
"""

import json
import time
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import create_llm


# ============================================================================
# 【关键】Prompt模板 - 修改这里调整输出质量
# ============================================================================
PROMPT_TEMPLATE = """你是一个专业的网文编辑。请将以下章节内容缩减为草稿版本。

要求：
1. 输出总字数约5000字（7章合计），每章约700字
2. 保留：人物性格特征、话语模式、关键对话原文、事件细节、决策过程、冲突结果、设定、伏笔
3. 删除：过于冗长的环境描写、无关的过渡段落
4. 保持连贯：缩减后剧情逻辑完整，人物形象鲜明

章节内容：
{content}

直接输出缩减后的文本，每章用【第X章】分隔。确保总字数约5000字。"""


def load_sequences(input_dir: Path):
    """加载序列"""
    index_file = input_dir / "index.json"
    if not index_file.exists():
        print(f"  ✗ 找不到索引文件: {index_file}")
        return []
    
    index = json.loads(index_file.read_text(encoding='utf-8'))
    
    sequences = []
    for item in index:
        seq_file = input_dir / f"sequence_{item['seq_id']:02d}.txt"
        if seq_file.exists():
            text = seq_file.read_text(encoding='utf-8')
            sequences.append({
                "seq_id": item['seq_id'],
                "start": item['start'],
                "end": item['end'],
                "text": text
            })
    
    return sorted(sequences, key=lambda x: x['seq_id'])


def load_existing_drafts(output_dir: Path):
    """加载已存在的草稿（断点续传）"""
    existing = {}
    if output_dir.exists():
        for f in output_dir.glob("draft_*.txt"):
            seq_id = int(f.stem.split("_")[1])
            content = f.read_text(encoding='utf-8')
            if not content.startswith("[失败"):
                existing[seq_id] = content
    return existing


def generate_draft(llm, sequence: dict, chars_per_chapter: int = 3000):
    """
    生成单个草稿
    
    Args:
        llm: LLM实例
        sequence: 序列数据
        chars_per_chapter: 每章发送的字数限制
    
    Returns:
        草稿文本
    """
    # 构建内容（每章限制字数）
    # 【修改点】调整 chars_per_chapter 可发送更多/更少内容
    content = sequence['text'][:chars_per_chapter * 7]  # 7章，每章限制字数
    
    prompt = PROMPT_TEMPLATE.format(content=content)
    
    response = llm.invoke(prompt)
    return response.content


def save_draft(seq_id: int, draft_text: str, output_dir: Path):
    """保存草稿"""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"draft_{seq_id:02d}.txt"
    filepath.write_text(draft_text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='步骤3：LLM生成草稿')
    parser.add_argument('--input', '-i', default='output/02_sequences', help='输入目录')
    parser.add_argument('--output', '-o', default='output/03_drafts', help='输出目录')
    parser.add_argument('--chars', '-c', type=int, default=3000, help='每章发送字数')
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("步骤3：LLM生成草稿")
    print("="*50)
    
    # 初始化LLM
    print("\n初始化LLM...")
    llm = create_llm(temperature=0.3)
    if not llm:
        print("  ✗ LLM初始化失败")
        return
    print("  ✓ LLM初始化成功")
    
    # 加载序列
    print(f"\n加载序列: {args.input}")
    sequences = load_sequences(Path(args.input))
    if not sequences:
        return
    print(f"  ✓ 加载 {len(sequences)} 个序列")
    
    # 加载已存在的草稿
    output_dir = Path(args.output)
    existing = load_existing_drafts(output_dir)
    if existing:
        print(f"  发现已有草稿: {len(existing)} 个（将跳过）")
    
    # 处理每个序列
    print(f"\n生成草稿...")
    for i, seq in enumerate(sequences):
        # 跳过已存在
        if seq['seq_id'] in existing:
            print(f"  [{i+1}/{len(sequences)}] 序列{seq['seq_id']}: 已存在，跳过")
            continue
        
        print(f"  [{i+1}/{len(sequences)}] 序列{seq['seq_id']}: 第{seq['start']}-{seq['end']}章...", end=" ")
        
        try:
            draft_text = generate_draft(llm, seq, args.chars)
            save_draft(seq['seq_id'], draft_text, output_dir)
            print(f"✓ {len(draft_text)}字")
            time.sleep(0.5)  # 防止限流
        except Exception as e:
            print(f"✗ 失败: {e}")
            save_draft(seq['seq_id'], f"[失败: {e}]", output_dir)
    
    print(f"\n✓ 完成，保存到: {output_dir}/")


if __name__ == "__main__":
    main()