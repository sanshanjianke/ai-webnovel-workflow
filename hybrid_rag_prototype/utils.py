"""
工具函数 - 创建LLM和Embedding对象

支持OpenAI兼容API（如阿里云DashScope）
"""

import os
from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, EMBEDDING_MODEL

# 尝试导入LangChain
try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None
    OpenAIEmbeddings = None


def create_llm(model: str = None, temperature: float = 0.7, request_timeout: int = 120, **kwargs):
    """
    创建LLM对象
    
    Args:
        model: 模型名称（默认使用config中的LLM_MODEL）
        temperature: 温度参数
        request_timeout: 请求超时时间（秒），默认120秒
        **kwargs: 其他参数
        
    Returns:
        LangChain LLM对象
    """
    if not LANGCHAIN_AVAILABLE:
        print("警告: langchain_openai未安装，无法创建LLM")
        return None
    
    if not OPENAI_API_KEY:
        print("警告: 未配置OPENAI_API_KEY，无法创建LLM")
        return None
    
    model = model or LLM_MODEL
    
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_BASE_URL,
        request_timeout=request_timeout,
        **kwargs
    )
    
    return llm


def create_embeddings(model: str = None, **kwargs):
    """
    创建Embedding对象
    
    Args:
        model: 模型名称（默认使用config中的EMBEDDING_MODEL）
        **kwargs: 其他参数
        
    Returns:
        LangChain Embeddings对象
    """
    if not LANGCHAIN_AVAILABLE:
        print("警告: langchain_openai未安装，无法创建Embedding")
        return None
    
    if not OPENAI_API_KEY:
        print("警告: 未配置OPENAI_API_KEY，无法创建Embedding")
        return None
    
    model = model or EMBEDDING_MODEL
    
    embeddings = OpenAIEmbeddings(
        model=model,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_BASE_URL,
        **kwargs
    )
    
    return embeddings


def test_api_connection():
    """测试API连接"""
    print("=== 测试API连接 ===")
    print(f"Base URL: {OPENAI_BASE_URL}")
    print(f"API Key: {OPENAI_API_KEY[:20]}..." if OPENAI_API_KEY else "未配置")
    print(f"LLM Model: {LLM_MODEL}")
    print(f"Embedding Model: {EMBEDDING_MODEL}")
    
    if not LANGCHAIN_AVAILABLE:
        print("\n错误: langchain_openai未安装")
        print("请运行: pip install langchain-openai")
        return False
    
    if not OPENAI_API_KEY:
        print("\n错误: 未配置OPENAI_API_KEY")
        return False
    
    # 测试LLM
    print("\n测试LLM连接...")
    try:
        llm = create_llm()
        if llm:
            response = llm.invoke("你好，请回复'API连接成功'")
            print(f"LLM响应: {response.content}")
            print("✓ LLM连接成功")
        else:
            print("✗ LLM创建失败")
            return False
    except Exception as e:
        print(f"✗ LLM连接失败: {e}")
        return False
    
    # 测试Embedding
    print("\n测试Embedding连接...")
    try:
        embeddings = create_embeddings()
        if embeddings:
            test_text = "测试文本"
            embedding_vector = embeddings.embed_query(test_text)
            print(f"Embedding维度: {len(embedding_vector)}")
            print("✓ Embedding连接成功")
        else:
            print("✗ Embedding创建失败")
            return False
    except Exception as e:
        print(f"✗ Embedding连接失败: {e}")
        return False
    
    print("\n=== API连接测试通过 ===")
    return True


if __name__ == "__main__":
    test_api_connection()