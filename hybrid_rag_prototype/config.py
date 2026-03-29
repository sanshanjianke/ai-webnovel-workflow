"""
配置文件 - 笔记6混合检索方案原型

核心设计：
- 双库分离：向量数据库（摘要+标签+指针） + MD文本库（完整切片）
- 多维度切片：剧情/人物/爽点/功能四个维度
- Agent检索专家：理解语境，智能加工检索结果
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 存储路径
VECTOR_DB_PATH = PROJECT_ROOT / "data" / "vector_db"
TEXT_DB_PATH = PROJECT_ROOT / "data" / "text_db"

# 确保目录存在
VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
TEXT_DB_PATH.mkdir(parents=True, exist_ok=True)

# 向量数据库配置
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI embedding模型
VECTOR_DB_TYPE = "chroma"  # 使用Chroma作为向量数据库

# 切片维度定义（笔记6核心概念）
SLICE_DIMENSIONS = {
    "plot": {
        "name": "剧情维度",
        "unit": "序列/事件",
        "boundary": "序列开始/结束",
        "description": "剧情架构师查询完整情节"
    },
    "character": {
        "name": "人物维度",
        "unit": "角色相关段落",
        "boundary": "人物出场/退场",
        "description": "人物设计师查询角色行为"
    },
    "emotion": {
        "name": "爽点维度",
        "unit": "情绪段落",
        "boundary": "情绪转折点",
        "description": "网络编辑评估爽点节奏"
    },
    "function": {
        "name": "功能维度",
        "unit": "叙事功能",
        "boundary": "功能边界",
        "description": "分析剧情结构"
    }
}

# L2专家角色定义
L2_EXPERTS = {
    "architect": {
        "name": "剧情架构师",
        "focus": "逻辑通顺、结构完整",
        "preferred_dimension": "plot"
    },
    "editor": {
        "name": "网络编辑",
        "focus": "爽点、节奏、读者留存",
        "preferred_dimension": "emotion"
    },
    "character_designer": {
        "name": "人物设计师",
        "focus": "人设一致、行为合理",
        "preferred_dimension": "character"
    }
}

# 情绪阶段定义（用于爽点维度切片）
EMOTION_PHASES = ["压抑", "爆发", "余韵"]

# 功能类型定义（用于功能维度切片）
FUNCTION_TYPES = ["铺垫", "转折", "反馈", "获得", "禁令", "违背", "斗争", "胜利"]

# OpenAI API配置
# 支持环境变量或直接配置
# 阿里云DashScope API（OpenAI兼容）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-sp-2fe4558782804e59a3353e2439b7b11c")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://coding.dashscope.aliyuncs.com/v1")

# 模型配置（智谱AI GLM-5）
# 智谱AI API支持GLM系列模型
LLM_MODEL = os.getenv("LLM_MODEL", "glm-5")  # 使用glm-5
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "embedding-3")  # 智谱embedding模型

# LangSmith追踪配置（可选）
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "hybrid_rag_prototype")

# 启用LLM功能（需要API配置）
ENABLE_LLM = True if OPENAI_API_KEY else False
ENABLE_EMBEDDING = True if OPENAI_API_KEY else False