"""
步骤5：LLM生成L2大纲（串行版本，保持上下文记忆）

功能：逐个处理block，每次输出独立outline文件，保持上下文连贯

用法：
    python steps/step5_generate_outline.py --input output/04_blocks --output output/05_outline --name "书名"
"""

import re
import json
import time
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import create_llm

DEFAULT_TIMEOUT = 180


def load_blocks(input_dir: Path):
    """加载块"""
    blocks = []
    for f in sorted(input_dir.glob("block_*.txt")):
        blocks.append(f.read_text(encoding='utf-8'))
    return blocks


def clean_json(text: str) -> str:
    """清理JSON"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    return text.strip()


def build_context_summary(characters: dict, sequences: list) -> str:
    """构建上下文摘要"""
    if not characters and not sequences:
        return ""
    
    lines = ["【已提取内容摘要】"]
    if characters:
        lines.append(f"人物表（{len(characters)}人）：")
        for name, desc in list(characters.items())[:10]:
            lines.append(f"  - {name}: {desc[:50]}...")
    if sequences:
        lines.append(f"已提取序列（{len(sequences)}个）：")
        for seq in sequences[-5:]:
            lines.append(f"  - {seq.get('name', '未知')}")
    return "\n".join(lines)


def process_block(block_text: str, block_id: int, context: str, timeout: int):
    """处理单个block"""
    if block_id == 1 or not context:
        prompt = f"""你是一个专业的网文剧情架构师。请将以下内容转换为L2格式大纲。

L2格式说明：
1. 按"序列"组织，每个序列是一个完整的剧情单元（约2-5章内容为一个序列）
2. 每个序列包含：
   - 序列名称（如"拍卖会打脸"、"初遇反派"）
   - 功能类型：铺垫/转折/反馈/获得/斗争/胜利
   - 情绪走向：如"压抑→爆发→余韵"
   - 爽点类型：如"打脸、装逼、逆袭"
   - 人物列表：本序列出现的主要人物
   - 详细剧情：必须详细展开，保留关键对话原句、场景描写、人物动作、心理变化、冲突过程、结果影响。每个序列的plot至少300字

待处理内容：
{block_text}

输出JSON格式：
{{
  "characters": [
    {{"name": "人物名", "desc": "详细身份描述、性格特点、与主角关系、关键事件"}}
  ],
  "sequences": [
    {{
      "name": "序列名称",
      "functions": ["铺垫", "转折"],
      "emotion": "压抑→爆发",
      "appeal_types": ["打脸"],
      "characters": ["人物A", "人物B"],
      "plot": "详细剧情描述，必须包含：场景设定、人物登场、对话原句、动作描写、冲突过程、心理变化、结果影响。不少于300字"
    }}
  ]
}}

只输出JSON，不要其他内容。"""
    else:
        prompt = f"""你是一个专业的网文剧情架构师。请将以下内容转换为L2格式大纲。

{context}

请继续提取后续内容，注意：
1. 人物表：只添加新出现的人物，已提取的不要重复，描述要详细（性格、关系、关键事件）
2. 序列：继续提取新的序列，保持剧情连贯，每个序列plot至少300字

待处理内容：
{block_text}

输出JSON格式：
{{
  "characters": [
    {{"name": "新人物名", "desc": "详细身份描述、性格特点、与主角关系、关键事件"}}
  ],
  "sequences": [
    {{
      "name": "序列名称",
      "functions": ["铺垫", "转折"],
      "emotion": "压抑→爆发",
      "appeal_types": ["打脸"],
      "characters": ["人物A", "人物B"],
      "plot": "详细剧情描述，必须包含：场景设定、人物登场、对话原句、动作描写、冲突过程、心理变化、结果影响。不少于300字"
    }}
  ]
}}

