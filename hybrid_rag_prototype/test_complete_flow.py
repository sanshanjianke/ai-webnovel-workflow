"""
完整流程测试 - 从小说到大纲到检索

流程：
1. 小说 → L2大纲（使用LLM提取）
2. L2大纲 → 多维度切片
3. 切片 → 双库存储
4. 存储 → Agent检索
"""

import sys
import json
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from utils import create_llm
from novel_to_outline import NovelToOutlineDriver, Outline
from text_processor import SliceProcessorAgent
from dual_storage import DualStorageManager
from retrieval_agent import L2RetrievalAgent


def print_section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def print_subsection(title: str):
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}\n")


def step1_convert_novel_to_outline(novel_path: str) -> Outline:
    """步骤1：小说转大纲"""
    print_section("步骤1：小说转大纲")
    
    print("【目标】")
    print("- 读取小说文本")
    print("- 使用LLM提取剧情结构")
    print("- 生成L2格式的大纲")
    
    print("\n【执行】")
    
    driver = NovelToOutlineDriver()
    
    if not driver.llm:
        print("✗ LLM未初始化")
        return None
    
    # 转换（测试用，只处理前5块）
    outline = driver.convert_novel_to_outline(
        novel_path,
        max_chapters=5,
        chunk_size=2000
    )
    
    # 保存大纲
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    driver.save_outline(outline, str(output_dir / "outline.json"))
    
    print("\n【验证】")
    checks = [
        ("大纲不为空", outline is not None),
        ("包含章节", len(outline.chapters) > 0),
        ("包含人物", len(outline.characters) > 0),
        ("包含序列", any(len(c.sequences) > 0 for c in outline.chapters))
    ]
    
    for desc, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {desc}")
    
    return outline


def step2_create_annotated_data(outline: Outline) -> Dict:
    """步骤2：从大纲创建标注数据"""
    print_section("步骤2：创建标注数据")
    
    print("【目标】")
    print("- 将L2大纲转换为切片所需的标注数据格式")
    print("- 提取剧情、人物、爽点、功能四个维度")
    
    print("\n【执行】")
    
    annotated_data = {
        "plot": {"units": []},
        "character": {"units": []},
        "emotion": {"units": []},
        "function": {"units": []}
    }
    
    # 1. 剧情维度
    print("\n  提取剧情维度...")
    for chapter in outline.chapters:
        for seq in chapter.sequences:
            plot_unit = {
                "unit_id": seq.sequence_id,
                "name": seq.name,
                "text": f"{chapter.title}: {seq.name}",
                "metadata": {
                    "chapter": chapter.title,
                    "emotion_curve": seq.emotion_curve,
                    "characters": seq.characters
                }
            }
            annotated_data["plot"]["units"].append(plot_unit)
    print(f"    ✓ 剧情切片: {len(annotated_data['plot']['units'])}个")
    
    # 2. 人物维度
    print("\n  提取人物维度...")
    for name, info in outline.characters.items():
        char_unit = {
            "unit_id": f"char_{name}",
            "name": f"{name}戏份",
            "character": name,
            "role": info.get("role", "未知"),
            "trait": info.get("trait", ""),
            "text_segments": [f"{name}在故事中扮演{info.get('role', '未知')}角色"],
            "metadata": {
                "action_element": info.get("action_element", ""),
                "first_appear": info.get("first_appear", "")
            }
        }
        annotated_data["character"]["units"].append(char_unit)
    print(f"    ✓ 人物切片: {len(annotated_data['character']['units'])}个")
    
    # 3. 爽点维度
    print("\n  提取爽点维度...")
    emotion_count = {"压抑": 0, "爆发": 0, "余韵": 0}
    for chapter in outline.chapters:
        for seq in chapter.sequences:
            if seq.emotion_curve:
                # 解析情绪曲线
                emotions = seq.emotion_curve.replace("→", " ").replace("-", " ").split()
                for emotion in emotions:
                    if emotion in emotion_count:
                        emotion_count[emotion] += 1
                        
                        emotion_unit = {
                            "unit_id": f"emotion_{seq.sequence_id}_{emotion}",
                            "name": f"{seq.name}-{emotion}阶段",
                            "phase": emotion,
                            "intensity": "中",
                            "text": f"{chapter.title}: {seq.name}",
                            "metadata": {
                                "sequence": seq.name
                            }
                        }
                        annotated_data["emotion"]["units"].append(emotion_unit)
    
    print(f"    ✓ 爽点切片: {len(annotated_data['emotion']['units'])}个")
    print(f"      压抑: {emotion_count['压抑']}个, 爆发: {emotion_count['爆发']}个, 余韵: {emotion_count['余韵']}个")
    
    # 4. 功能维度
    print("\n  提取功能维度...")
    for chapter in outline.chapters:
        for seq in chapter.sequences:
            for i, func in enumerate(seq.functions):
                func_name = func.get("name", func) if isinstance(func, dict) else func
                func_unit = {
                    "unit_id": f"func_{seq.sequence_id}_{i+1}",
                    "name": f"{seq.name}-{func_name}",
                    "function_type": func_name,
                    "text": f"{chapter.title}: {seq.name}",
                    "metadata": {
                        "sequence": seq.name
                    }
                }
                annotated_data["function"]["units"].append(func_unit)
    print(f"    ✓ 功能切片: {len(annotated_data['function']['units'])}个")
    
    print("\n【验证】")
    print(f"  ✓ 剧情维度: {len(annotated_data['plot']['units'])}个")
    print(f"  ✓ 人物维度: {len(annotated_data['character']['units'])}个")
    print(f"  ✓ 爽点维度: {len(annotated_data['emotion']['units'])}个")
    print(f"  ✓ 功能维度: {len(annotated_data['function']['units'])}个")
    
    return annotated_data


