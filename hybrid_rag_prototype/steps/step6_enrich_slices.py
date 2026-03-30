"""
步骤6：多维度切片 + 文档增强

文档增强策略：
- 一次性生成5个视角的改写
- 充分利用GLM5的理解能力
- 增加检索入口，提高命中率

用法：
    python steps/step6_enrich_slices.py --input output/05_outline --output output/06_slices
"""

import re
import json
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import create_llm

DEFAULT_TIMEOUT = 180


def load_outline(input_dir: Path):
    """加载outline"""
    outline_file = input_dir / "outline.json"
    if outline_file.exists():
        return json.loads(outline_file.read_text(encoding='utf-8'))
    
    all_data = {"novel_name": "", "characters": [], "sequences": []}
    for f in sorted(input_dir.glob("outline_*.json")):
        data = json.loads(f.read_text(encoding='utf-8'))
        all_data["novel_name"] = data.get("novel_name", all_data["novel_name"])
        all_data["characters"].extend(data.get("characters", []))
        all_data["sequences"].extend(data.get("sequences", []))
    
    return all_data


def generate_multi_perspective(llm, sequence: dict, timeout: int, max_retries: int = 3) -> dict:
    """
    一次性生成5个视角的文档增强
    
    返回格式：
    {
        "plot_summary": "情节概述",
        "appeal_analysis": "爽点分析", 
        "character_relation": "人物关系",
        "emotion_arc": "情感弧线",
        "reader_questions": ["读者可能问的问题"]
    }
    """
    prompt = f"""你是一个网文分析专家。请从以下5个视角对这段剧情进行分析和改写。

【序列信息】
名称：{sequence.get('name', '')}
功能：{sequence.get('functions', [])}
情绪：{sequence.get('emotion', '')}
爽点：{sequence.get('appeal_types', [])}
人物：{sequence.get('characters', [])}
剧情：{sequence.get('plot', '')[:800]}

请输出JSON格式，包含以下字段：

{{
    "plot_summary": "用2-3句话概括情节（发生了什么，怎么解决的，结果如何）",
    "appeal_analysis": "从爽点角度分析这段剧情的吸引力（为什么读者会觉得爽，用了什么手法）",
    "character_relation": "描述本序列中主要人物之间的关系和互动（谁对谁做了什么，反应如何）",
    "emotion_arc": "描述读者阅读时的情绪变化过程（从什么情绪到什么情绪，转折点在哪）",
    "reader_questions": ["读者可能会问的3-5个问题，如'李白为什么要这样做'、'郑屠是谁'等"]
}}

只输出JSON，不要其他内容。"""

    for attempt in range(max_retries):
        try:
            response = llm.invoke(prompt)
            content = response.content
            
            # 清理JSON
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content.strip())
            
            # 提取JSON
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                data = json.loads(match.group())
                return data
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"\n    重试 {attempt+2}/{max_retries}...", end=" ", flush=True)
                time.sleep(2)
            else:
                print(f"\n    失败: {e}")
    
    return {
        "plot_summary": "",
        "appeal_analysis": "",
        "character_relation": "",
        "emotion_arc": "",
        "reader_questions": []
    }


