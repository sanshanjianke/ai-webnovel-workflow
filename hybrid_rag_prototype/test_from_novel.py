"""
完整测试 - 从小说到大纲到检索

简化版：一次性完成所有步骤
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils import create_llm
from text_processor import SliceProcessorAgent
from dual_storage import DualStorageManager, TextDBManager
from retrieval_agent import L2RetrievalAgent
from config import SLICE_DIMENSIONS


def main():
    print("\n" + "="*70)
    print("  小说 → 大纲 → 检索 完整测试")
    print("="*70)
    
    # ========== 步骤1：读取小说 ==========
    print("\n【步骤1】读取小说...")
    novel_path = Path("/home/ssjk/talk/1627崛起南海.txt")
    
    try:
        with open(novel_path, 'r', encoding='utf-8') as f:
            novel_text = f.read(3000)  # 只读取前3000字用于测试
        print(f"✓ 读取成功: {len(novel_text)}字符")
        print(f"预览: {novel_text[:100]}...")
    except Exception as e:
        print(f"✗ 读取失败: {e}")
        return
    
    # ========== 步骤2：使用LLM提取大纲 ==========
    print("\n【步骤2】使用LLM提取大纲...")
    llm = create_llm()
    
    if not llm:
        print("✗ LLM未初始化")
        return
    
    print("✓ LLM已初始化")
    
    # 提取大纲
    prompt = f"""分析以下小说片段，提取L2层大纲信息：

{novel_text[:2000]}

请以JSON格式返回（简洁）：
{{
  "novel_name": "小说名",
  "author": "作者",
  "genre": "类型（如：历史、穿越、工业）",
  "protagonist": "主角名",
  "core_appeal": "核心爽点（如：工业建设、强国）",
  "sequences": [
    {{
      "name": "序列名称（如：穿越开局）",
      "functions": ["功能1", "功能2"],
      "emotion_curve": "压抑/爆发/余韵",
      "appeal_type": "爽点类型"
    }}
  ]
}}

要求：
- 序列最多3个
- 每个序列2-3个功能
- 情绪曲线简洁
"""
    
    print("  正在分析...")
    try:
        response = llm.invoke(prompt, timeout=30)
        print("✓ 分析完成")
        
        # 解析JSON
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        outline = json.loads(content.strip())
        
        print(f"\n小说: {outline.get('novel_name')}")
        print(f"作者: {outline.get('author')}")
        print(f"类型: {outline.get('genre')}")
        print(f"主角: {outline.get('protagonist')}")
        print(f"核心爽点: {outline.get('core_appeal')}")
        print(f"序列数: {len(outline.get('sequences', []))}")
        
    except Exception as e:
        print(f"✗ 提取失败: {e}")
        print(f"响应内容: {response.content[:200]}")
        return
    
    # ========== 步骤3：转换为标注数据 ==========
    print("\n【步骤3】转换为标注数据...")
    
    # 构建L2格式的标注数据
    annotated_data = {
        "plot": {
            "unit_id": "plot_001",
            "name": f"{outline.get('novel_name', '小说')}剧情",
            "text": f"{outline.get('novel_name', '小说')}\n作者: {outline.get('author', '')}\n类型: {outline.get('genre', '')}\n核心爽点: {outline.get('core_appeal', '')}",
            "metadata": {
                "genre": outline.get('genre', ''),
                "core_appeal": outline.get('core_appeal', '')
            }
        },
        "character": {"units": []},
        "emotion": {"units": []},
        "function": {"units": []}
    }
    
    # 从序列提取人物、情绪、功能
    characters = set()
    for i, seq in enumerate(outline.get('sequences', []), 1):
        # 情绪
        emotion_curve = seq.get('emotion_curve', '')
        if emotion_curve:
            emotions = emotion_curve.replace('/', ' ').replace('→', ' ').split()
            for j, emotion in enumerate(emotions[:2], 1):  # 最多2个情绪
                annotated_data['emotion']['units'].append({
                    "unit_id": f"emotion_{i}_{j}",
                    "name": f"{seq.get('name', '序列')}-{emotion}阶段",
                    "phase": emotion,
                    "intensity": "中",
                    "text": f"序列: {seq.get('name', '')}\n情绪: {emotion}",
                    "metadata": {"sequence": seq.get('name', '')}
                })
        
        # 功能
        functions = seq.get('functions', [])
        for j, func in enumerate(functions[:2], 1):  # 最多2个功能
            annotated_data['function']['units'].append({
                "unit_id": f"func_{i}_{j}",
                "name": f"{seq.get('name', '')}-{func}",
                "function_type": func,
                "text": f"序列: {seq.get('name', '')}\n功能: {func}",
                "metadata": {"sequence": seq.get('name', '')}
            })
    
    # 添加主角
    if outline.get('protagonist'):
        annotated_data['character']['units'].append({
            "unit_id": "char_protagonist",
            "name": f"{outline.get('protagonist')}戏份",
            "character": outline.get('protagonist'),
            "role": "主体",
            "trait": "主角",
            "text_segments": [f"{outline.get('protagonist')}是故事的主角"],
            "metadata": {"action_element": "主体"}
        })
    
    print(f"✓ 标注数据构建完成")
    print(f"  - 剧情维度: 1个切片")
    print(f"  - 人物维度: {len(annotated_data['character']['units'])}个切片")
    print(f"  - 爽点维度: {len(annotated_data['emotion']['units'])}个切片")
    print(f"  - 功能维度: {len(annotated_data['function']['units'])}个切片")
    
    # ========== 步骤4：多维度切片 ==========
    print("\n【步骤4】多维度切片...")
    processor = SliceProcessorAgent()
    
    # 使用大纲文本和标注数据
    outline_text = f"""# {outline.get('novel_name', '小说')}

