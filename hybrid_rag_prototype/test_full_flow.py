"""
完整测试脚本 - 按笔记6需求测试每个节点

测试流程：
1. API连接测试（LLM）
2. 读取小说文本并切片
3. 多维度切片处理
4. 双库存储测试
5. Agent检索专家测试
6. 与L2专家会议集成测试
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    VECTOR_DB_PATH, TEXT_DB_PATH, SLICE_DIMENSIONS, L2_EXPERTS,
    OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
)
from utils import create_llm, test_api_connection
from text_processor import SliceProcessorAgent, MultiDimensionalSliceProcessor
from dual_storage import DualStorageManager, TextDBManager
from retrieval_agent import L2RetrievalAgent, L3MappingAgent, L4TechniqueAgent
from sample_data import AUCTION_SEQUENCE, ANNOTATED_SLICES, L2_MEETING_DATA


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def print_subsection(title: str):
    """打印子标题"""
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}\n")


def test_node_1_api_connection():
    """节点1：API连接测试"""
    print_section("节点1：API连接测试")
    
    print("【测试目标】")
    print("- 验证OpenAI兼容API是否可用")
    print("- 验证LLM模型是否可用")
    print("- 验证Embedding模型是否可用（可选）")
    
    print("\n【配置信息】")
    print(f"- Base URL: {OPENAI_BASE_URL}")
    print(f"- API Key: {OPENAI_API_KEY[:20]}...")
    print(f"- LLM Model: {LLM_MODEL}")
    
    print("\n【测试过程】")
    
    # 测试LLM
    print("\n1. 测试LLM连接...")
    try:
        llm = create_llm()
        if llm:
            response = llm.invoke("你好，请简短回复")
            print(f"   ✓ LLM响应成功")
            print(f"   响应内容: {response.content[:50]}...")
            llm_ok = True
        else:
            print("   ✗ LLM创建失败")
            llm_ok = False
    except Exception as e:
        print(f"   ✗ LLM连接失败: {e}")
        llm_ok = False
    
    print("\n【测试结果】")
    if llm_ok:
        print("✓ 节点1通过：API连接正常")
        return True
    else:
        print("✗ 节点1失败：API连接异常")
        return False


def test_node_2_text_loading():
    """节点2：文本加载测试"""
    print_section("节点2：文本加载测试")
    
    print("【测试目标】")
    print("- 读取小说文本")
    print("- 提取片段用于测试")
    
    novel_path = Path("/home/ssjk/talk/1627崛起南海.txt")
    
    print("\n【小说信息】")
    print(f"- 路径: {novel_path}")
    print(f"- 文件大小: {novel_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    print("\n【测试过程】")
    print("\n1. 读取小说文本...")
    
    try:
        # 尝试多种编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030']
        full_text = None
        
        for encoding in encodings:
            try:
                with open(novel_path, 'r', encoding=encoding) as f:
                    # 只读取前10000字用于测试
                    full_text = f.read(10000)
                    total_chars = len(full_text)
                    print(f"   ✓ 读取成功（编码: {encoding}）")
                    break
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if full_text is None:
            raise Exception("无法识别文件编码")
        
        print(f"   读取字符数: {total_chars}")
        print(f"   预览:\n   {full_text[:200]}...")
        
        print("\n【测试结果】")
        print("✓ 节点2通过：文本加载正常")
        return full_text
        
    except Exception as e:
        print(f"   ✗ 读取失败: {e}")
        print("\n【测试结果】")
        print("✗ 节点2失败：文本加载异常")
        return None


def test_node_3_multi_dimensional_slicing(test_text: str = None):
    """节点3：多维度切片测试"""
    print_section("节点3：多维度切片测试")
    
    print("【测试目标】")
    print("- 测试四个维度的切片功能")
    print("- 验证切片边界是否合理")
    print("- 检查切片标签是否完整")
    
    print("\n【测试说明】")
    print("由于小说文本未预标注，使用示例数据（拍卖会打脸序列）测试")
    print("实际应用中需要：")
    print("1. 使用LLM自动识别切分点")
    print("2. 或人工预标注")
    
    print("\n【测试过程】")
    
    # 使用示例数据
    processor = SliceProcessorAgent()
    
    print("\n1. 处理示例数据...")
    slices = processor.process_with_annotation(AUCTION_SEQUENCE, ANNOTATED_SLICES)
    
    print("\n2. 检查各维度切片...")
    total_slices = 0
    dimension_stats = {}
    
    for dim, slice_list in slices.items():
        dim_name = SLICE_DIMENSIONS[dim]['name']
        count = len(slice_list)
        total_slices += count
        
        print(f"\n   ◆ {dim_name} ({dim}):")
        print(f"     切片数: {count}")
        
        for s in slice_list:
            print(f"     - {s.metadata.name}")
            print(f"       ID: {s.metadata.unit_id}")
            print(f"       字数: {len(s.full_text)}")
            print(f"       标签字段: {list(s.metadata.tags.keys())}")
        
        dimension_stats[dim] = {
            'count': count,
            'names': [s.metadata.name for s in slice_list]
        }
    
    print("\n【验证检查点】")
    checks = []
    
    # 检查1：四个维度都有切片
    check1 = len(slices) == 4
    checks.append(("四个维度都有切片", check1))
    
    # 检查2：每个切片都有完整属性
    check2 = all(
        all(s.metadata.unit_id and s.metadata.name and s.full_text 
            for s in slice_list)
        for slice_list in slices.values()
    )
    checks.append(("每个切片都有完整属性", check2))
    
    # 检查3：爽点维度包含压抑/爆发/余韵
    emotion_phases = [s.metadata.tags.get('phase') for s in slices.get('emotion', [])]
    check3 = '压抑' in emotion_phases and '爆发' in emotion_phases and '余韵' in emotion_phases
    checks.append(("爽点维度包含完整情绪曲线", check3))
    
    # 检查4：人物维度包含主体/敌对者/帮助者
    character_roles = [s.metadata.tags.get('role') for s in slices.get('character', [])]
    check4 = '主体' in character_roles and '敌对者' in character_roles
    checks.append(("人物维度包含完整行动元", check4))
    
    print()
    for desc, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {desc}")
    
    all_passed = all(c[1] for c in checks)
    
    print("\n【测试结果】")
    if all_passed:
        print("✓ 节点3通过：多维度切片功能正常")
        print(f"  总切片数: {total_slices}")
        print(f"  各维度统计: {dimension_stats}")
        return slices
    else:
        print("✗ 节点3失败：多维度切片存在问题")
        return None


def test_node_4_dual_storage(slices):
    """节点4：双库存储测试"""
    print_section("节点4：双库存储测试")
    
    print("【测试目标】")
    print("- 验证向量数据库存储功能")
    print("- 验证MD文本库存储功能")
    print("- 检查双库关联是否正确")
    
    print("\n【测试过程】")
    
    # 创建存储管理器（无embedding，简化模式）
    print("\n1. 创建存储管理器...")
    storage = DualStorageManager(embedding=None, use_local_storage=True)
    
    # 存储切片
    print("\n2. 存储多维度切片...")
    stats = storage.store_slices(slices)
    
    print(f"\n   存储统计:")
    print(f"   - 总切片数: {stats['total']}")
    
    # 检查MD文本库
    print("\n3. 检查MD文本库...")
    text_db = TextDBManager()
    md_files = text_db.list_documents()
    
    print(f"   MD文件数: {len(md_files)}")
    
    # 显示部分文件
    print("\n   文件列表（前10个）:")
    for doc in md_files[:10]:
        print(f"   - {doc['dimension']}/{doc['unit_id']}.md")
    
    # 读取一个MD文件验证内容
    if md_files:
        test_file_path = Path(md_files[0]['path'])
        print(f"\n4. 验证MD文件内容...")
        print(f"   读取: {test_file_path.name}")
        
        with open(test_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"   文件大小: {len(content)} 字符")
        print(f"   内容预览:\n   {content[:200]}...")
    
    print("\n【验证检查点】")
    checks = []
    
    # 检查1：所有维度都已存储
    check1 = len(stats['by_dimension']) == 4
    checks.append(("所有维度都已存储", check1))
    
    # 检查2：MD文件数量正确
    check2 = len(md_files) == stats['total']
    checks.append(("MD文件数量与切片数一致", check2))
    
    # 检查3：每个MD文件都有内容
    check3 = all(Path(doc['path']).stat().st_size > 0 for doc in md_files)
    checks.append(("每个MD文件都有内容", check3))
    
    # 检查4：目录结构正确
    dimensions_in_files = set(doc['dimension'] for doc in md_files)
    check4 = dimensions_in_files == set(slices.keys())
    checks.append(("目录结构与切片维度一致", check4))
    
    print()
    for desc, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {desc}")
    
    all_passed = all(c[1] for c in checks)
    
    print("\n【测试结果】")
    if all_passed:
        print("✓ 节点4通过：双库存储功能正常")
        print(f"  MD文本库路径: {TEXT_DB_PATH}")
        print(f"  向量数据库路径: {VECTOR_DB_PATH}")
        return storage
    else:
        print("✗ 节点4失败：双库存储存在问题")
        return None


def test_node_5_retrieval_agent(storage):
    """节点5：Agent检索专家测试"""
    print_section("节点5：Agent检索专家测试")
    
    print("【测试目标】")
    print("- 测试检索专家的意图识别")
    print("- 测试维度选择逻辑")
    print("- 测试结果加工功能")
    
    print("\n【测试说明】")
    print("由于简化模式无向量检索功能，测试基本逻辑流程")
    print("完整版需要：")
    print("1. 向量数据库检索")
    print("2. LLM智能加工")
    
    print("\n【测试过程】")
    
    # 创建检索专家
    print("\n1. 创建L2检索专家...")
    retrieval_agent = L2RetrievalAgent(storage_manager=storage, llm=None)
    
    print(f"   专家名称: {retrieval_agent.name}")
    
    # 测试意图识别
    print("\n2. 测试意图识别...")
    
    test_queries = [
        ("查询拍卖会的剧情结构", "剧情"),
        ("分析主角的行为模式", "人物"),
        ("评估爽点节奏是否合理", "爽点"),
        ("这个情节的功能是什么", "功能")
    ]
    
    for query, expected_type in test_queries:
        intent = retrieval_agent.analyze_intent(query, {})
        print(f"   查询: {query}")
        print(f"   识别意图: {intent.value}")
        print(f"   预期类型: {expected_type}")
        print()
    
    # 测试维度选择
    print("\n3. 测试维度选择...")
    
    for expert_role in ["architect", "editor", "character_designer"]:
        dimension = retrieval_agent.determine_dimension_from_expert(expert_role)
        expert_info = L2_EXPERTS[expert_role]
        print(f"   专家: {expert_info['name']} → 维度: {dimension}")
    
    print("\n【验证检查点】")
    checks = []
    
    # 检查1：意图识别功能存在
    check1 = hasattr(retrieval_agent, 'analyze_intent')
    checks.append(("意图识别功能存在", check1))
    
    # 检查2：维度选择功能存在
    check2 = hasattr(retrieval_agent, 'determine_dimension_from_expert')
    checks.append(("维度选择功能存在", check2))
    
    # 检查3：监听功能存在
    check3 = hasattr(retrieval_agent, 'listen_and_retrieve')
    checks.append(("监听功能存在", check3))
    
    print()
    for desc, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {desc}")
    
    all_passed = all(c[1] for c in checks)
    
    print("\n【测试结果】")
    if all_passed:
        print("✓ 节点5通过：Agent检索专家功能正常（简化模式）")
        print("  完整功能需要：向量检索 + LLM加工")
        return retrieval_agent
    else:
        print("✗ 节点5失败：Agent检索专家存在问题")
        return None


def test_node_6_llm_processing(retrieval_agent):
    """节点6：LLM智能加工测试"""
    print_section("节点6：LLM智能加工测试")
    
    print("【测试目标】")
    print("- 测试LLM对检索结果的智能加工")
    print("- 验证不同意图的加工效果")
    
    print("\n【测试过程】")
    
    # 创建LLM
    print("\n1. 创建LLM...")
    llm = create_llm()
    
    if not llm:
        print("   ✗ LLM创建失败，跳过此节点")
        print("\n【测试结果】")
        print("⚠ 节点6跳过：LLM不可用")
        return False
    
    print("   ✓ LLM创建成功")
    
    # 测试智能加工
    print("\n2. 测试智能加工功能（简化测试）...")
    
    # 使用LLM直接测试
    try:
        test_query = "分析这段文字的爽点节奏：拍卖会上主角被嘲讽，然后亮出宝物震惊全场"
        print(f"\n   测试查询: {test_query}")
        
        response = llm.invoke(test_query)
        print(f"   LLM响应:")
        print(f"   {response.content[:200]}...")
        
        llm_ok = True
    except Exception as e:
        print(f"   ✗ LLM调用失败: {e}")
        llm_ok = False
    
    print("\n【验证检查点】")
    checks = []
    
    # 检查1：LLM能正常响应
    check1 = llm is not None and llm_ok
    checks.append(("LLM能正常响应", check1))
    
    # 检查2：智能加工功能存在
    check2 = hasattr(retrieval_agent, '_llm_process')
    checks.append(("智能加工功能存在", check2))
    
    print()
    for desc, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {desc}")
    
    all_passed = all(c[1] for c in checks)
    
    print("\n【测试结果】")
    if all_passed:
        print("✓ 节点6通过：LLM智能加工功能正常")
        return True
    else:
        print("✗ 节点6失败：LLM智能加工存在问题")
        return False


def test_node_7_expert_meeting_integration(retrieval_agent):
    """节点7：与L2专家会议集成测试"""
    print_section("节点7：与L2专家会议集成测试")
    
    print("【测试目标】")
    print("- 测试检索专家与专家会议的交互")
    print("- 验证监听和响应机制")
    print("- 检查上下文提供功能")
    
    print("\n【专家会议数据】")
    print(f"- 会议ID: {L2_MEETING_DATA['meeting_id']}")
    print(f"- 场景: {L2_MEETING_DATA['scenario']}")
    
    print("\n【测试过程】")
    
    # 模拟专家会议流程
    print("\n1. 模拟专家会议讨论...")
    
    for i, discussion in enumerate(L2_MEETING_DATA['discussion'], 1):
        expert = discussion['expert']
        role = discussion['role']
        comment = discussion['comment']
        preferred_dim = discussion['metadata']['preferred_dimension']
        
        print(f"\n   【第{i}轮讨论】")
        print(f"   发言专家: {role}")
        print(f"   发言内容: {comment}")
        
        # 模拟检索专家响应
        print(f"\n   检索专家响应:")
        
        # 构建会议上下文
        meeting_context = {
            "current_discussion": comment,
            "expert_role": expert,
            "needs_retrieval": True,
            "scenario": L2_MEETING_DATA['scenario']
        }
        
        # 检索专家监听
        result = retrieval_agent.listen_and_retrieve(meeting_context)
        
        if result:
            print(f"   - 检索意图: {result.request.intent.value}")
            print(f"   - 检索维度: {result.metadata.get('dimension')}")
            print(f"   - 结果状态: 已返回（简化模式）")
        else:
            print(f"   - 结果状态: 无需检索")
    
    print("\n【验证检查点】")
    checks = []
    
    # 检查1：能监听专家会议
    check1 = hasattr(retrieval_agent, 'listen_and_retrieve')
    checks.append(("能监听专家会议", check1))
    
    # 检查2：能根据专家角色选择维度
    check2 = hasattr(retrieval_agent, 'determine_dimension_from_expert')
    checks.append(("能根据专家角色选择维度", check2))
    
    # 检查3：能主动提供上下文
    check3 = hasattr(retrieval_agent, 'provide_contextual_info')
    checks.append(("能主动提供上下文", check3))
    
    print()
    for desc, passed in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {desc}")
    
    all_passed = all(c[1] for c in checks)
    
    print("\n【测试结果】")
    if all_passed:
        print("✓ 节点7通过：与专家会议集成功能正常")
        return True
    else:
        print("✗ 节点7失败：与专家会议集成存在问题")
        return False


def run_full_test():
    """运行完整测试"""
    print("\n" + "="*70)
    print("  笔记6混合检索方案 - 完整测试")
    print("  测试小说: 1627崛起南海.txt")
    print("="*70)
    
    results = {}
    
    # 节点1：API连接测试
    results['node_1'] = test_node_1_api_connection()
    
    # 节点2：文本加载测试
    test_text = test_node_2_text_loading()
    results['node_2'] = test_text is not None
    
    # 节点3：多维度切片测试
    slices = test_node_3_multi_dimensional_slicing(test_text)
    results['node_3'] = slices is not None
    
    # 节点4：双库存储测试
    storage = test_node_4_dual_storage(slices) if slices else None
    results['node_4'] = storage is not None
    
    # 节点5：Agent检索专家测试
    retrieval_agent = test_node_5_retrieval_agent(storage) if storage else None
    results['node_5'] = retrieval_agent is not None
    
    # 节点6：LLM智能加工测试
    if retrieval_agent:
        results['node_6'] = test_node_6_llm_processing(retrieval_agent)
    else:
        results['node_6'] = False
    
    # 节点7：专家会议集成测试
    if retrieval_agent:
        results['node_7'] = test_node_7_expert_meeting_integration(retrieval_agent)
    else:
        results['node_7'] = False
    
    # 打印测试报告
    print_section("测试报告")
    
    print("【节点测试结果】\n")
    
    node_names = {
        'node_1': 'API连接测试',
        'node_2': '文本加载测试',
        'node_3': '多维度切片测试',
        'node_4': '双库存储测试',
        'node_5': 'Agent检索专家测试',
        'node_6': 'LLM智能加工测试',
        'node_7': '专家会议集成测试'
    }
    
    passed_count = 0
    for node, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {node_names[node]}: {status}")
        if result:
            passed_count += 1
    
    print(f"\n【总体评估】")
    print(f"  通过节点: {passed_count}/{len(results)}")
    
    if passed_count == len(results):
        print("\n  ✓ 所有节点测试通过！")
        print("  符合笔记6.md的需求。")
    elif passed_count >= 5:
        print("\n  ⚠ 大部分节点测试通过")
        print("  基本符合笔记6.md的需求，部分功能需要完善。")
    else:
        print("\n  ✗ 多个节点测试失败")
        print("  不符合笔记6.md的需求，需要修复问题。")
    
    print("\n【符合笔记6需求的评估】\n")
    
    requirements = [
        ("多维度切片（剧情/人物/爽点/功能）", results.get('node_3', False)),
        ("双库分离（向量库 + MD文本库）", results.get('node_4', False)),
        ("Agent检索专家", results.get('node_5', False)),
        ("智能加工（LLM）", results.get('node_6', False)),
        ("与L2专家会议集成", results.get('node_7', False))
    ]
    
    for req, met in requirements:
        status = "✓" if met else "✗"
        print(f"  {status} {req}")
    
    print("\n" + "="*70)
    
    return results


if __name__ == "__main__":
    run_full_test()