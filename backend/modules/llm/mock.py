from typing import Iterator
from backend.core.protocols.llm import BaseLLMProvider
from backend.core.registry import register_module


@register_module("llm")
class MockLLM(BaseLLMProvider):
    def __init__(self, response: str = ""):
        self.response = response or self._default_response()

    def invoke(self, prompt: str, **kwargs) -> str:
        return self.response

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        words = self.response.split()
        for word in words:
            yield word + " "

    def _default_response(self) -> str:
        return """# 故事愿景文档

## 核心梗
主角穿越到修真世界，带着现代AI系统，用科技思维改变修真界。

## 阅读契约
- 目标读者：男频，18-35岁
- 核心爽点：装逼打脸、系统升级、科技碾压
- 风格基调：轻松热血

## 粗略大纲
1. 开篇：主角穿越，激活AI系统，发现自己身处修真宗门
2. 发展：利用AI分析功法，快速突破，引起注意
3. 高潮：宗门大比，主角以科技思维碾压传统修士
4. 结局：主角成为宗门核心弟子，开启新的征程

## 核心设定
- 世界观：修真世界，等级森严，强者为尊
- 主角人设：理工男，理性思维，不按常理出牌
- 金手指/核心道具：AI系统，可分析功法、预测对手招式

## 热点/潮流元素（如有）
- 热点：AI技术热潮
- 融合方式：将AI思维融入修真体系
- 时效性评估：长期有效，科技是永恒话题

## 预期字数
长篇，预计200万字
"""
