"""
Agent检索专家 - 笔记6核心实现

负责：
1. 理解当前专家会议的讨论语境
2. 判断需要检索的维度
3. 调用向量数据库获取标签/摘要
4. 根据指针获取完整文本
5. 智能加工处理后返回给专家会议

设计思路：
- 为L2/L3/L4各层设计专门的检索专家
- 检索专家监听专家会议，根据讨论内容主动检索
- 智能加工：压缩、重组、摘要、推理
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# 尝试导入LangChain，失败则使用简化实现
try:
    from langchain_core.messages import HumanMessage, AIMessage
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from config import L2_EXPERTS, SLICE_DIMENSIONS
from dual_storage import DualStorageManager


class RetrievalIntent(Enum):
    """检索意图类型"""
    PLOT_SEARCH = "plot_search"  # 剧情查询
    CHARACTER_ANALYSIS = "character_analysis"  # 人物分析
    EMOTION_EVALUATION = "emotion_evaluation"  # 爽点评估
    FUNCTION_MAPPING = "function_mapping"  # 功能映射
    TECHNIQUE_REFERENCE = "technique_reference"  # 技法参考


@dataclass
class RetrievalRequest:
    """检索请求"""
    query: str  # 查询内容
    intent: RetrievalIntent  # 检索意图
    dimension: Optional[str] = None  # 指定维度
    expert_role: Optional[str] = None  # 发起检索的专家角色
    context: Dict = field(default_factory=dict)  # 上下文信息


@dataclass
class RetrievalResult:
    """检索结果"""
    request: RetrievalRequest
    documents: List[Any]  # 检索到的文档
    processed_content: str  # 智能加工后的内容
    metadata: Dict = field(default_factory=dict)  # 元数据


class BaseRetrievalAgent:
    """检索专家基类"""
    
    def __init__(self, storage_manager: DualStorageManager, llm=None):
        """
        Args:
            storage_manager: 双库存储管理器
            llm: LangChain LLM对象（用于智能加工）
        """
        self.storage = storage_manager
        self.llm = llm
    
    def analyze_intent(self, query: str, context: Dict) -> RetrievalIntent:
        """
        分析检索意图
        
        根据查询内容和上下文判断需要检索什么类型的信息
        """
        # 简化规则：根据关键词判断
        if any(kw in query for kw in ["剧情", "序列", "情节", "事件", "序列"]):
            return RetrievalIntent.PLOT_SEARCH
        elif any(kw in query for kw in ["人物", "角色", "行为", "人设", "主角", "反派"]):
            return RetrievalIntent.CHARACTER_ANALYSIS
        elif any(kw in query for kw in ["爽点", "节奏", "压抑", "爆发", "余韵", "情绪"]):
            return RetrievalIntent.EMOTION_EVALUATION
        elif any(kw in query for kw in ["功能", "铺垫", "转折", "反馈"]):
            return RetrievalIntent.FUNCTION_MAPPING
        else:
            return RetrievalIntent.PLOT_SEARCH
    
    def determine_dimension(self, intent: RetrievalIntent, expert_role: Optional[str] = None) -> str:
        """
        确定检索维度
        
        根据检索意图和专家角色选择最合适的维度
        """
        # 专家偏好维度
        if expert_role:
            expert_info = L2_EXPERTS.get(expert_role)
            if expert_info:
                return expert_info.get("preferred_dimension", "plot")
        
        # 意图对应维度
        intent_dimension_map = {
            RetrievalIntent.PLOT_SEARCH: "plot",
            RetrievalIntent.CHARACTER_ANALYSIS: "character",
            RetrievalIntent.EMOTION_EVALUATION: "emotion",
            RetrievalIntent.FUNCTION_MAPPING: "function",
            RetrievalIntent.TECHNIQUE_REFERENCE: "function"
        }
        
        return intent_dimension_map.get(intent, "plot")
    
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """
        执行检索
        
        流程：
        1. 分析意图
        2. 确定维度
        3. 查询向量数据库
        4. 获取完整文本
        5. 智能加工
        """
        # 如果请求中没有指定意图，自动分析
        if not request.intent:
            request.intent = self.analyze_intent(request.query, request.context)
        
        # 如果请求中没有指定维度，自动确定
        if not request.dimension:
            request.dimension = self.determine_dimension(request.intent, request.expert_role)
        
        # 查询向量数据库（使用摘要）
        documents = self.storage.retrieve(
            query=request.query,
            dimension=request.dimension,
            k=3
        )
        
        # 智能加工
        processed_content = self.process_documents(documents, request)
        
        return RetrievalResult(
            request=request,
            documents=documents,
            processed_content=processed_content,
            metadata={"dimension": request.dimension}
        )
    
    def process_documents(self, documents: List[Any], request: RetrievalRequest) -> str:
        """
        智能加工文档
        
        根据检索意图，对文档进行不同的加工处理：
        - 剧情查询：返回完整剧情概述
        - 人物分析：提取人物行为模式
        - 爽点评估：分析情绪曲线
        - 功能映射：提炼叙事功能
        """
        if not documents:
            return "未找到相关内容。"
        
        # 如果没有LLM，使用简单处理
        if not self.llm:
            return self._simple_process(documents, request.intent)
        
        # 使用LLM智能加工
        return self._llm_process(documents, request)
    
    def _simple_process(self, documents: List[Any], intent: RetrievalIntent) -> str:
        """简单处理（无LLM）"""
        results = []
        
        for doc in documents[:3]:  # 只处理前3个
            content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            results.append(content[:200])  # 取前200字
        
        return "\n\n---\n\n".join(results)
    
    def _llm_process(self, documents: List[Any], request: RetrievalRequest) -> str:
        """LLM智能加工"""
        
        # 构建文档内容
        doc_contents = []
        for doc in documents:
            content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            doc_contents.append(content)
        
        combined_docs = "\n\n---\n\n".join(doc_contents)
        
        # 根据意图选择加工方式
        if request.intent == RetrievalIntent.EMOTION_EVALUATION:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个网文爽点分析专家。分析以下内容中的情绪曲线（压抑-爆发-余韵），评估爽感强度，指出节奏问题。"),
                ("human", "{documents}")
            ])
        elif request.intent == RetrievalIntent.CHARACTER_ANALYSIS:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个人物设计专家。分析以下内容中人物的行为模式、性格特点，评估是否符合人设。"),
                ("human", "{documents}")
            ])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个剧情分析专家。总结以下内容的剧情结构，提炼关键序列和功能。"),
                ("human", "{documents}")
            ])
        
        # 调用LLM
        chain = prompt | self.llm
        result = chain.invoke({"documents": combined_docs})
        
        return result.content


class L2RetrievalAgent(BaseRetrievalAgent):
    """L2专家会议检索专家"""
    
    def __init__(self, storage_manager: DualStorageManager, llm=None):
        super().__init__(storage_manager, llm)
        self.name = "知识库检索专家"
    
    def listen_and_retrieve(self, meeting_context: Dict) -> Optional[RetrievalResult]:
        """
        监听专家会议，判断是否需要检索
        
        Args:
            meeting_context: 专家会议上下文
                - current_discussion: 当前讨论内容
                - expert_role: 当前发言的专家角色
                - needs_retrieval: 是否需要检索（专家明确请求）
                
        Returns:
            检索结果（如果需要）
        """
        # 判断是否需要检索
        needs_retrieval = meeting_context.get("needs_retrieval", False)
        
        if not needs_retrieval:
            return None
        
        # 构建检索请求
        query = meeting_context.get("current_discussion", "")
        expert_role = meeting_context.get("expert_role")
        
        request = RetrievalRequest(
            query=query,
            intent=self.analyze_intent(query, meeting_context),
            dimension=self.determine_dimension_from_expert(expert_role),
            expert_role=expert_role,
            context=meeting_context
        )
        
        # 执行检索
        return self.retrieve(request)
    
    def determine_dimension_from_expert(self, expert_role: str) -> str:
        """根据专家角色确定检索维度"""
        dimension_map = {
            "architect": "plot",  # 剧情架构师 → 剧情维度
            "editor": "emotion",  # 网络编辑 → 爽点维度
            "character_designer": "character"  # 人物设计师 → 人物维度
        }
        return dimension_map.get(expert_role, "plot")
    
    def provide_contextual_info(self, expert_role: str, scenario: str) -> str:
        """
        主动提供上下文信息
        
        当专家会议讨论某个场景时，检索专家可以主动提供相关背景信息
        """
        # 根据专家角色和场景，构建检索请求
        request = RetrievalRequest(
            query=f"{scenario} {self._get_expert_focus(expert_role)}",
            intent=self._get_intent_from_expert(expert_role),
            dimension=self.determine_dimension_from_expert(expert_role),
            expert_role=expert_role,
            context={"scenario": scenario}
        )
        
        result = self.retrieve(request)
        return result.processed_content
    
    def _get_expert_focus(self, expert_role: str) -> str:
        """获取专家关注点"""
        focus_map = {
            "architect": "剧情结构 序列功能",
            "editor": "爽点节奏 情绪曲线",
            "character_designer": "人物行为 人设一致性"
        }
        return focus_map.get(expert_role, "")
    
    def _get_intent_from_expert(self, expert_role: str) -> RetrievalIntent:
        """根据专家角色获取检索意图"""
        intent_map = {
            "architect": RetrievalIntent.PLOT_SEARCH,
            "editor": RetrievalIntent.EMOTION_EVALUATION,
            "character_designer": RetrievalIntent.CHARACTER_ANALYSIS
        }
        return intent_map.get(expert_role, RetrievalIntent.PLOT_SEARCH)


class L3MappingAgent(BaseRetrievalAgent):
    """L3映射检索专家"""
    
    def __init__(self, storage_manager: DualStorageManager, llm=None):
        super().__init__(storage_manager, llm)
        self.name = "映射检索专家"
        self.dimension = "function"  # L3主要使用功能维度
    
    def retrieve_mapping_rules(self, effect_label: str) -> Dict:
        """
        检索映射规则
        
        将网文效果标签映射到叙事学技术指令
        
        Args:
            effect_label: 效果标签（如"装逼打脸"、"压抑"、"爆发"）
            
        Returns:
            映射规则字典
        """
        request = RetrievalRequest(
            query=effect_label,
            intent=RetrievalIntent.FUNCTION_MAPPING,
            dimension=self.dimension,
            context={"effect_label": effect_label}
        )
        
        result = self.retrieve(request)
        
        # 解析映射规则
        mapping_rules = self._parse_mapping_rules(result.processed_content)
        
        return mapping_rules
    
    def _parse_mapping_rules(self, content: str) -> Dict:
        """
        解析映射规则
        
        从检索结果中提取视角、节奏、话语模式等映射信息
        """
        # 简化处理：返回格式化的规则
        # 实际应用中需要更复杂的解析逻辑
        
        rules = {
            "effect": "装逼打脸",
            "mapping": {
                "压抑": {
                    "视角": "反派/路人内聚焦",
                    "节奏": "慢速扩述",
                    "话语模式": "对话+心理"
                },
                "爆发": {
                    "视角": "外聚焦",
                    "节奏": "中速等述",
                    "话语模式": "动作+环境"
                },
                "余韵": {
                    "视角": "自由间接引语",
                    "节奏": "快速概述",
                    "话语模式": "震惊反应"
                }
            },
            "source_content": content
        }
        
        return rules


class L4TechniqueAgent(BaseRetrievalAgent):
    """L4技法检索专家"""
    
    def __init__(self, storage_manager: DualStorageManager, llm=None):
        super().__init__(storage_manager, llm)
        self.name = "技法检索专家"
        self.dimension = "function"  # L4主要使用功能维度
    
    def retrieve_technique_examples(
        self,
        perspective: str,
        rhythm: str,
        discourse_mode: str
    ) -> List[Dict]:
        """
        检索技法示例
        
        根据叙事指令（视角、节奏、话语模式）检索参考文本
        
        Args:
            perspective: 视角类型
            rhythm: 节奏类型
            discourse_mode: 话语模式
            
        Returns:
            技法示例列表
        """
        query = f"{perspective} {rhythm} {discourse_mode}"
        
        request = RetrievalRequest(
            query=query,
            intent=RetrievalIntent.TECHNIQUE_REFERENCE,
            dimension=self.dimension,
            context={
                "perspective": perspective,
                "rhythm": rhythm,
                "discourse_mode": discourse_mode
            }
        )
        
        result = self.retrieve(request)
        
        # 提取技法示例
        examples = self._extract_technique_examples(result.documents)
        
        return examples
    
    def _extract_technique_examples(self, documents: List[Any]) -> List[Dict]:
        """提取技法示例"""
        examples = []
        
        for doc in documents:
            content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            
            examples.append({
                "text": content,
                "perspective": metadata.get("perspective", "unknown"),
                "rhythm": metadata.get("rhythm", "unknown"),
                "discourse_mode": metadata.get("discourse_mode", "unknown"),
                "source": metadata.get("source", "sample_data")
            })
        
        return examples
    
    def select_best_example(self, examples: List[Dict], style: str) -> Optional[Dict]:
        """
        选择最佳示例
        
        根据风格要求筛选最合适的参考文本
        
        Args:
            examples: 技法示例列表
            style: 风格要求（如"古龙风"、"海明威风"）
            
        Returns:
            最佳示例
        """
        # 如果有LLM，可以智能选择
        if self.llm and examples:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个写作风格专家。从以下技法示例中，选择最适合'{style}'风格的示例。"),
                ("human", "{examples}")
            ])
            
            chain = prompt | self.llm
            result = chain.invoke({
                "examples": str(examples),
                "style": style
            })
            
            # 简化处理：返回第一个示例
            return examples[0]
        
        # 无LLM：返回第一个示例
        return examples[0] if examples else None


if __name__ == "__main__":
    # 测试检索专家（无embedding和LLM）
    print("=== 测试检索专家（无embedding模式） ===")
    
    from sample_data import AUCTION_SEQUENCE, ANNOTATED_SLICES
    from text_processor import SliceProcessorAgent
    
    # 1. 切片和存储
    processor = SliceProcessorAgent()
    slices = processor.process_with_annotation(AUCTION_SEQUENCE, ANNOTATED_SLICES)
    
    storage = DualStorageManager(embedding=None)
    storage.store_slices(slices)
    
    # 2. 创建L2检索专家
    retrieval_agent = L2RetrievalAgent(storage_manager=storage, llm=None)
    
    # 3. 测试监听和检索
    meeting_context = {
        "current_discussion": "评估拍卖会打脸的爽点节奏",
        "expert_role": "editor",
        "needs_retrieval": True
    }
    
    result = retrieval_agent.listen_and_retrieve(meeting_context)
    
    if result:
        print(f"\n检索意图: {result.request.intent}")
        print(f"检索维度: {result.metadata.get('dimension')}")
        print(f"检索结果（加工后）:\n{result.processed_content[:300]}...")
    
    # 4. 测试主动提供上下文
    print("\n\n=== 主动提供上下文 ===")
    context_info = retrieval_agent.provide_contextual_info("architect", "拍卖会打脸")
    print(context_info[:300] + "...")