"""
步骤5：LLM生成L2大纲

功能：使用滑动窗口生成L2格式大纲

输入：output/04_blocks/
输出：output/05_outline/

用法：
    python steps/step5_generate_outline.py --input output/04_blocks --output output/05_outline

滑动窗口策略：
    - 每次处理150KB文本
    - 前50KB作为上下文
    - 中间50KB作为重点处理区域
    - 后50KB作为上下文
    - 窗口每次移动50KB
"""

import re
import json
import time
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import create_llm


# ============================================================================
# 配置参数
# ============================================================================
CONTEXT_SIZE = 50 * 1024  # 上下文大小 50KB
FOCUS_SIZE = 50 * 1024    # 重点区域大小 50KB


def load_blocks(input_dir: Path):
    """加载块"""
    blocks = []
    
    if not input_dir.exists():
        return blocks
    
    for f in sorted(input_dir.glob("block_*.txt")):
        block_id = int(f.stem.split("_")[1])
        text = f.read_text(encoding='utf-8')
        blocks.append({
            "block_id": block_id,
            "text": text
        })
    
    return blocks


def generate_outline_for_window(llm, all_text: str, start: int, total_size: int):
    """
    为单个窗口生成大纲
    
    Args:
        llm: LLM实例
        all_text: 全部文本
        start: 窗口起始位置
        total_size: 文本总大小
    
    Returns:
        章节列表
    """
    # 计算窗口范围
    window_start = max(0, start - CONTEXT_SIZE)
    window_end = min(total_size, start + FOCUS_SIZE + CONTEXT_SIZE)
    
    # 构建prompt
    if start == 0:
        # 第一段，没有前文
        focus_text = all_text[start:start + FOCUS_SIZE]
        after_text = all_text[start + FOCUS_SIZE:window_end]
        
        prompt = f"""你是一个专业的网文大纲编辑。请为以下内容生成L2格式大纲。

重点关注区域：
{focus_text}

后续背景：
{after_text}

请为重点关注区域生成详细的大纲，包含：
1. 每章标题
2. 摘要（1-2句话）
3. 序列信息（名称、功能类型、情绪走向、爽点类型）

输出JSON格式：
{{"chapters": [{{"chapter_num": 1, "title": "...", "summary": "...", "sequences": [{{"name": "...", "functions": [], "emotion": "...", "appeal_type": "..."}}]}}]}}"""
    else:
        # 中间段，有前后文
        before_text = all_text[window_start:start]
        focus_text = all_text[start:start + FOCUS_SIZE]
        after_text = all_text[start + FOCUS_SIZE:window_end]
        
        prompt = f"""你是一个专业的网文大纲编辑。请为以下内容生成L2格式大纲。

【前文背景】：
{before_text}

【重点关注区域】：
{focus_text}

【后续背景】：
{after_text}

请为重点关注区域生成详细的大纲，注意与前文和后文的连贯性。

输出JSON格式：
{{"chapters": [{{"chapter_num": N, "title": "...", "summary": "...", "sequences": [{{"name": "...", "functions": [], "emotion": "...", "appeal_type": "..."}}]}}]}}"""
    
    try:
        response = llm.invoke(prompt)
        content = response.content
        
        # 提取JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            data = json.loads(json_match.group())
            return data.get('chapters', [])
    except Exception as e:
        print(f"    ✗ 失败: {e}")
    
    return []


def save_outline(chapters: list, output_dir: Path, novel_name: str = "未命名"):
    """保存大纲"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存JSON
    outline = {
        "novel_name": novel_name,
        "total_chapters": len(chapters),
        "chapters": chapters
    }
    
    json_path = output_dir / "outline.json"
    json_path.write_text(
        json.dumps(outline, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    
    # 保存Markdown
    md_lines = [
        f"# {novel_name} - L2大纲\n",
        f"总章节: {len(chapters)}章\n"
    ]
    
    for ch in chapters:
        md_lines.append(f"## {ch.get('title', '未知章节')}")
        md_lines.append(f"{ch.get('summary', '无摘要')}\n")
        
        for seq in ch.get('sequences', []):
            md_lines.append(f"- 序列: {seq.get('name', '未知')}")
            md_lines.append(f"  - 功能: {', '.join(seq.get('functions', []))}")
            md_lines.append(f"  - 情绪: {seq.get('emotion', '未知')}")
            md_lines.append(f"  - 爽点: {seq.get('appeal_type', '未知')}")
        md_lines.append("")
    
    md_path = output_dir / "outline.md"
    md_path.write_text('\n'.join(md_lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='步骤5：LLM生成L2大纲')
    parser.add_argument('--input', '-i', default='output/04_blocks', help='输入目录')
    parser.add_argument('--output', '-o', default='output/05_outline', help='输出目录')
    parser.add_argument('--name', '-n', default='未命名', help='小说名称')
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("步骤5：LLM生成L2大纲")
    print("="*50)
    
    # 初始化LLM
    print("\n初始化LLM...")
    llm = create_llm(temperature=0.3)
    if not llm:
        print("  ✗ LLM初始化失败")
        return
    print("  ✓ LLM初始化成功")
    
    # 加载块
    print(f"\n加载块: {args.input}")
    blocks = load_blocks(Path(args.input))
    if not blocks:
        print("  ✗ 没有找到块")
        return
    print(f"  ✓ 加载 {len(blocks)} 个块")
    
    # 合并所有块
    all_text = "\n\n".join([b['text'] for b in blocks])
    total_size = len(all_text)
    print(f"  总文本: {total_size:,}字 ({total_size//1024}KB)")
    
    # 滑动窗口处理
    print(f"\n生成大纲 (滑动窗口: {CONTEXT_SIZE//1024}KB + {FOCUS_SIZE//1024}KB + {CONTEXT_SIZE//1024}KB)...")
    
    all_chapters = []
    start = 0
    
    while start < total_size:
        print(f"  处理位置 {start//1024}KB/{total_size//1024}KB...", end=" ")
        
        chapters = generate_outline_for_window(llm, all_text, start, total_size)
        
        if chapters:
            all_chapters.extend(chapters)
            print(f"✓ 累计 {len(all_chapters)} 章")
        else:
            print("⚠ 无输出")
        
        time.sleep(1)
        start += FOCUS_SIZE
    
    # 保存
    print(f"\n保存大纲...")
    save_outline(all_chapters, Path(args.output), args.name)
    print(f"✓ 保存到: {args.output}/ ({len(all_chapters)}章)")


if __name__ == "__main__":
    main()