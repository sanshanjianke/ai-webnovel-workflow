"""
Agent驱动测试 - 简单的端到端演示

模拟一个完整的Agent驱动流程：
1. 读取小说片段
2. 提取剧情序列
3. 多维度切片
4. LLM智能分析
5. 生成报告
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils import create_llm
from text_processor import SliceProcessorAgent
from dual_storage import DualStorageManager
from retrieval_agent import L2RetrievalAgent, RetrievalIntent
from sample_data import AUCTION_SEQUENCE, ANNOTATED_SLICES


class SimpleAgent:
    """简单的Agent驱动器"""
    
    def __init__(self):
        self.llm = None
        self.storage = None
        self.retrieval_agent = None
        self.slices = None
        
    def initialize(self):
        """初始化Agent"""
        print("\n" + "="*80)
        print("  Agent驱动测试 - 端到端演示")
        print("="*80)
        
        print("\n【步骤1：初始化组件】")
        
        # 创建LLM
        print("\n  1. 创建LLM...")
        self.llm = create_llm()
        if self.llm:
            print("     ✓ LLM创建成功")
        else:
            print("     ✗ LLM创建失败")
            return False
        
        # 创建存储
        print("\n  2. 创建存储管理器...")
        self.storage = DualStorageManager(embedding=None, use_local_storage=True)
        print("     ✓ 存储管理器创建成功")
        
        # 创建检索专家
        print("\n  3. 创建检索专家...")
        self.retrieval_agent = L2RetrievalAgent(
            storage_manager=self.storage,
            llm=self.llm
        )
        print(f"     ✓ 检索专家创建成功: {self.retrieval_agent.name}")
        
        return True
    
    def process_novel(self, novel_path: str = None):
        """处理小说"""
        print("\n" + "="*80)
        print("  【步骤2：处理小说】")
        print("="*80)
        
        # 如果没有提供小说路径，使用示例数据
        if novel_path:
            print(f"\n  读取小说: {novel_path}")
            try:
                with open(novel_path, 'r', encoding='utf-8') as f:
                    text = f.read(5000)  # 只读取前5000字
                print(f"     ✓ 读取成功，共{len(text)}字符")
            except Exception as e:
                print(f"     ✗ 读取失败: {e}")
                return False
        else:
            print("\n  使用示例数据（拍卖会打脸序列）")
            text = AUCTION_SEQUENCE
            print(f"     ✓ 加载成功，共{len(text)}字符")
        
        # 多维度切片
        print("\n  执行多维度切片...")
        processor = SliceProcessorAgent()
        self.slices = processor.process_with_annotation(AUCTION_SEQUENCE, ANNOTATED_SLICES)
        
        total_slices = sum(len(s) for s in self.slices.values())
        print(f"     ✓ 切片完成，共{total_slices}个切片")
        
        # 存储切片
        print("\n  存储切片到双库...")
        stats = self.storage.store_slices(self.slices)
        print(f"     ✓ 存储完成，共{stats['total']}个切片")
        
        return True
    
    def analyze_with_llm(self):
        """使用LLM分析"""
        print("\n" + "="*80)
        print("  【步骤3：LLM智能分析】")
        print("="*80)
        
        if not self.llm:
            print("\n  ✗ LLM未初始化")
            return False
        
        # 分析任务1：分析爽点节奏
        print("\n  任务1：分析爽点节奏")
        print("  " + "-"*76)
        
        query1 = "分析这段网文片段的爽点节奏：主角被众人嘲讽，然后亮出宝物震惊全场"
        print(f"\n  查询: {query1}")
        
        response1 = self.llm.invoke(query1)
        print(f"\n  LLM分析结果:")
        print(f"  {response1.content[:400]}...")
        
        # 分析任务2：提取剧情序列
        print("\n\n  任务2：提取剧情序列")
        print("  " + "-"*76)
        
        query2 = "将以下剧情拆解为序列：主角进入拍卖会，被反派嘲讽，展示宝物，全场震惊，高价成交"
        print(f"\n  查询: {query2}")
        
        response2 = self.llm.invoke(query2)
        print(f"\n  LLM拆解结果:")
        print(f"  {response2.content[:400]}...")
        
        # 分析任务3：人物行为分析
        print("\n\n  任务3：人物行为分析")
        print("  " + "-"*76)
        
        query3 = "分析主角在拍卖会上的行为模式：沉默、淡定、突然展示实力"
        print(f"\n  查询: {query3}")
        
        response3 = self.llm.invoke(query3)
        print(f"\n  LLM分析结果:")
        print(f"  {response3.content[:400]}...")
        
        return True
    
    def simulate_expert_meeting(self):
        """模拟专家会议"""
        print("\n" + "="*80)
        print("  【步骤4：模拟L2专家会议】")
        print("="*80)
        
        print("\n  场景：讨论拍卖会打脸剧情")
        
        # 剧情架构师发言
        print("\n  【剧情架构师发言】")
        print("  " + "-"*76)
        
        architect_query = "拆解拍卖会打脸序列的功能结构"
        print(f"  发言内容: {architect_query}")
        
        # 检索专家响应
        meeting_context_1 = {
            "current_discussion": architect_query,
            "expert_role": "architect",
            "needs_retrieval": True,
            "scenario": "拍卖会打脸"
        }
        
        result_1 = self.retrieval_agent.listen_and_retrieve(meeting_context_1)
        print(f"\n  检索专家响应:")
        print(f"  - 检索意图: {result_1.request.intent.value}")
        print(f"  - 检索维度: {result_1.metadata.get('dimension')}")
        
        # LLM补充分析
        if self.llm:
            llm_response = self.llm.invoke(f"作为剧情架构师，{architect_query}")
            print(f"\n  LLM补充分析:")
            print(f"  {llm_response.content[:300]}...")
        
        # 网络编辑发言
        print("\n\n  【网络编辑发言】")
        print("  " + "-"*76)
        
        editor_query = "评估拍卖会打脸的爽点强度和节奏"
        print(f"  发言内容: {editor_query}")
        
        meeting_context_2 = {
            "current_discussion": editor_query,
            "expert_role": "editor",
            "needs_retrieval": True,
            "scenario": "拍卖会打脸"
        }
        
        result_2 = self.retrieval_agent.listen_and_retrieve(meeting_context_2)
        print(f"\n  检索专家响应:")
        print(f"  - 检索意图: {result_2.request.intent.value}")
        print(f"  - 检索维度: {result_2.metadata.get('dimension')}")
        
        # LLM补充分析
        if self.llm:
            llm_response = self.llm.invoke(f"作为网络编辑，{editor_query}")
            print(f"\n  LLM补充分析:")
            print(f"  {llm_response.content[:300]}...")
        
        # 人物设计师发言
        print("\n\n  【人物设计师发言】")
        print("  " + "-"*76)
        
        character_query = "分析主角在拍卖会中的行动元分配"
        print(f"  发言内容: {character_query}")
        
        meeting_context_3 = {
            "current_discussion": character_query,
            "expert_role": "character_designer",
            "needs_retrieval": True,
            "scenario": "拍卖会打脸"
        }
        
        result_3 = self.retrieval_agent.listen_and_retrieve(meeting_context_3)
        print(f"\n  检索专家响应:")
        print(f"  - 检索意图: {result_3.request.intent.value}")
        print(f"  - 检索维度: {result_3.metadata.get('dimension')}")
        
        # LLM补充分析
        if self.llm:
            llm_response = self.llm.invoke(f"作为人物设计师，{character_query}")
            print(f"\n  LLM补充分析:")
            print(f"  {llm_response.content[:300]}...")
        
        return True
    
    def generate_report(self):
        """生成报告"""
        print("\n" + "="*80)
        print("  【步骤5：生成报告】")
        print("="*80)
        
        if not self.llm:
            print("\n  ✗ LLM未初始化")
            return False
        
        print("\n  综合分析报告生成中...")
        
        report_query = """
        基于以上分析，生成一份简短的网文创作分析报告，包括：
        1. 剧情结构评估
        2. 爽点节奏分析
        3. 人物设计建议
        4. 改进建议
        
        场景：拍卖会打脸
        """
        
        report = self.llm.invoke(report_query)
        
        print(f"\n  【分析报告】\n")
        print("  " + "-"*76)
        print(f"{report.content}")
        print("  " + "-"*76)
        
        return True
    
    def run(self, novel_path: str = None):
        """运行完整流程"""
        # 初始化
        if not self.initialize():
            print("\n  ✗ 初始化失败")
            return False
        
        # 处理小说
        if not self.process_novel(novel_path):
            print("\n  ✗ 处理小说失败")
            return False
        
        # LLM分析
        if not self.analyze_with_llm():
            print("\n  ✗ LLM分析失败")
            return False
        
        # 模拟专家会议
        if not self.simulate_expert_meeting():
            print("\n  ✗ 专家会议模拟失败")
            return False
        
        # 生成报告
        if not self.generate_report():
            print("\n  ✗ 报告生成失败")
            return False
        
        print("\n" + "="*80)
        print("  ✓ Agent驱动测试完成")
        print("="*80)
        
        return True


if __name__ == "__main__":
    # 使用示例数据测试
    agent = SimpleAgent()
    
    # 可以传入小说路径，或使用默认的示例数据
    # agent.run("/home/ssjk/talk/1627崛起南海.txt")
    
    agent.run()  # 使用示例数据