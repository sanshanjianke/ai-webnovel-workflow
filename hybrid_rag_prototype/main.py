"""
主入口 - 笔记6混合检索方案原型演示

演示完整流程：
1. 加载示例数据（拍卖会打脸序列）
2. 多维度切片处理
3. 双库存储（向量库 + MD文本库）
4. Agent检索专家工作流演示
5. 与L2专家会议集成演示
"""

from pathlib import Path
import os
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from config import VECTOR_DB_PATH, TEXT_DB_PATH, SLICE_DIMENSIONS, L2_EXPERTS
from sample_data import AUCTION_SEQUENCE, ANNOTATED_SLICES, L2_MEETING_DATA
from text_processor import SliceProcessorAgent, save_slices_to_files
from dual_storage import DualStorageManager, TextDBManager
from retrieval_agent import L2RetrievalAgent, L3MappingAgent, L4TechniqueAgent, RetrievalIntent


def print_banner(title: str):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}\n")


def demo_step_1_load_data():
    """步骤1：加载示例数据"""
    print_banner("步骤1：加载示例数据")
    
    print(f"【原始剧情文本】")
    print(f"- 名称: 拍卖会打脸序列")
    print(f"- 字数: {len(AUCTION_SEQUENCE)} 字")
    print(f"- 预览:\n{AUCTION_SEQUENCE[:200]}...\n")
    
    print(f"【标注数据】")
    print(f"- 剧情维度: 1个完整序列")
    print(f"- 人物维度: {len(ANNOTATED_SLICES['character']['units'])}个角色戏份")
    print(f"- 爽点维度: {len(ANNOTATED_SLICES['emotion']['units'])}个情绪阶段")
    print(f"- 功能维度: {len(ANNOTATED_SLICES['function']['units'])}个叙事功能")


def demo_step_2_slice_processing():
    """步骤2：多维度切片处理"""
    print_banner("步骤2：多维度切片处理")
    
    # 创建切片处理器
    processor = SliceProcessorAgent()
    
    # 处理切片
    slices = processor.process_with_annotation(AUCTION_SEQUENCE, ANNOTATED_SLICES)
    
    # 打印结果
    print("【切片结果统计】\n")
    for dim, slice_list in slices.items():
        dim_name = SLICE_DIMENSIONS[dim]['name']
        print(f"◆ {dim_name} ({dim}): {len(slice_list)}个切片")
        
        for s in slice_list:
            print(f"  ├─ {s.metadata.name}")
            print(f"  │  ID: {s.metadata.unit_id}")
            print(f"  │  摘要: {s.summary[:60]}...")
            if s.metadata.tags:
                tags_str = ", ".join([f"{k}={v}" for k, v in list(s.metadata.tags.items())[:3]])
                print(f"  │  标签: {tags_str}")
    
    # 保存切片文件（用于调试）
    output_dir = Path("demo_slices_output")
    save_slices_to_files(slices, output_dir)
    print(f"\n切片JSON文件已保存到: {output_dir}")
    
    return slices


def demo_step_3_dual_storage(slices):
    """步骤3：双库存储"""
    print_banner("步骤3：双库存储（向量库 + MD文本库）")
    
    # 创建存储管理器（无embedding，演示模式）
    storage = DualStorageManager(embedding=None, use_local_storage=True)
    
    # 存储切片
    stats = storage.store_slices(slices)
    
    print(f"【存储统计】")
    print(f"- 总切片数: {stats['total']}")
    print(f"\n各维度存储:")
    for dim, dim_stats in stats['by_dimension'].items():
        print(f"  ◆ {SLICE_DIMENSIONS[dim]['name']}: {dim_stats['count']}个")
        for id in dim_stats['ids'][:3]:
            print(f"    ├─ ID: {id}")
    
    print(f"\n【存储路径】")
    print(f"- 向量数据库: {VECTOR_DB_PATH}")
    print(f"- MD文本库: {TEXT_DB_PATH}")
    
    # 查看MD文件
    text_db = TextDBManager()
    docs = text_db.list_documents()
    print(f"\n【已存储的MD文件】共{len(docs)}个:")
    for doc in docs[:10]:
        print(f"  ├─ {doc['dimension']}/{doc['unit_id']}.md")
    
    return storage


