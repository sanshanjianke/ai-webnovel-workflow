"""
步骤5：LLM生成L2大纲（并行版本）

功能：使用滑动窗口生成L2格式大纲

用法：
    python steps/step5_generate_outline.py --input output/04_blocks --output output/05_outline --name "书名"

滑动窗口策略：
    - 每次处理约150KB文本（前50KB + 中间50KB + 后50KB）
    - 窗口每次移动50KB
"""

import re
import json
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import create_llm


# ============================================================================
# 配置
# ============================================================================
# 中文字符约3字节，50KB ≈ 17000字符
CONTEXT_CHARS = 17000   # 上下文字符数（约50KB）
FOCUS_CHARS = 17000     # 重点区域字符数（约50KB）
DEFAULT_TIMEOUT = 180   # 超时秒数
DEFAULT_WORKERS = 3     # 并发数


def load_blocks(input_dir: Path):
    """加载块"""
    blocks = []
    for f in sorted(input_dir.glob("block_*.txt")):
        blocks.append(f.read_text(encoding='utf-8'))
    return blocks


def clean_json(text: str) -> str:
    """清理JSON，移除markdown代码块标记"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    return text.strip()


def process_window(all_text: str, start: int, total_chars: int, timeout: int):
    """
    处理单个窗口
    
    Args:
        all_text: 全部文本
        start: 窗口起始位置（字符）
        total_chars: 总字符数
        timeout: 超时秒数
    
    Returns:
        章节列表
    """
    # 计算窗口范围
    window_start = max(0, start - CONTEXT_CHARS)
    window_end = min(total_chars, start + FOCUS_CHARS + CONTEXT_CHARS)
    
    # 提取文本
    if start == 0:
        # 第一段，没有前文
        focus_text = all_text[start:start + FOCUS_CHARS]
        after_text = all_text[start + FOCUS_CHARS:window_end]
        
        prompt = f"""你是一个专业的网文剧情架构师。请将以下章节内容转换为L2格式大纲。

L2格式说明：
1. 按"序列"组织，每个序列是一个完整的剧情单元
2. 每个序列包含：
   - 序列名称（如"拍卖会打脸"、"初遇反派"）
   - 功能类型：铺垫/转折/反馈/获得/斗争/胜利
   - 情绪走向：如"压抑→爆发→余韵"
   - 爽点类型：如"打脸、装逼、逆袭"
   - 详细剧情（保留关键对话、决策、冲突）

重点关注区域：
{focus_text}

后续背景：
{after_text}

输出JSON格式：
{{
  "sequences": [
    {{
      "name": "序列名称",
      "functions": ["铺垫", "转折"],
      "emotion": "压抑→爆发",
      "appeal_types": ["打脸"],
      "plot": "详细剧情描述，包含关键对话、决策、冲突结果..."
    }}
  ]
}}

只输出JSON，不要其他内容。"""
    else:
        # 中间段
        before_text = all_text[window_start:start]
        focus_text = all_text[start:start + FOCUS_CHARS]
        after_text = all_text[start + FOCUS_CHARS:window_end]
        
        prompt = f"""你是一个专业的网文剧情架构师。请将以下章节内容转换为L2格式大纲。

L2格式说明：
1. 按"序列"组织，每个序列是一个完整的剧情单元
2. 每个序列包含：
   - 序列名称（如"拍卖会打脸"、"初遇反派"）
   - 功能类型：铺垫/转折/反馈/获得/斗争/胜利
   - 情绪走向：如"压抑→爆发→余韵"
   - 爽点类型：如"打脸、装逼、逆袭"
   - 详细剧情（保留关键对话、决策、冲突）

【前文背景】：
{before_text}

【重点关注区域】：
{focus_text}

【后续背景】：
{after_text}

输出JSON格式：
{{
  "sequences": [
    {{
      "name": "序列名称",
      "functions": ["铺垫", "转折"],
      "emotion": "压抑→爆发",
      "appeal_types": ["打脸"],
      "plot": "详细剧情描述，包含关键对话、决策、冲突结果..."
    }}
  ]
}}

只输出JSON，不要其他内容。"""
    
    try:
        llm = create_llm(request_timeout=timeout)
        response = llm.invoke(prompt)
        content = clean_json(response.content)
        
        # 提取JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            data = json.loads(json_match.group())
            return data.get('sequences', [])
    except Exception as e:
        print(f"    错误: {e}")
    
    return []


def main():
    parser = argparse.ArgumentParser(description='步骤5：LLM生成L2大纲')
    parser.add_argument('--input', '-i', default='output/04_blocks')
    parser.add_argument('--output', '-o', default='output/05_outline')
    parser.add_argument('--name', '-n', default='未命名')
    parser.add_argument('--timeout', '-t', type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument('--workers', '-w', type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("步骤5：LLM生成L2大纲")
    print("="*60)
    
    # 加载块
    input_dir = Path(args.input)
    blocks = load_blocks(input_dir)
    if not blocks:
        print("✗ 没有找到块")
        return
    
    all_text = "\n\n".join(blocks)
    total_chars = len(all_text)
    print(f"总文本: {total_chars:,}字符 ({total_chars*3//1024}KB)")
    
    # 计算窗口数量
    num_windows = (total_chars + FOCUS_CHARS - 1) // FOCUS_CHARS
    print(f"窗口数: {num_windows} (并发={args.workers})")
    
    # 生成窗口任务
    windows = []
    start = 0
    while start < total_chars:
        windows.append(start)
        start += FOCUS_CHARS
    
    # 并行处理
    print(f"\n开始处理...")
    all_sequences = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for window_start in windows:
            future = executor.submit(
                process_window, 
                all_text, window_start, total_chars, args.timeout
            )
            futures[future] = window_start
            time.sleep(0.5)  # 错开请求
        
        for future in as_completed(futures):
            window_start = futures[future]
            try:
                sequences = future.result()
                if sequences:
                    all_sequences.extend(sequences)
                    print(f"  位置{window_start//1024}KB: ✓ {len(sequences)}序列 (累计{len(all_sequences)})")
                else:
                    print(f"  位置{window_start//1024}KB: ⚠ 无输出")
            except Exception as e:
                print(f"  位置{window_start//1024}KB: ✗ {e}")
    
    elapsed = time.time() - start_time
    
    # 保存
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    outline = {
        "novel_name": args.name,
        "total_sequences": len(all_sequences),
        "sequences": all_sequences
    }
    
    (output_dir / "outline.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    
    # Markdown
    md_lines = [f"# {args.name} - L2大纲\n\n总序列: {len(all_sequences)}个\n"]
    for seq in all_sequences:
        md_lines.append(f"## 【{seq.get('name', '未知序列')}】")
        md_lines.append(f"- 功能: {', '.join(seq.get('functions', []))}")
        md_lines.append(f"- 情绪: {seq.get('emotion', '')}")
        md_lines.append(f"- 爽点: {', '.join(seq.get('appeal_types', []))}")
        md_lines.append(f"\n{seq.get('plot', '')}\n")
    
    (output_dir / "outline.md").write_text('\n'.join(md_lines), encoding='utf-8')
    
    print(f"\n{'='*60}")
    print(f"完成: {len(all_sequences)}个序列")
    print(f"耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
    print(f"输出: {output_dir}/")


if __name__ == "__main__":
    main()