def create_slices(outline: dict, enrichments: dict) -> dict:
    """创建多维度切片"""
    slices = {
        "plot": [],
        "character": [],
        "emotion": [],
        "function": []
    }
    
    characters_db = {c["name"]: c.get("desc", "") for c in outline.get("characters", [])}
    
    for i, seq in enumerate(outline.get("sequences", [])):
        seq_id = f"seq_{i+1:03d}"
        enrichment = enrichments.get(seq_id, {})
        
        # 构建检索文本（摘要 + 多视角改写）
        search_parts = []
        
        # 基础信息
        search_parts.append(f"[{seq.get('name', '')}]")
        search_parts.append(f"功能: {','.join(seq.get('functions', []))}")
        search_parts.append(f"爽点: {','.join(seq.get('appeal_types', []))}")
        search_parts.append(f"人物: {','.join(seq.get('characters', []))}")
        search_parts.append(f"情绪: {seq.get('emotion', '')}")
        
        # 多视角改写
        if enrichment.get('plot_summary'):
            search_parts.append(f"情节: {enrichment['plot_summary']}")
        if enrichment.get('appeal_analysis'):
            search_parts.append(f"爽点分析: {enrichment['appeal_analysis']}")
        if enrichment.get('character_relation'):
            search_parts.append(f"人物关系: {enrichment['character_relation']}")
        if enrichment.get('emotion_arc'):
            search_parts.append(f"情绪变化: {enrichment['emotion_arc']}")
        
        search_text = "\n".join(search_parts)
        
        # 问题列表
        questions = enrichment.get('reader_questions', [])
        
        # ========== 剧情维度 ==========
        slices["plot"].append({
            "id": seq_id,
            "name": seq.get("name", ""),
            "text": seq.get("plot", ""),
            "search_text": search_text,
            "tags": {
                "functions": seq.get("functions", []),
                "emotion": seq.get("emotion", ""),
                "appeal_types": seq.get("appeal_types", []),
                "characters": seq.get("characters", [])
            },
            "questions": questions,
            "enrichment": enrichment
        })
        
        # ========== 人物维度 ==========
        for char_name in seq.get("characters", []):
            char_desc = characters_db.get(char_name, "")
            char_search = f"[人物] {char_name}\n"
            char_search += f"序列: {seq.get('name', '')}\n"
            char_search += f"角色描述: {char_desc}\n"
            if enrichment.get('character_relation') and char_name in enrichment['character_relation']:
                char_search += f"互动: {enrichment['character_relation']}"
            
            slices["character"].append({
                "id": f"{seq_id}_{char_name}",
                "name": f"{char_name}在{seq.get('name', '')}",
                "text": seq.get("plot", ""),
                "search_text": char_search,
                "tags": {
                    "character": char_name,
                    "sequence": seq.get("name", ""),
                    "role": "主角" if i == 0 else "配角"
                },
                "questions": [f"{char_name}在{seq.get('name', '')}中做了什么？"]
            })
        
        # ========== 爽点维度 ==========
        emotion_str = seq.get("emotion", "")
        if emotion_str and "→" in emotion_str:
            phases = emotion_str.split("→")
            for phase in phases:
                phase = phase.strip()
                phase_search = f"[爽点] {seq.get('name', '')} {phase}阶段\n"
                phase_search += f"爽点类型: {','.join(seq.get('appeal_types', []))}\n"
                if enrichment.get('emotion_arc'):
                    phase_search += f"情绪分析: {enrichment['emotion_arc']}"
                
                slices["emotion"].append({
                    "id": f"{seq_id}_{phase}",
                    "name": f"{seq.get('name', '')}-{phase}阶段",
                    "text": seq.get("plot", ""),
                    "search_text": phase_search,
                    "tags": {
                        "phase": phase,
                        "appeal_types": seq.get("appeal_types", []),
                        "sequence": seq.get("name", "")
                    },
                    "questions": [f"{seq.get('name', '')}的{phase}阶段是怎样的？"]
                })
        
        # ========== 功能维度 ==========
        for func in seq.get("functions", []):
            func_search = f"[功能] {seq.get('name', '')} {func}\n"
            func_search += f"功能类型: {func}\n"
            if enrichment.get('plot_summary'):
                func_search += f"情节: {enrichment['plot_summary']}"
            
            slices["function"].append({
                "id": f"{seq_id}_{func}",
                "name": f"{seq.get('name', '')}-{func}",
                "text": seq.get("plot", ""),
                "search_text": func_search,
                "tags": {
                    "function": func,
                    "sequence": seq.get("name", "")
                },
                "questions": [f"{seq.get('name', '')}如何实现{func}？"]
            })
    
    return slices


