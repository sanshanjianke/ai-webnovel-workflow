"""
步骤3：LLM生成草稿（并行版本）

功能：并行调用LLM将序列缩减为草稿

用法：
    python steps/step3_generate_drafts.py --input output/02_sequences --output output/03_drafts --workers 10

特性：
    - 并行处理多个序列
    - 超时自动重试
    - 支持断点续传
"""

import json
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import re

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import create_llm


# ============================================================================
# 配置（可通过命令行参数覆盖）
# ============================================================================
DEFAULT_TIMEOUT = 180      # 默认超时（秒）- GLM5很慢
DEFAULT_WORKERS = 5        # 默认并发数
DEFAULT_CHARS = 2000       # 默认每章发送字数
DEFAULT_DELAY = 0.5        # 请求间隔（秒）
MAX_RETRIES = 2            # 最大重试次数

PROMPT_TEMPLATE = """请用约3000字总结以下章节内容，保留关键剧情、人物性格、对话和设定：

{content}"""


def clean_response(text: str) -> str:
    """清理LLM响应，去除think等标签"""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def load_sequences(input_dir: Path):
    """加载序列"""
    sequences = []
    index_file = input_dir / "index.json"
    
    if index_file.exists():
        index = json.loads(index_file.read_text(encoding='utf-8'))
        for item in index:
            seq_file = input_dir / f"sequence_{item['seq_id']:02d}.txt"
            if seq_file.exists():
                sequences.append({
                    "seq_id": item['seq_id'],
                    "text": seq_file.read_text(encoding='utf-8')
                })
    else:
        for f in sorted(input_dir.glob("sequence_*.txt")):
            seq_id = int(f.stem.split("_")[1])
            sequences.append({"seq_id": seq_id, "text": f.read_text()})
    
    return sorted(sequences, key=lambda x: x['seq_id'])


def process_one(seq_id: int, text: str, output_dir: Path, chars: int, timeout: int, retries: int = MAX_RETRIES):
    """处理单个序列（带重试）"""
    content = text[:chars * 7]
    prompt = PROMPT_TEMPLATE.format(content=content)
    
    for attempt in range(retries + 1):
        try:
            llm = create_llm(request_timeout=timeout)
            resp = llm.invoke(prompt)
            draft = clean_response(resp.content)
            
            if len(draft) < 100:
                raise Exception(f"输出太短: {len(draft)}字")
            
            filepath = output_dir / f"draft_{seq_id:02d}.txt"
            filepath.write_text(draft, encoding='utf-8')
            
            return (seq_id, len(draft), True, None)
            
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                return (seq_id, 0, False, str(e))
    
    return (seq_id, 0, False, "未知错误")


def main():
    parser = argparse.ArgumentParser(description='步骤3：LLM生成草稿（并行版本）')
    parser.add_argument('--input', '-i', default='output/02_sequences')
    parser.add_argument('--output', '-o', default='output/03_drafts')
    parser.add_argument('--workers', '-w', type=int, default=DEFAULT_WORKERS, help=f'并发数（默认{DEFAULT_WORKERS}）')
    parser.add_argument('--chars', '-c', type=int, default=DEFAULT_CHARS, help=f'每章字数（默认{DEFAULT_CHARS}）')
    parser.add_argument('--timeout', '-t', type=int, default=DEFAULT_TIMEOUT, help=f'超时秒数（默认{DEFAULT_TIMEOUT}）')
    parser.add_argument('--delay', '-d', type=float, default=DEFAULT_DELAY, help=f'请求间隔（默认{DEFAULT_DELAY}）')
    parser.add_argument('--retries', '-r', type=int, default=MAX_RETRIES, help=f'重试次数（默认{MAX_RETRIES}）')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("步骤3：LLM生成草稿（并行版本）")
    print("="*60)
    print(f"并发: {args.workers}, 超时: {args.timeout}秒, 重试: {args.retries}次")
    
    # 加载
    input_dir = Path(args.input)
    sequences = load_sequences(input_dir)
    if not sequences:
        print("✗ 没有找到序列")
        return
    
    print(f"加载 {len(sequences)} 个序列")
    
    # 输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查已完成
    existing = set()
    for f in output_dir.glob("draft_*.txt"):
        if f.stat().st_size > 100:
            seq_id = int(f.stem.split("_")[1])
            existing.add(seq_id)
    
    pending = [s for s in sequences if s['seq_id'] not in existing]
    print(f"已完成: {len(existing)}, 待处理: {len(pending)}")
    
    if not pending:
        print("✓ 全部完成")
        return
    
    # 并行处理
    print(f"\n开始处理...")
    start_time = time.time()
    success = len(existing)
    failed = []
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        
        for seq in pending:
            future = executor.submit(
                process_one, 
                seq['seq_id'], seq['text'], output_dir,
                args.chars, args.timeout, args.retries
            )
            futures[future] = seq
            time.sleep(args.delay)
        
        for future in as_completed(futures):
            seq = futures[future]
            try:
                seq_id, length, ok, err = future.result()
                if ok:
                    success += 1
                    print(f"  [{success}/{len(sequences)}] ✓ 序列{seq_id}: {length}字")
                else:
                    failed.append((seq_id, err))
                    print(f"  ✗ 序列{seq_id}: {err}")
            except Exception as e:
                failed.append((seq['seq_id'], str(e)))
                print(f"  ✗ 序列{seq['seq_id']}: {e}")
    
    elapsed = time.time() - start_time
    
    # 统计
    print(f"\n{'='*60}")
    print(f"完成: {success}/{len(sequences)} 成功")
    print(f"失败: {len(failed)}")
    if failed:
        print("失败列表:", [f[0] for f in failed])
    print(f"耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
    if len(pending) > 0:
        print(f"平均: {elapsed/len(pending):.1f}秒/序列")


if __name__ == "__main__":
    main()