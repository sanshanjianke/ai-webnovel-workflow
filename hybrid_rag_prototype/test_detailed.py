"""
详细节点测试 - 验证每个节点的输出是否符合预期

测试小说: 1627崛起南海.txt (UTF-8编码)
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent))

from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from utils import create_llm
from text_processor import SliceProcessorAgent, SliceUnit
from dual_storage import DualStorageManager
from retrieval_agent import L2RetrievalAgent, RetrievalIntent, RetrievalRequest


class NodeTester:
    """节点测试器"""
    
    def __init__(self):
        self.results = {}
        self.novel_path = Path("/home/ssjk/talk/1627崛起南海.txt")
        
    def print_header(self, title: str):
        """打印标题"""
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    
    def print_subheader(self, title: str):
        """打印子标题"""
        print(f"\n{'─'*80}")
        print(f"  {title}")
        print(f"{'─'*80}\n")
    
    def print_check(self, desc: str, passed: bool):
        """打印检查结果"""
        status = "✓" if passed else "✗"
        print(f"  {status} {desc}")
    
    def print_output(self, label: str, content: str, max_len: int = 200):
        """打印输出内容"""
        print(f"\n  【{label}】")
        if len(content) > max_len:
            print(f"  {content[:max_len]}...")
        else:
            print(f"  {content}")
    
    def test_node_1_novel_loading(self) -> Dict[str, Any]:
        """节点1：小说加载测试"""
        self.print_header("节点1：小说加载测试")
        
        print("【预期输出】")
        print("  1. 成功读取UTF-8编码的小说文件")
        print("  2. 返回文本内容（前10000字用于测试）")
        print("  3. 文本包含小说标题、作者等信息")
        
        print("\n【实际执行】")
        
        result = {
            "success": False,
            "text": None,
            "total_chars": 0,
            "checks": []
        }
        
        try:
            # 读取小说
            print("\n  步骤1：读取小说文件...")
            with open(self.novel_path, 'r', encoding='utf-8') as f:
                full_text = f.read(10000)  # 读取前10000字用于测试
            
            result["text"] = full_text
            result["total_chars"] = len(full_text)
            
            print(f"  ✓ 读取成功")
            print(f"  ✓ 读取字符数: {result['total_chars']}")
            
            # 检查1：文本不为空
            check1 = len(full_text) > 0
            result["checks"].append(("文本不为空", check1))
            self.print_check("文本不为空", check1)
            
            # 检查2：包含小说标题
            check2 = "1627崛起南海" in full_text
            result["checks"].append(("包含小说标题", check2))
            self.print_check("包含小说标题", check2)
            
            # 检查3：包含作者信息
            check3 = "作者" in full_text
            result["checks"].append(("包含作者信息", check3))
            self.print_check("包含作者信息", check3)
            
            # 检查4：编码正确（无乱码字符）
            # 检查是否有替换字符（表示解码错误）
            has_replacement_char = '\ufffd' in full_text
            check4 = not has_replacement_char
            result["checks"].append(("编码正确无乱码", check4))
            self.print_check("编码正确无乱码", check4)
            
            # 打印文本预览
            self.print_output("文本预览（前300字）", full_text[:300], 300)
            
            result["success"] = all(c[1] for c in result["checks"])
            
        except Exception as e:
            print(f"  ✗ 读取失败: {e}")
            result["checks"].append(("文件读取", False))
        
        print(f"\n【测试结果】")
        if result["success"]:
            print("  ✓ 节点1通过：小说加载正常")
        else:
            print("  ✗ 节点1失败：小说加载异常")
        
        self.results["node_1"] = result
        return result
    
    def test_node_2_llm_connection(self) -> Dict[str, Any]:
        """节点2：LLM连接测试"""
        self.print_header("节点2：LLM连接测试")
        
        print("【预期输出】")
        print("  1. 成功创建LLM对象")
        print("  2. LLM能正常响应")
        print("  3. 响应内容合理")
        
        print("\n【实际执行】")
        
        result = {
            "success": False,
            "llm": None,
            "response": None,
            "checks": []
        }
        
        try:
            # 创建LLM
            print("\n  步骤1：创建LLM对象...")
            llm = create_llm()
            
            if not llm:
                print("  ✗ LLM创建失败")
                result["checks"].append(("LLM创建", False))
            else:
                print("  ✓ LLM创建成功")
                result["llm"] = llm
                result["checks"].append(("LLM创建", True))
                self.print_check("LLM创建成功", True)
                
                # 测试响应
                print("\n  步骤2：测试LLM响应...")
                test_query = "请用一句话回答：1+1等于几？"
                response = llm.invoke(test_query)
                
                result["response"] = response.content
                
                print(f"  ✓ LLM响应成功")
                
                # 检查响应内容
                check2 = len(response.content) > 0
                result["checks"].append(("LLM响应非空", check2))
                self.print_check("LLM响应非空", check2)
                
                # 检查响应合理性（包含数字）
                check3 = any(char.isdigit() for char in response.content)
                result["checks"].append(("响应内容合理", check3))
                self.print_check("响应内容合理", check3)
                
                # 打印响应
                self.print_output("LLM响应", response.content, 150)
                
                result["success"] = all(c[1] for c in result["checks"])
        
        except Exception as e:
            print(f"  ✗ LLM测试失败: {e}")
            result["checks"].append(("LLM测试", False))
        
        print(f"\n【测试结果】")
        if result["success"]:
            print("  ✓ 节点2通过：LLM连接正常")
        else:
            print("  ✗ 节点2失败：LLM连接异常")
        
        self.results["node_2"] = result
        return result
    
    def test_node_3_slicing(self, test_text: str) -> Dict[str, Any]:
        """节点3：多维度切片测试"""
        self.print_header("节点3：多维度切片测试")
        
        print("【预期输出】")
        print("  1. 生成4个维度的切片")
        print("  2. 每个切片包含完整属性")
        print("  3. 切片标签正确")
        
        print("\n【实际执行】")
        
        result = {
            "success": False,
            "slices": {},
            "total_slices": 0,
            "checks": []
        }
        
        try:
            # 使用示例数据（小说文本需要预标注）
            print("\n  使用示例数据测试（拍卖会打脸序列）")
            from sample_data import AUCTION_SEQUENCE, ANNOTATED_SLICES
            
            # 切片处理
            print("\n  步骤1：创建切片处理器...")
            processor = SliceProcessorAgent()
            print("  ✓ 切片处理器创建成功")
            
            print("\n  步骤2：执行多维度切片...")
            slices = processor.process_with_annotation(AUCTION_SEQUENCE, ANNOTATED_SLICES)
            result["slices"] = slices
            
            # 统计切片
            for dim, slice_list in slices.items():
                result["total_slices"] += len(slice_list)
            
            print(f"  ✓ 切片完成，共{result['total_slices']}个切片")
            
            # 检查1：四个维度都有切片
            check1 = len(slices) == 4
            result["checks"].append(("四个维度都有切片", check1))
            self.print_check("四个维度都有切片", check1)
            
            # 检查2：每个切片都有ID
            check2 = all(
                all(s.metadata.unit_id for s in slice_list)
                for slice_list in slices.values()
            )
            result["checks"].append(("每个切片都有ID", check2))
            self.print_check("每个切片都有ID", check2)
            
            # 检查3：每个切片都有名称
            check3 = all(
                all(s.metadata.name for s in slice_list)
                for slice_list in slices.values()
            )
            result["checks"].append(("每个切片都有名称", check3))
            self.print_check("每个切片都有名称", check3)
            
            # 检查4：每个切片都有完整文本
            check4 = all(
                all(s.full_text for s in slice_list)
                for slice_list in slices.values()
            )
            result["checks"].append(("每个切片都有完整文本", check4))
            self.print_check("每个切片都有完整文本", check4)
            
            # 打印切片详情
            print("\n  【切片详情】")
            for dim, slice_list in slices.items():
                print(f"\n  ◆ {dim}维度: {len(slice_list)}个切片")
                for s in slice_list[:2]:  # 只显示前2个
                    print(f"    - {s.metadata.name}")
                    print(f"      ID: {s.metadata.unit_id}")
                    print(f"      字数: {len(s.full_text)}")
                    tags_preview = list(s.metadata.tags.keys())[:3]
                    print(f"      标签字段: {tags_preview}")
            
            result["success"] = all(c[1] for c in result["checks"])
            
        except Exception as e:
            print(f"  ✗ 切片测试失败: {e}")
            result["checks"].append(("切片处理", False))
        
        print(f"\n【测试结果】")
        if result["success"]:
            print("  ✓ 节点3通过：多维度切片正常")
        else:
            print("  ✗ 节点3失败：多维度切片异常")
        
        self.results["node_3"] = result
        return result
    
    def test_node_4_storage(self, slices: Dict) -> Dict[str, Any]:
        """节点4：双库存储测试"""
        self.print_header("节点4：双库存储测试")
        
        print("【预期输出】")
        print("  1. 成功存储所有切片")
        print("  2. MD文件正确生成")
        print("  3. 文件内容完整")
        
        print("\n【实际执行】")
        
        result = {
            "success": False,
            "storage": None,
            "md_files": [],
            "checks": []
        }
        
        try:
            # 创建存储管理器
            print("\n  步骤1：创建存储管理器...")
            storage = DualStorageManager(embedding=None, use_local_storage=True)
            print("  ✓ 存储管理器创建成功")
            result["storage"] = storage
            
            # 存储切片
            print("\n  步骤2：存储多维度切片...")
            stats = storage.store_slices(slices)
            print(f"  ✓ 存储完成，共{stats['total']}个切片")
            
            # 检查MD文件
            print("\n  步骤3：检查MD文本库...")
            from dual_storage import TextDBManager
            text_db = TextDBManager()
            md_files = text_db.list_documents()
            result["md_files"] = md_files
            
            print(f"  ✓ MD文件数: {len(md_files)}")
            
            # 检查1：所有维度都已存储
            check1 = len(stats['by_dimension']) == 4
            result["checks"].append(("所有维度都已存储", check1))
            self.print_check("所有维度都已存储", check1)
            
            # 检查2：MD文件数量正确
            check2 = len(md_files) == stats['total']
            result["checks"].append(("MD文件数量正确", check2))
            self.print_check("MD文件数量正确", check2)
            
            # 检查3：MD文件有内容
            check3 = all(
                Path(doc['path']).stat().st_size > 0
                for doc in md_files[:5]  # 检查前5个
            )
            result["checks"].append(("MD文件有内容", check3))
            self.print_check("MD文件有内容", check3)
            
            # 打印MD文件列表
            print("\n  【MD文件列表】")
            for doc in md_files[:10]:
                file_size = Path(doc['path']).stat().st_size
                print(f"    - {doc['dimension']}/{doc['unit_id']}.md ({file_size}字节)")
            
            # 读取一个文件验证
            if md_files:
                print(f"\n  步骤4：验证MD文件内容...")
                test_file = Path(md_files[0]['path'])
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                self.print_output("MD文件内容预览", content, 300)
                
                check4 = len(content) > 100
                result["checks"].append(("MD文件内容完整", check4))
                self.print_check("MD文件内容完整", check4)
            
            result["success"] = all(c[1] for c in result["checks"])
            
        except Exception as e:
            print(f"  ✗ 存储测试失败: {e}")
            result["checks"].append(("存储处理", False))
        
        print(f"\n【测试结果】")
        if result["success"]:
            print("  ✓ 节点4通过：双库存储正常")
        else:
            print("  ✗ 节点4失败：双库存储异常")
        
        self.results["node_4"] = result
        return result
    
    def test_node_5_retrieval(self, storage) -> Dict[str, Any]:
        """节点5：Agent检索专家测试"""
        self.print_header("节点5：Agent检索专家测试")
        
        print("【预期输出】")
        print("  1. 检索专家能识别意图")
        print("  2. 能根据专家角色选择维度")
        print("  3. 监听功能正常")
        
        print("\n【实际执行】")
        
        result = {
            "success": False,
            "agent": None,
            "checks": []
        }
        
        try:
            # 创建检索专家
            print("\n  步骤1：创建L2检索专家...")
            agent = L2RetrievalAgent(storage_manager=storage, llm=None)
            print(f"  ✓ 检索专家创建成功: {agent.name}")
            result["agent"] = agent
            
            # 测试意图识别
            print("\n  步骤2：测试意图识别...")
            test_queries = [
                ("查询拍卖会的剧情结构", "plot_search"),
                ("分析主角的行为模式", "character_analysis"),
                ("评估爽点节奏", "emotion_evaluation"),
            ]
            
            intent_correct = 0
            for query, expected_intent in test_queries:
                intent = agent.analyze_intent(query, {})
                is_correct = intent.value == expected_intent
                if is_correct:
                    intent_correct += 1
                print(f"    查询: {query}")
                print(f"    识别: {intent.value} {'✓' if is_correct else '✗'}")
            
            check1 = intent_correct == len(test_queries)
            result["checks"].append(("意图识别正确", check1))
            self.print_check("意图识别正确", check1)
            
            # 测试维度选择
            print("\n  步骤3：测试维度选择...")
            dimension_tests = [
                ("architect", "plot"),
                ("editor", "emotion"),
                ("character_designer", "character"),
            ]
            
            dimension_correct = 0
            for expert_role, expected_dim in dimension_tests:
                dimension = agent.determine_dimension_from_expert(expert_role)
                is_correct = dimension == expected_dim
                if is_correct:
                    dimension_correct += 1
                print(f"    专家: {expert_role} → 维度: {dimension} {'✓' if is_correct else '✗'}")
            
            check2 = dimension_correct == len(dimension_tests)
            result["checks"].append(("维度选择正确", check2))
            self.print_check("维度选择正确", check2)
            
            # 测试监听功能
            print("\n  步骤4：测试监听功能...")
            meeting_context = {
                "current_discussion": "评估拍卖会的爽点节奏",
                "expert_role": "editor",
                "needs_retrieval": True
            }
            
            retrieval_result = agent.listen_and_retrieve(meeting_context)
            
            check3 = retrieval_result is not None
            result["checks"].append(("监听功能正常", check3))
            self.print_check("监听功能正常", check3)
            
            if retrieval_result:
                print(f"    检索意图: {retrieval_result.request.intent.value}")
                print(f"    检索维度: {retrieval_result.metadata.get('dimension')}")
            
            result["success"] = all(c[1] for c in result["checks"])
            
        except Exception as e:
            print(f"  ✗ 检索专家测试失败: {e}")
            result["checks"].append(("检索专家处理", False))
        
        print(f"\n【测试结果】")
        if result["success"]:
            print("  ✓ 节点5通过：Agent检索专家正常")
        else:
            print("  ✗ 节点5失败：Agent检索专家异常")
        
        self.results["node_5"] = result
        return result
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*80)
        print("  详细节点测试 - 验证每个节点的输出")
        print("  测试小说: 1627崛起南海.txt (UTF-8)")
        print("="*80)
        
        # 节点1：小说加载
        node1_result = self.test_node_1_novel_loading()
        
        # 节点2：LLM连接
        node2_result = self.test_node_2_llm_connection()
        
        # 节点3：多维度切片
        node3_result = self.test_node_3_slicing(node1_result.get("text", ""))
        
        # 节点4：双库存储
        node4_result = self.test_node_4_storage(node3_result.get("slices", {}))
        
        # 节点5：Agent检索专家
        node5_result = self.test_node_5_retrieval(node4_result.get("storage"))
        
        # 打印总结
        self.print_summary()
    
    def print_summary(self):
        """打印测试总结"""
        self.print_header("测试总结")
        
        print("【各节点测试结果】\n")
        
        node_names = {
            "node_1": "小说加载测试",
            "node_2": "LLM连接测试",
            "node_3": "多维度切片测试",
            "node_4": "双库存储测试",
            "node_5": "Agent检索专家测试",
        }
        
        passed_count = 0
        for node, result in self.results.items():
            status = "✓ 通过" if result.get("success") else "✗ 失败"
            print(f"  {node_names.get(node, node)}: {status}")
            if result.get("success"):
                passed_count += 1
        
        print(f"\n【总体评估】")
        print(f"  通过节点: {passed_count}/{len(self.results)}")
        
        if passed_count == len(self.results):
            print("\n  ✓ 所有节点测试通过！")
        elif passed_count >= 3:
            print("\n  ⚠ 大部分节点测试通过")
        else:
            print("\n  ✗ 多个节点测试失败")


if __name__ == "__main__":
    tester = NodeTester()
    tester.run_all_tests()