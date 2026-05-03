"""
通过 FastAPI TestClient 模拟完整管道请求，观察 SSE 事件流。
用法: cd backend && ~/talk/venv/bin/python -m pytest tests/test_pipeline_api.py -v -s
"""

import pytest
import json
from backend.core.registry import discover_modules, MODULE_REGISTRY
from backend.core.config import get_config
from backend.modules.llm.mock import MockLLM
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_mock():
    discover_modules()
    MODULE_REGISTRY["llm"]["mock"] = MockLLM
    config = get_config()
    old_primary = config.llm.primary
    config.llm.primary = "mock"
    yield
    config.llm.primary = old_primary


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def project_with_vision(client):
    """创建项目 + L1 愿景"""
    from backend.core.config import get_config
    config = get_config()
    config.llm.primary = "mock"

    resp = client.post("/api/projects/", json={"name": "管道API测试"})
    assert resp.status_code == 200
    pid = resp.json()["id"]

    client.post(f"/api/projects/{pid}/l1/generate", json={
        "idea": "主角穿越修真世界带AI系统",
        "rough_outline": "1.穿越 2.修炼 3.打脸 4.登顶",
    })
    return pid


def parse_sse_events(response):
    """解析 SSE 响应为事件列表。兼容 event: + data: 和纯 data: 两种格式。"""
    events = []
    lines = response.text.split('\n')
    i = 0
    event_type = ''
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('event: '):
            event_type = line[7:]
        elif line.startswith('data: '):
            data_str = line[6:]
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = data_str
            if isinstance(data, dict):
                events.append((event_type or data.get('type', 'message'), data))
            else:
                events.append((event_type or 'message', data))
            event_type = ''
        elif not line:
            event_type = ''
        i += 1
    return events


def test_pipeline_sse_two_nodes(client, project_with_vision):
    """完整 API SSE 流：两节点管道。观察是否走完两节点。"""
    pid = project_with_vision

    payload = {
        "meeting_name": "管道测试",
        "pipeline": True,
        "experts": [
            {"expert_id": "plot_architect_v1", "node_id": "node_0", "role": "main"},
            {"expert_id": "web_editor_v1", "node_id": "node_1", "role": "review"},
        ],
        "containers": [],
        "edges": [
            {"source": "node_0", "target": "node_1"},
        ],
    }

    response = client.post(
        f"/api/projects/{pid}/meeting/start",
        json=payload,
        headers={"Accept": "text/event-stream"},
    )

    assert response.status_code == 200
    events = parse_sse_events(response)

    print("\n=== SSE 事件流 ===")
    for evt, data in events:
        if isinstance(data, dict):
            ptype = data.get("type", evt)
            if ptype in ("pipeline_start",):
                print(f"  [{evt}] {ptype}  levels={data.get('levels')} nodes={data.get('nodes')}")
            elif ptype in ("level_start", "level_complete"):
                print(f"  [{evt}] {ptype}  level={data.get('level')}")
            elif ptype == "expert_start":
                print(f"  [{evt}] {ptype}  expert={data.get('expert_type')}  level={data.get('level')}")
            elif ptype == "expert_speak":
                content = data.get("content", "")
                print(f"  [{evt}] {ptype}  expert={data.get('expert_type')}  len={len(content)}")
            elif ptype == "pipeline_complete":
                output = data.get("output", {})
                print(f"  [{evt}] {ptype}  speeches={output.get('total_speeches')}  nodes={list(output.get('node_outputs', {}).keys())}")
            elif ptype == "done":
                print(f"  [{evt}] done")
            else:
                print(f"  [{evt}] {ptype}")
        else:
            print(f"  [{evt}] raw={str(data)[:80]}")

    # 检查是否 pipeline_complete 被正确发送
    event_types = [edata.get("type") for _, edata in events if isinstance(edata, dict)]
    print(f"\n  event_types: {event_types}")

    assert "pipeline_start" in event_types
    assert "pipeline_complete" in event_types
    assert event_types.count("expert_speak") == 2, f"Expected 2 expert_speak, got {event_types.count('expert_speak')}"


def test_pipeline_sse_with_container(client, project_with_vision):
    """完整 API SSE 流：容器 + 两专家，管道模式。"""
    pid = project_with_vision

    payload = {
        "meeting_name": "容器管道测试",
        "pipeline": True,
        "experts": [
            {"expert_id": "plot_architect_v1", "node_id": "node_container", "role": "main", "container_id": "container_1"},
            {"expert_id": "web_editor_v1", "role": "review", "container_id": "container_1"},
        ],
        "containers": [
            {
                "container_id": "container_1",
                "name": "测试容器",
                "concurrency": "serial",
                "speaking_mode": "ordered",
                "children": ["plot_architect_v1_main", "web_editor_v1_review"],
                "edges": [],
            }
        ],
        "edges": [],
    }

    response = client.post(
        f"/api/projects/{pid}/meeting/start",
        json=payload,
        headers={"Accept": "text/event-stream"},
    )

    assert response.status_code == 200
    events = parse_sse_events(response)

    print("\n=== 容器管道 SSE ===")
    for evt, data in events:
        if isinstance(data, dict):
            ptype = data.get("type", evt)
            if ptype == "expert_speak":
                print(f"  [{evt}] {ptype}  expert={data.get('expert_type')}  container={data.get('container_id')}")
            else:
                print(f"  [{evt}] {ptype}")
