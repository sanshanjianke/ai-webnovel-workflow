"""
简化测试 - 小说转大纲驱动

只测试核心流程，使用小说的前2000字
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils import create_llm


def test_basic():
    """测试基本信息提取"""
    print("\n" + "="*60)
    print("  测试小说转大纲 - 基本信息提取")
    print("="*60)
    
    # 初始化LLM
    print("\n1. 初始化LLM...")
    llm = create_llm()
    
    if not llm:
        print("✗ LLM未初始化")
        return
    
    print("✓ LLM已初始化")
    
    # 读取小说片段
    print("\n2. 读取小说片段...")
    novel_path = Path("/home/ssjk/talk/1627崛起南海.txt")
    
    try:
        with open(novel_path, 'r', encoding='utf-8') as f:
            text = f.read(2000)
        print(f"✓ 读取成功: {len(text)}字符")
    except:
        print("✗ 读取失败")
        return
    
    # 测试LLM响应
    print("\n3. 测试LLM分析...")
    
    prompt = f"""分析以下小说片段，提取基本信息：

{text[:500]}

请简短回答：
1. 小说名
2. 作者
3. 类型
4. 主角名
"""
    
    try:
        response = llm.invoke(prompt)
        print(f"✓ LLM响应成功")
        print(f"\n响应内容:\n{response.content}")
    except Exception as e:
        print(f"✗ LLM调用失败: {e}")
        return
    
    print("\n" + "="*60)
    print("  测试完成")
    print("="*60)


def test_sequence_extraction():
    """测试序列提取"""
    print("\n" + "="*60)
    print("  测试序列提取")
    print("="*60)
    
    llm = create_llm()
    if not llm:
        print("✗ LLM未初始化")
        return
    
    # 模拟一段剧情
    test_text = """
主角林尘身着旧衣，低调走入黑市拍卖行VIP室。
"这位客人，VIP室需要出示邀请函。"接待员的声音带着傲慢。
林尘没有说话，只是从怀中取出一枚暗淡的晶核，放在桌上。
赵少看到后大笑起来："这种低级晶核？我们这里不收。"
众人哄笑。
突然，鉴定师王老走了进来，接过晶核一看，瞳孔骤然收缩。
晶核爆发出淡蓝色光芒，全场窒息。
"这是修真界的晶核？！"王老激动得浑身颤抖。
拍卖行负责人冲进来："客人请留步！我们愿意收！"
"""
    
    prompt = f"""分析以下剧情片段，提取序列信息：

{test_text}

请识别：
1. 序列名称
2. 功能链（如：被嘲讽→被轻视→展示实力→全场震惊）
3. 情绪曲线（如：压抑→爆发→余韵）
4. 爽点类型
"""
    
    print("\n测试剧情:")
    print(test_text[:100] + "...")
    
    print("\nLLM分析中...")
    try:
        response = llm.invoke(prompt)
        print(f"✓ 分析成功\n")
        print(response.content)
    except Exception as e:
        print(f"✗ 分析失败: {e}")


def test_outline_generation():
    """测试大纲生成"""
    print("\n" + "="*60)
    print("  测试大纲生成")
    print("="*60)
    
    llm = create_llm()
    if not llm:
        print("✗ LLM未初始化")
        return
    
    # 读取小说前5000字
    novel_path = Path("/home/ssjk/talk/1627崛起南海.txt")
    try:
        with open(novel_path, 'r', encoding='utf-8') as f:
            text = f.read(5000)
        print(f"✓ 读取小说: {len(text)}字符")
    except:
        print("✗ 读取失败")
        return
    
    prompt = f"""基于以下小说片段，生成一个简短的L2层大纲：

{text}

请以JSON格式返回：
{{
  "novel_name": "小说名",
  "author": "作者",
  "genre": "类型",
  "protagonist": "主角",
  "golden_finger": "金手指",
  "core_appeal": "核心爽点",
  "chapters": [
    {{
      "title": "第1章",
      "summary": "章节概要（30字）",
      "sequences": [
        {{
          "name": "序列1",
          "functions": ["功能1", "功能2"],
          "emotion_curve": "压抑→爆发"
        }}
      ]
    }}
  ]
}}

注意：
- 章节数最多3个
- 每章最多2个序列
- 概要控制在30字以内
"""
    
    print("\n生成大纲中...")
    try:
        response = llm.invoke(prompt)
        print(f"✓ 大纲生成成功\n")
        print(response.content[:500])
        
        # 尝试解析JSON
        import json
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        outline = json.loads(content.strip())
        
        print("\n" + "="*60)
        print("  大纲解析成功")
        print("="*60)
        print(f"\n小说名: {outline.get('novel_name')}")
        print(f"作者: {outline.get('author')}")
        print(f"类型: {outline.get('genre')}")
        print(f"主角: {outline.get('protagonist')}")
        print(f"金手指: {outline.get('golden_finger')}")
        print(f"核心爽点: {outline.get('core_appeal')}")
        
        if 'chapters' in outline:
            print(f"\n章节数: {len(outline['chapters'])}")
            for i, chapter in enumerate(outline['chapters'][:3], 1):
                print(f"\n  第{i}章: {chapter.get('title')}")
                print(f"  概要: {chapter.get('summary')}")
                if 'sequences' in chapter:
                    print(f"  序列数: {len(chapter['sequences'])}")
        
        return outline
        
    except Exception as e:
        print(f"✗ 生成失败: {e}")
        return None


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  小说转大纲驱动 - 简化测试")
    print("="*60)
    
    # 测试1：基本信息
    test_basic()
    
    # 测试2：序列提取
    test_sequence_extraction()
    
    # 测试3：大纲生成
    outline = test_outline_generation()
    
    print("\n" + "="*60)
    print("  测试完成")
    print("="*60)