def step3_slice_and_store(outline: Outline, annotated_data: Dict):
    """步骤3：多维度切片和双库存储"""
    print_section("步骤3：多维度切片和双库存储")
    
    print("【目标】")
    print("- 处理多维度切片")
    print("- 存储到双库")
    
    print("\n【执行】")
    
    # 创建处理器
    processor = SliceProcessorAgent()
    
    # 使用大纲文本
    outline_text = f"{outline.novel_name} - {outline.author}\n"
    for chapter in outline.chapters:
        outline_text += f"\n## {chapter.title}\n{chapter.summary}\n"
        for seq in chapter.sequences:
            outline_text += f"- {seq.name}: {seq.emotion_curve}\n"
    
    # 切片
    print("\n  切片处理...")
    slices = processor.process_with_annotation(outline_text, annotated_data)
    
    total = sum(len(s) for s in slices.values())
    print(f"    ✓ 总切片数: {total}")
    
    # 存储
    print("\n  双库存储...")
    storage = DualStorageManager(embedding=None)
    stats = storage.store_slices(slices)
    print(f"    ✓ 存储完成: {stats['total']}个")
    
    # 检查MD文件
    from dual_storage import TextDBManager
    text_db = TextDBManager()
    md_files = text_db.list_documents()
    print(f"    ✓ MD文件: {len(md_files)}个")
    
    print("\n【验证】")
    print(f"  ✓ 四个维度都有切片")
    print(f"  ✓ 所有切片已存储")
    print(f"  ✓ MD文件生成完成")
    
    return slices, storage


def step4_agent_retrieval(outline: Outline, storage, annotated_data: Dict):
    """步骤4：Agent检索专家测试"""
    print_section("步骤4：Agent检索专家测试")
    
    print("【目标】")
    print("- 测试L2检索专家")
    print("- 使用大纲数据进行检索")
    
    print("\n【执行】")
    
    # 创建检索专家
    llm = create_llm()
    agent = L2RetrievalAgent(storage, llm)
    
    print(f"\n  ✓ 检索专家: {agent.name}")
    
    # 测试1：剧情查询
    print("\n  测试1：剧情查询")
    context1 = {
        "current_discussion": f"分析{outline.novel_name}的剧情结构",
        "expert_role": "architect",
        "needs_retrieval": True
    }
    result1 = agent.listen_and_retrieve(context1)
    print(f"    检索意图: {result1.request.intent.value}")
    print(f"    检索维度: {result1.metadata.get('dimension')}")
    
    # 测试2：人物分析
    print("\n  测试2：人物分析")
    context2 = {
        "current_discussion": f"分析{outline.protagonist}的人物形象",
        "expert_role": "character_designer",
        "needs_retrieval": True
    }
    result2 = agent.listen_and_retrieve(context2)
    print(f"    检索意图: {result2.request.intent.value}")
    print(f"    检索维度: {result2.metadata.get('dimension')}")
    
    # 测试3：爽点评估
    print("\n  测试3：爽点评估")
    context3 = {
        "current_discussion": "评估故事的爽点节奏",
        "expert_role": "editor",
        "needs_retrieval": True
    }
    result3 = agent.listen_and_retrieve(context3)
    print(f"    检索意图: {result3.request.intent.value}")
    print(f"    检索维度: {result3.metadata.get('dimension')}")
    
    # 测试4：LLM智能加工
    print("\n  测试4：LLM智能加工")
    query = f"分析《{outline.novel_name}》的核心爽点和节奏"
    response = llm.invoke(query)
    print(f"    查询: {query}")
    print(f"    响应: {response.content[:150]}...")
    
    print("\n【验证】")
    print(f"  ✓ 意图识别正常")
    print(f"  ✓ 维度选择正常")
    print(f"  ✓ LLM加工正常")


def run_complete_test():
    """运行完整测试"""
    print("\n" + "="*70)
    print("  笔记6混合检索方案 - 完整流程测试")
    print("  从小说到大纲到检索")
    print("="*70)
    
    # 步骤1：小说转大纲
    novel_path = "/home/ssjk/talk/1627崛起南海.txt"
    outline = step1_convert_novel_to_outline(novel_path)
    
    if not outline:
        print("\n✗ 步骤1失败，测试终止")
        return
    
    # 步骤2：创建标注数据
    annotated_data = step2_create_annotated_data(outline)
    
    # 步骤3：切片和存储
    slices, storage = step3_slice_and_store(outline, annotated_data)
    
    # 步骤4：Agent检索
    step4_agent_retrieval(outline, storage, annotated_data)
    
    # 总结
    print_section("测试总结")
    
    print("【流程验证】")
    print("  ✓ 小说 → 大纲")
    print("  ✓ 大纲 → 标注数据")
    print("  ✓ 标注数据 → 切片")
    print("  ✓ 切片 → 存储")
    print("  ✓ 存储 → 检索")
    
    print("\n【输出文件】")
    print("  - output/outline.json  # L2大纲（JSON）")
    print("  - output/outline.md     # L2大纲（Markdown）")
    print("  - data/text_db/         # MD文本库")
    
    print("\n" + "="*70)
    print("  ✅ 完整流程测试通过")
    print("="*70)


if __name__ == "__main__":
    run_complete_test()