def demo_step_4_retrieval_agent(storage):
    """步骤4：Agent检索专家工作流"""
    print_banner("步骤4：Agent检索专家工作流")
    
    # 创建L2检索专家（无LLM，演示模式）
    retrieval_agent = L2RetrievalAgent(storage_manager=storage, llm=None)
    
    print(f"【检索专家角色】")
    print(f"- 名称: {retrieval_agent.name}")
    print(f"- 功能: 监听专家会议，智能检索，加工结果")
    
    # 场景1：剧情架构师查询
    print(f"\n{'─'*60}")
    print(f"【场景1：剧情架构师查询完整剧情】\n")
    
    meeting_context_1 = {
        "current_discussion": "查询拍卖会打脸的完整剧情序列",
        "expert_role": "architect",
        "needs_retrieval": True,
        "scenario": "拍卖会打脸"
    }
    
    result_1 = retrieval_agent.listen_and_retrieve(meeting_context_1)
    
    if result_1:
        print(f"检索意图: {result_1.request.intent.value}")
        print(f"检索维度: {result_1.metadata.get('dimension')}")
        print(f"检索结果（加工后，前300字）:")
        print(f"{result_1.processed_content[:300]}...")
    
    # 场景2：网络编辑评估爽点
    print(f"\n{'─'*60}")
    print(f"【场景2：网络编辑评估爽点节奏】\n")
    
    meeting_context_2 = {
        "current_discussion": "评估拍卖会打脸的情绪曲线和爽点强度",
        "expert_role": "editor",
        "needs_retrieval": True,
        "scenario": "拍卖会打脸"
    }
    
    result_2 = retrieval_agent.listen_and_retrieve(meeting_context_2)
    
    if result_2:
        print(f"检索意图: {result_2.request.intent.value}")
        print(f"检索维度: {result_2.metadata.get('dimension')}")
        print(f"检索结果（加工后，前300字）:")
        print(f"{result_2.processed_content[:300]}...")
    
    # 场景3：人物设计师分析角色
    print(f"\n{'─'*60}")
    print(f"【场景3：人物设计师分析主角行为】\n")
    
    meeting_context_3 = {
        "current_discussion": "分析主角林尘在拍卖会中的行为模式",
        "expert_role": "character_designer",
        "needs_retrieval": True,
        "scenario": "拍卖会打脸"
    }
    
    result_3 = retrieval_agent.listen_and_retrieve(meeting_context_3)
    
    if result_3:
        print(f"检索意图: {result_3.request.intent.value}")
        print(f"检索维度: {result_3.metadata.get('dimension')}")
        print(f"检索结果（加工后，前300字）:")
        print(f"{result_3.processed_content[:300]}...")
    
    return retrieval_agent


def demo_step_5_expert_meeting(retrieval_agent):
    """步骤5：与L2专家会议集成"""
    print_banner("步骤5：与L2专家会议集成演示")
    
    print(f"【专家会议数据】")
    print(f"- 会议ID: {L2_MEETING_DATA['meeting_id']}")
    print(f"- 场景: {L2_MEETING_DATA['scenario']}")
    
    print(f"\n【专家讨论流程】\n")
    
    for discussion in L2_MEETING_DATA['discussion']:
        expert = discussion['expert']
        role = discussion['role']
        comment = discussion['comment']
        preferred_dim = discussion['metadata']['preferred_dimension']
        
        print(f"◆ {role} 发言:")
        print(f"  {comment}")
        
        # 检索专家监听并响应
        print(f"\n  检索专家响应:")
        context_info = retrieval_agent.provide_contextual_info(expert, L2_MEETING_DATA['scenario'])
        print(f"  主动提供{SLICE_DIMENSIONS[preferred_dim]['name']}信息:")
        print(f"  {context_info[:200]}...")
        
        print(f"\n{'─'*60}\n")


def demo_architecture_diagram():
    """打印架构图"""
    print_banner("混合检索方案架构图")
    
    diagram = """
┌─────────────────────────────────────────────────────────────┐
│                    笔记6混合检索方案                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────┐                                          │
│  │ L2生成长剧情   │                                          │
│  │ 文本          │                                          │
│  └───────────────┘                                          │
│         │                                                   │
│         ↓                                                   │
│  ┌───────────────┐                                          │
│  │ 切分Agent     │  多维度切片：                            │
│  │               │  - 剧情维度（序列边界）                  │
│  │               │  - 人物维度（出场/退场）                 │
│  │               │  - 爽点维度（压抑/爆发/余韵）            │
│  │               │  - 功能维度（铺垫/转折/反馈）            │
│  └───────────────┘                                          │
│         │                                                   │
│         ↓                                                   │
│  ┌───┴────┐                                                 │
│  │        │                                                 │
│  ↓        ↓                                                 │
│  ┌────┐  ┌────┐                                            │
│  │向量│  │MD  │  双库分离：                                │
│  │库  │  │文本│  - 向量库：摘要+标签+指针                  │
│  │    │  │库  │  - MD库：完整切片文本                      │
│  └────┘  └────┐                                            │
│  │        │                                                 │
│  │        │                                                 │
│  └────────┘                                                 │
│         │                                                   │
│         ↓                                                   │
│  ┌───────────────┐                                          │
│  │ 检索专家Agent │  智能加工：                              │
│  │               │  - 理解语境                              │
│  │               │  - 判断维度                              │
│  │               │  - 检索向量库                            │
│  │               │  - 获取完整文本                          │
│  │               │  - 智能加工返回                          │
│  └───────────────┘                                          │
│         │                                                   │
│         ↓                                                   │
│  ┌───────────────┐                                          │
│  │ L2专家会议    │                                          │
│  │ (剧情架构师   │                                          │
│  │  网络编辑     │                                          │
│  │  人物设计师)  │                                          │
│  └───────────────┘                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
"""
    
    print(diagram)


