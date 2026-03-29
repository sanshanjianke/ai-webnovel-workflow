#!/usr/bin/env python3
"""
运行全部步骤

用法：
    python steps/run_all.py --novel 都市剑说.txt --max 100 --name "都市剑说"
"""

import argparse
import subprocess
from pathlib import Path


def run_step(script: str, args: list = []):
    """运行单个步骤"""
    cmd = ["python", script] + args
    print(f"\n执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description='运行全部步骤')
    parser.add_argument('--novel', '-n', required=True, help='小说文件路径')
    parser.add_argument('--max', '-m', type=int, default=100, help='最大章节数')
    parser.add_argument('--name', required=True, help='小说名称')
    parser.add_argument('--output', '-o', default='output', help='输出目录')
    parser.add_argument('--seq-size', type=int, default=7, help='每组章节数')
    parser.add_argument('--block-size', type=int, default=50, help='块大小KB')
    args = parser.parse_args()
    
    steps_dir = Path(__file__).parent
    
    print("="*60)
    print("分层大纲提取器")
    print("="*60)
    print(f"小说: {args.novel}")
    print(f"名称: {args.name}")
    print(f"章节数: {args.max}")
    print(f"输出目录: {args.output}")
    
    # 步骤1：章节切片
    if not run_step(
        str(steps_dir / "step1_split_chapters.py"),
        [args.novel, "--output", f"{args.output}/01_chapters", "--max", str(args.max)]
    ):
        return
    
    # 步骤2：序列分组
    if not run_step(
        str(steps_dir / "step2_create_sequences.py"),
        ["--input", f"{args.output}/01_chapters", "--output", f"{args.output}/02_sequences", "--size", str(args.seq_size)]
    ):
        return
    
    # 步骤3：LLM生成草稿
    if not run_step(
        str(steps_dir / "step3_generate_drafts.py"),
        ["--input", f"{args.output}/02_sequences", "--output", f"{args.output}/03_drafts"]
    ):
        return
    
    # 步骤4：切分成块
    if not run_step(
        str(steps_dir / "step4_merge_blocks.py"),
        ["--input", f"{args.output}/03_drafts", "--output", f"{args.output}/04_blocks", "--size", str(args.block_size)]
    ):
        return
    
    # 步骤5：LLM生成大纲
    if not run_step(
        str(steps_dir / "step5_generate_outline.py"),
        ["--input", f"{args.output}/04_blocks", "--output", f"{args.output}/05_outline", "--name", args.name]
    ):
        return
    
    print("\n" + "="*60)
    print("✓ 全部完成！")
    print("="*60)


if __name__ == "__main__":
    main()