只输出JSON，不要其他内容。"""
    
    try:
        llm = create_llm(request_timeout=timeout)
        response = llm.invoke(prompt)
        content = clean_json(response.content)
        
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            data = json.loads(json_match.group())
            return data.get('characters', []), data.get('sequences', [])
    except Exception as e:
        print(f"    错误: {e}")
    
    return [], []


def save_outline_part(output_dir: Path, block_id: int, characters: list, sequences: list, novel_name: str):
    """保存单部分outline"""
    outline = {
        "novel_name": novel_name,
        "block_id": block_id,
        "characters": characters,
        "sequences": sequences
    }
    
    (output_dir / f"outline_{block_id:02d}.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def merge_all_outlines(output_dir: Path, novel_name: str):
    """合并所有outline"""
    all_characters = {}
    all_sequences = []
    
    for f in sorted(output_dir.glob("outline_*.json")):
        data = json.loads(f.read_text(encoding='utf-8'))
        for c in data.get('characters', []):
            name = c.get('name', '')
            if name and name not in all_characters:
                all_characters[name] = c.get('desc', '')
        all_sequences.extend(data.get('sequences', []))
    
    char_list = [{"name": k, "desc": v} for k, v in all_characters.items()]
    
    final_outline = {
        "novel_name": novel_name,
        "total_characters": len(char_list),
        "total_sequences": len(all_sequences),
        "characters": char_list,
        "sequences": all_sequences
    }
    
    (output_dir / "outline.json").write_text(
        json.dumps(final_outline, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    
    md_lines = [f"# {novel_name} - L2大纲\n"]
    md_lines.append(f"## 人物表 ({len(char_list)}人)\n")
    for c in char_list:
        md_lines.append(f"- **{c['name']}**: {c.get('desc', '')}")
    md_lines.append(f"\n## 序列 ({len(all_sequences)}个)\n")
    for seq in all_sequences:
        md_lines.append(f"\n### 【{seq.get('name', '未知序列')}】")
        md_lines.append(f"- 功能: {', '.join(seq.get('functions', []))}")
        md_lines.append(f"- 情绪: {seq.get('emotion', '')}")
        md_lines.append(f"- 爽点: {', '.join(seq.get('appeal_types', []))}")
        chars = seq.get('characters', [])
        if chars:
            md_lines.append(f"- 人物: {', '.join(chars)}")
        md_lines.append(f"\n{seq.get('plot', '')}\n")
    
    (output_dir / "outline.md").write_text('\n'.join(md_lines), encoding='utf-8')
    
    return len(char_list), len(all_sequences)


def main():
    parser = argparse.ArgumentParser(description='步骤5：LLM生成L2大纲')
    parser.add_argument('--input', '-i', default='output/04_blocks')
    parser.add_argument('--output', '-o', default='output/05_outline')
    parser.add_argument('--name', '-n', default='未命名')
    parser.add_argument('--timeout', '-t', type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("步骤5：LLM生成L2大纲（串行，保持上下文）")
    print("="*60)
    
    input_dir = Path(args.input)
    blocks = load_blocks(input_dir)
    if not blocks:
        print("✗ 没有找到块")
        return
    
    print(f"总块数: {len(blocks)}")
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_characters = {}
    all_sequences = []
    start_time = time.time()
    
    print(f"\n开始处理...")
    for i, block in enumerate(blocks):
        block_id = i + 1
        
        # 断点续传：跳过已完成的块
        existing = output_dir / f"outline_{block_id:02d}.json"
        if existing.exists():
            data = json.loads(existing.read_text(encoding='utf-8'))
            characters = data.get('characters', [])
            sequences = data.get('sequences', [])
            all_sequences.extend(sequences)
            for c in characters:
                name = c.get('name', '')
                if name and name not in all_characters:
                    all_characters[name] = c.get('desc', '')
            print(f"  块{block_id}: 已存在，跳过 ({len(sequences)}序列)")
            continue
        
        context = build_context_summary(all_characters, all_sequences)
        
        print(f"\n  处理块{block_id}/{len(blocks)} ({len(block)}字符)...")
        block_start = time.time()
        
        characters, sequences = process_block(block, block_id, context, args.timeout)
        
        if sequences:
            all_sequences.extend(sequences)
            for c in characters:
                name = c.get('name', '')
                if name and name not in all_characters:
                    all_characters[name] = c.get('desc', '')
            
            save_outline_part(output_dir, block_id, characters, sequences, args.name)
            
            block_time = time.time() - block_start
            print(f"    ✓ {len(sequences)}序列, {len(characters)}人物 ({block_time:.0f}秒)")
        else:
            print(f"    ⚠ 无输出")
    
    elapsed = time.time() - start_time
    
    print(f"\n合并所有outline...")
    char_count, seq_count = merge_all_outlines(output_dir, args.name)
    
    print(f"\n{'='*60}")
    print(f"完成: {seq_count}个序列, {char_count}个人物")
    print(f"耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
    print(f"输出: {output_dir}/")


if __name__ == "__main__":
    main()