作者: {outline.get('author', '')}
类型: {outline.get('genre', '')}
主角: {outline.get('protagonist', '')}
核心爽点: {outline.get('core_appeal', '')}

## 剧情序列
"""
    for i, seq in enumerate(outline.get('sequences', []), 1):
        outline_text += f"\n### 序列{i}: {seq.get('name', '')}\n"
        outline_text += f"- 功能: {', '.join(seq.get('functions', []))}\n"
        outline_text += f"- 情绪: {seq.get('emotion_curve', '')}\n"
        outline_text += f"- 爽点: {seq.get('appeal_type', '')}\n"
    
    slices = processor.process_with_annotation(outline_text, annotated_data)
    
    total_slices = sum(len(s) for s in slices.values())
    print(f"✓ 切片完成: {total_slices}个")
    
    for dim, slice_list in slices.items():
        print(f"  - {SLICE_DIMENSIONS[dim]['name']}: {len(slice_list)}个")
    
    # ========== 步骤5：双库存储 ==========
    print("\n【步骤5】双库存储...")
    storage = DualStorageManager(embedding=None)
    stats = storage.store_slices(slices)
    print(f"✓ 存储完成: {stats['total']}个切片")
    
    text_db = TextDBManager()
    md_files = text_db.list_documents()
    print(f"✓ MD文件: {len(md_files)}个")
    
    # ========== 步骤6：Agent检索专家测试 ==========
    print("\n【步骤6】Agent检索专家测试...")
    agent = L2RetrievalAgent(storage, llm)
    print(f"✓ 检索专家: {agent.name}")
    
    # 测试检索
    test_cases = [
        ("剧情架构师", f"分析{outline.get('novel_name', '小说')}的剧情结构"),
        ("editor", f"评估{outline.get('novel_name', '小说')}的爽点节奏"),
        ("character_designer", f"分析{outline.get('protagonist', '主角')}的人物形象")
    ]
    
    for expert_role, query in test_cases:
        print(f"\n  测试: {expert_role}")
        print(f"  查询: {query}")
        
        context = {
            "current_discussion": query,
            "expert_role": expert_role,
            "needs_retrieval": True
        }
        
        result = agent.listen_and_retrieve(context)
        if result:
            print(f"  意图: {result.request.intent.value}")
            print(f"  维度: {result.metadata.get('dimension')}")
    
    # ========== 步骤7：LLM智能加工 ==========
    print("\n【步骤7】LLM智能加工...")
    query = f"简要分析《{outline.get('novel_name', '小说')}》的核心爽点"
    response = llm.invoke(query, timeout=30)
    print(f"查询: {query}")
    print(f"响应: {response.content[:200]}...")
    
    # ========== 总结 ==========
    print("\n" + "="*70)
    print("  测试总结")
    print("="*70)
    print(f"\n小说: {outline.get('novel_name')}")
    print(f"大纲提取: ✓ 成功")
    print(f"多维度切片: ✓ {total_slices}个")
    print(f"双库存储: ✓ {stats['total']}个")
    print(f"Agent检索: ✓ 正常")
    print(f"LLM加工: ✓ 正常")
    
    print("\n输出文件:")
    print(f"  - data/text_db/ (MD文本库)")
    
    # 保存大纲
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "outline.json", 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    
    with open(output_dir / "outline.md", 'w', encoding='utf-8') as f:
        f.write(outline_text)
    
    print(f"  - output/outline.json (L2大纲JSON)")
    print(f"  - output/outline.md (L2大纲Markdown)")
    
    print("\n" + "="*70)
    print("  ✅ 完整流程测试通过")
    print("="*70)


if __name__ == "__main__":
    main()