def save_slices(slices: dict, output_dir: Path):
    """保存切片到MD文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for dimension, slice_list in slices.items():
        dim_dir = output_dir / dimension
        dim_dir.mkdir(exist_ok=True)
        
        for slice_unit in slice_list:
            md_path = dim_dir / f"{slice_unit['id']}.md"
            
            # 构建MD内容
            md_lines = [
                f"# {slice_unit['name']}",
                "",
                f"**维度**: {dimension}",
                f"**ID**: {slice_unit['id']}",
                f"**标签**: {json.dumps(slice_unit['tags'], ensure_ascii=False)}",
                "",
                "---",
                "",
                "## 检索文本",
                slice_unit['search_text'],
                "",
                "---",
                "",
                "## 附加问题"
            ]
            
            for q in slice_unit.get('questions', []):
                md_lines.append(f"- {q}")
            
            md_lines.extend([
                "",
                "---",
                "",
                "## 完整内容",
                slice_unit['text']
            ])
            
            # 如果有文档增强信息
            if slice_unit.get('enrichment'):
                enrichment = slice_unit['enrichment']
                md_lines.extend([
                    "",
                    "---",
                    "",
                    "## 文档增强"
                ])
                if enrichment.get('plot_summary'):
                    md_lines.extend(["", "### 情节概述", enrichment['plot_summary']])
                if enrichment.get('appeal_analysis'):
                    md_lines.extend(["", "### 爽点分析", enrichment['appeal_analysis']])
                if enrichment.get('character_relation'):
                    md_lines.extend(["", "### 人物关系", enrichment['character_relation']])
                if enrichment.get('emotion_arc'):
                    md_lines.extend(["", "### 情感弧线", enrichment['emotion_arc']])
            
            md_path.write_text('\n'.join(md_lines), encoding='utf-8')
    
    # 保存索引
    index = {
        "dimensions": {
            dim: {
                "count": len(slice_list),
                "ids": [s['id'] for s in slice_list]
            }
            for dim, slice_list in slices.items()
        }
    }
    
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def main():
    parser = argparse.ArgumentParser(description='步骤6：多维度切片+文档增强')
    parser.add_argument('--input', '-i', default='output/05_outline')
    parser.add_argument('--output', '-o', default='output/06_slices')
    parser.add_argument('--timeout', '-t', type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument('--skip-enrichment', action='store_true', help='跳过文档增强')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("步骤6：多维度切片 + 文档增强")
    print("="*60)
    
    input_dir = Path(args.input)
    outline = load_outline(input_dir)
    
    if not outline.get("sequences"):
        print("✗ 没有找到序列数据")
        return
    
    print(f"加载outline: {len(outline.get('sequences', []))}个序列")
    
    # 文档增强
    enrichments = {}
    if not args.skip_enrichment:
        print(f"\n生成多视角文档增强...")
        llm = create_llm(request_timeout=args.timeout)
        
        if llm:
            sequences = outline.get("sequences", [])
            total = len(sequences)
            start_time = time.time()
            success_count = 0
            
            # 加载已完成的（断点续传）
            progress_file = Path(args.output) / ".progress.json"
            if progress_file.exists():
                enrichments = json.loads(progress_file.read_text(encoding='utf-8'))
                print(f"  发现已完成的进度: {len(enrichments)}个")
            
            for i, seq in enumerate(sequences):
                seq_id = f"seq_{i+1:03d}"
                
                # 跳过已完成的
                if seq_id in enrichments:
                    print(f"  [{i+1}/{total}] {seq.get('name', '')}... 已存在，跳过")
                    success_count += 1
                    continue
                
                # 进度条
                bar_len = 30
                filled = int(bar_len * (i + 1) / total)
                bar = '█' * filled + '░' * (bar_len - filled)
                elapsed = time.time() - start_time
                avg_time = elapsed / (i + 1) if i > 0 else 0
                eta = avg_time * (total - i - 1)
                
                print(f"\r  [{bar}] {i+1}/{total} {seq.get('name', '')[:20]:<20} ", end="", flush=True)
                
                enrichment = generate_multi_perspective(llm, seq, args.timeout)
                enrichments[seq_id] = enrichment
                
                if enrichment.get('plot_summary'):
                    success_count += 1
                    print(f"✓", end="", flush=True)
                else:
                    print(f"⚠", end="", flush=True)
                
                # 保存进度
                Path(args.output).mkdir(parents=True, exist_ok=True)
                progress_file.write_text(json.dumps(enrichments, ensure_ascii=False), encoding='utf-8')
            
            elapsed = time.time() - start_time
            print(f"\n\n  完成: {success_count}/{total}")
            print(f"  耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
            
            # 删除进度文件
            if progress_file.exists():
                progress_file.unlink()
        else:
            print("  ⚠ LLM未初始化，跳过文档增强")
    
    # 创建切片
    print(f"\n创建多维度切片...")
    slices = create_slices(outline, enrichments)
    
    for dim, slice_list in slices.items():
        print(f"  {dim}: {len(slice_list)}个切片")
    
    # 保存
    output_dir = Path(args.output)
    save_slices(slices, output_dir)
    print(f"\n✓ 保存到: {output_dir}/")


if __name__ == "__main__":
    main()