def demo_comparison_with_traditional_rag():
    """与传统RAG对比"""
    print_banner("与传统RAG对比")
    
    comparison = """
【传统RAG的问题】（笔记6分析）

问题1：叙事完整性破坏
- 切片只保留片段，丢失上下文关联
- 例：拍卖会打脸序列5000字，切片成5个碎片，丢失完整剧情

问题2：序列逻辑断裂
- 一个完整序列被切成多个碎片
- 例：压抑-爆发-余韵的情绪曲线被切断

问题3：边界切割问题
- 关键信息刚好切在边界处
- 例："晶核爆发"的关键信息切在两个切片边界

问题4：检索结果失真
- 返回的切片无法支撑决策
- 例：网络编辑评估爽点节奏，返回的是破碎片段


【混合检索方案的优势】

优势1：多维度语义切分
- 按叙事学概念切分，而非机械长度
- 保持序列完整、情绪曲线完整、人物戏份完整

优势2：双库分离
- 向量库快速检索（摘要+标签）
- MD库提供完整上下文

优势3：Agent智能加工
- 理解专家会议语境
- 根据不同意图，对结果做不同处理
- 剧情查询→返回完整概述
- 爽点评估→分析情绪曲线
- 人物分析→提取行为模式

优势4：与创作流程绑定
- L2/L3/L4各有专门检索专家
- 各专家优先使用自己关注的维度
"""
    
    print(comparison)


def demo_l3_l4_integration():
    """演示L3/L4检索专家"""
    print_banner("L3/L4检索专家扩展应用")
    
    print("""
【L3映射检索专家】

职责：将网文效果标签映射到叙事学技术指令

工作流：
1. 读取L2产出的精修大纲
2. 监听当前映射任务
3. 判断需要哪些映射规则（视角？节奏？话语模式？）
4. 检索L3映射关系库
5. Agent智能加工：根据具体场景选择/组合映射规则
6. 产出细纲指令

示例：
- 输入："装逼打脸-压抑阶段"
- 输出：
  {
    "视角": "反派/路人内聚焦",
    "节奏": "慢速扩述",
    "话语模式": "对话+心理",
    "理由": "通过无知者的傲慢视角，制造信息差"
  }


【L4技法检索专家】

职责：根据细纲指令检索参考文本

工作流：
1. 读取L3产出的细纲指令
2. 分析当前场景需求（视角、节奏、话语模式）
3. 检索L4微观技法库
4. Agent智能加工：筛选、组合、调整参考文本
5. 产出正文

示例：
- 输入："外聚焦 + 短句动词 + 动作描写"
- 输出：
  [
    {
      "text": "光头男人敲了敲桌子...",
      "style": "古龙式冷硬",
      "source": "古龙《流星蝴蝶剑》"
    }
  ]
""")
    
    print("""
【统一架构】

┌─────────────────────────────────────────────────┐
│                   创作模型                        │
├─────────────────────────────────────────────────┤
│  L1种子层  →  L2架构层  →  L3叙事层  →  L4渲染层  │
│                ↓           ↓           ↓        │
│           检索专家(剧情)  检索专家(映射)  检索专家(技法) │
│                ↓           ↓           ↓        │
│           ┌────┴───────────┴───────────┴────┐   │
│           ↓         Agent智能加工层          ↓   │
│           └────┬───────────┬───────────┬────┘   │
│                ↓           ↓           ↓        │
│           向量数据库    向量数据库    向量数据库    │
│           (剧情库)     (映射库)     (技法库)      │
│                ↓           ↓           ↓        │
│           MD文本库     MD文本库     MD文本库      │
└─────────────────────────────────────────────────┘
""")


def main():
    """主函数"""
    print_banner("笔记6混合检索方案原型 - LangChain实现")
    
    print("""
本原型演示了笔记6提出的混合检索方案：
1. 多维度切片（剧情/人物/爽点/功能）
2. 双库分离（向量库 + MD文本库）
3. Agent检索专家（智能加工）
4. 与L2/L3/L4创作流程集成

当前为简化演示版本：
- 无embedding向量（向量数据库功能受限）
- 无LLM智能加工（使用简单处理）
- 使用预标注数据（而非自动切片）

完整版需要：
- OpenAI Embedding（text-embedding-3-small）
- OpenAI LLM（gpt-4或gpt-3.5-turbo）
- 自动切片Agent实现
""")
    
    # 执行演示步骤
    demo_architecture_diagram()
    
    demo_step_1_load_data()
    
    slices = demo_step_2_slice_processing()
    
    storage = demo_step_3_dual_storage(slices)
    
    retrieval_agent = demo_step_4_retrieval_agent(storage)
    
    demo_step_5_expert_meeting(retrieval_agent)
    
    demo_comparison_with_traditional_rag()
    
    demo_l3_l4_integration()
    
    print_banner("演示完成")
    
    print("""
查看生成的文件：
- demo_slices_output/  : 切片JSON文件
- data/text_db/        : MD文本库

下一步：
1. 安装依赖: pip install -r requirements.txt
2. 配置OpenAI API密钥: export OPENAI_API_KEY=your_key
3. 运行完整版: python main.py --with-embedding --with-llm
4. 测试自动切片: python text_processor.py
5. 测试检索专家: python retrieval_agent.py
""")


if __name__ == "__main__":
    main()