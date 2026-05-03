"""
独立测试：管道模式两节点执行，用 MockLLM 观察事件流。
用法: cd backend && python -m pytest tests/test_pipeline_debug.py -v -s
"""

import pytest
from backend.core.registry import discover_modules, MODULE_REGISTRY
from backend.core.config import get_config
from backend.core.protocols.meeting import (
    MeetingConfig, ExpertConfig, ContainerConfig, ExpertRole, Granularity
)
from backend.modules.orchestration import MeetingEngine
from backend.modules.llm.mock import MockLLM


@pytest.fixture(autouse=True)
def setup_mock_llm():
    """替换 LLM 为 Mock，避免真实 API 调用"""
    discover_modules()
    MODULE_REGISTRY["llm"]["mock"] = MockLLM
    config = get_config()
    config.llm.primary = "mock"
    yield
    config.llm.primary = "open_ai_compat"


def make_config(expert_ids: list[str], roles: list[str], edges: list[dict]) -> MeetingConfig:
    experts = []
    for i, (eid, role) in enumerate(zip(expert_ids, roles)):
        experts.append(ExpertConfig(
            expert_id=eid,
            role=ExpertRole(role),
            node_id=f"node_{i}",
        ))
    return MeetingConfig(
        meeting_name="管道测试",
        granularity=Granularity("chapter"),
        experts=experts,
        containers=[],
        edges=edges,
        collaboration_mode="semi_auto",
        max_rounds=3,
        max_speeches=0,
    )


def test_pipeline_two_nodes():
    """两节点 + 一条边：节点0 → 节点1。验证两个节点都会被调用。"""
    config = make_config(
        expert_ids=["plot_architect_v1", "web_editor_v1"],
        roles=["main", "review"],
        edges=[{"source": "node_0", "target": "node_1"}],
    )

    engine = MeetingEngine(config)
    context = {"core_idea": "测试用故事", "rough_outline": "1→2→3→4"}

    events = list(engine.run_pipeline(context, "worldbook text", "rag text"))

    print("\n=== 管道事件流 ===")
    for ev in events:
        ptype = ev.get("type", "?")
        if ptype == "pipeline_start":
            print(f"  PIPELINE_START  levels={ev.get('levels')}  nodes={ev.get('nodes')}")
        elif ptype == "level_start":
            print(f"  LEVEL_START  level={ev.get('level')}/{ev.get('total_levels')}  nodes={ev.get('nodes')}")
        elif ptype == "level_complete":
            print(f"  LEVEL_COMPLETE  level={ev.get('level')}")
        elif ptype == "expert_start":
            print(f"  EXPERT_START  expert={ev.get('expert_type')}  level={ev.get('level')}")
        elif ptype == "expert_speak":
            content = ev.get("content", "")
            print(f"  EXPERT_SPEAK  expert={ev.get('expert_type')}  len={len(content)}  preview={content[:80]}...")
        elif ptype == "pipeline_complete":
            output = ev["output"]
            print(f"  PIPELINE_COMPLETE  speeches={output.get('total_speeches')}  nodes_with_output={list(output['node_outputs'].keys())}")
        elif ptype == "node_skip":
            print(f"  NODE_SKIP  node={ev.get('node_id')}  reason={ev.get('reason')}")
        else:
            print(f"  {ptype}  {ev}")

    event_types = [e["type"] for e in events]

    # 断言关键事件都存在
    assert "pipeline_start" in event_types
    assert "pipeline_complete" in event_types

    # 两个 expert_start + 两个 expert_speak
    assert event_types.count("expert_start") == 2
    assert event_types.count("expert_speak") == 2

    # 应该有两层
    assert event_types.count("level_start") == 2
    assert event_types.count("level_complete") == 2

    # pipeline_complete 的 output 应该包含两个节点的输出
    final = events[-1]
    assert final["type"] == "pipeline_complete"
    assert "node_0" in final["output"]["node_outputs"]
    assert "node_1" in final["output"]["node_outputs"]
    assert final["output"]["total_speeches"] == 2


def test_pipeline_no_edges():
    """无连线：两个节点各自独立（同一层），都会被执行。"""
    config = make_config(
        expert_ids=["plot_architect_v1", "web_editor_v1"],
        roles=["main", "review"],
        edges=[],
    )

    engine = MeetingEngine(config)
    context = {"core_idea": "测试"}
    events = list(engine.run_pipeline(context))

    event_types = [e["type"] for e in events]
    print("\n=== 无连线管道 ===")
    for ev in events:
        print(f"  {ev.get('type')}")

    assert "pipeline_start" in event_types
    assert "pipeline_complete" in event_types
    assert event_types.count("expert_start") == 2
    assert event_types.count("expert_speak") == 2


def test_pipeline_single_node():
    """单节点：最简单场景。"""
    config = make_config(
        expert_ids=["plot_architect_v1"],
        roles=["main"],
        edges=[],
    )

    engine = MeetingEngine(config)
    context = {"core_idea": "测试"}
    events = list(engine.run_pipeline(context))

    event_types = [e["type"] for e in events]
    print("\n=== 单节点管道 ===")
    for ev in events:
        print(f"  {ev.get('type')}")

    assert "pipeline_start" in event_types
    assert "pipeline_complete" in event_types
    assert event_types.count("expert_start") == 1
    assert event_types.count("expert_speak") == 1


def test_pipeline_three_nodes_chain():
    """三节点链：node_0 → node_1 → node_2。验证三层都执行。"""
    config = make_config(
        expert_ids=["plot_architect_v1", "web_editor_v1", "character_designer_v1"],
        roles=["main", "review", "supplement"],
        edges=[
            {"source": "node_0", "target": "node_1"},
            {"source": "node_1", "target": "node_2"},
        ],
    )

    engine = MeetingEngine(config)
    context = {"core_idea": "测试链"}
    events = list(engine.run_pipeline(context))

    event_types = [e["type"] for e in events]
    print("\n=== 三节点链 ===")
    for ev in events:
        ptype = ev.get("type")
        if ptype in ("level_start", "level_complete"):
            print(f"  {ptype}  level={ev.get('level')}")
        elif ptype == "pipeline_complete":
            print(f"  {ptype}  nodes={list(ev['output']['node_outputs'].keys())}")
        else:
            print(f"  {ptype}")

    assert "pipeline_start" in event_types
    assert "pipeline_complete" in event_types
    assert event_types.count("expert_start") == 3
    assert event_types.count("expert_speak") == 3
    assert event_types.count("level_start") == 3


def test_pipeline_exception_handling():
    """验证 pipeline 在 exception 时不会静默崩溃"""
    config = make_config(
        expert_ids=["nonexistent_expert", "web_editor_v1"],
        roles=["main", "review"],
        edges=[],
    )

    engine = MeetingEngine(config)
    context = {"core_idea": "测试"}

    try:
        events = list(engine.run_pipeline(context))
        print("\n=== 异常测试 ===")
        for ev in events:
            print(f"  {ev.get('type')}")
    except ValueError as e:
        print(f"\n=== 预期异常: {e} ===")
