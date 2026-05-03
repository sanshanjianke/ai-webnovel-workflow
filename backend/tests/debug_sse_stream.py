"""
端到端调试脚本：模拟前端接收的完整 SSE 事件流并打印每个事件的内容。
用法: cd /home/ssjk/talk && venv/bin/python backend/tests/debug_sse_stream.py
"""

import json
import sys
import os

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.registry import discover_modules, MODULE_REGISTRY
from backend.core.config import get_config
from backend.modules.llm.mock import MockLLM

# Use mock LLM
discover_modules()
MODULE_REGISTRY["llm"]["mock"] = MockLLM
config = get_config()
config.llm.primary = "mock"

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

# Create project
resp = client.post("/api/projects/", json={"name": "SSE调试项目"})
assert resp.status_code == 200, resp.text
pid = resp.json()["id"]
print(f"项目 ID: {pid}")

# Generate L1 vision
resp = client.post(f"/api/projects/{pid}/l1/generate", json={
    "idea": "主角穿越修真世界带AI系统",
    "rough_outline": "1.穿越 2.修炼 3.打脸 4.登顶",
})
assert resp.status_code == 200, resp.text

# Send pipeline request
payload = {
    "meeting_name": "管道SSE调试",
    "pipeline": True,
    "experts": [
        {"expert_id": "plot_architect_v1", "node_id": "node_0", "role": "main"},
        {"expert_id": "web_editor_v1", "node_id": "node_1", "role": "review"},
    ],
    "containers": [],
    "edges": [{"source": "node_0", "target": "node_1"}],
}

response = client.post(
    f"/api/projects/{pid}/meeting/start",
    json=payload,
    headers={"Accept": "text/event-stream"},
)

print(f"HTTP status: {response.status_code}")
print(f"Response length: {len(response.text)} 字节")
print()

# Parse SSE events
lines = response.text.split('\n')
event_type = ''
events = []

for i, line in enumerate(lines):
    line = line.strip()
    if not line:
        continue
    if line.startswith('event: '):
        event_type = line[7:].strip()
    elif line.startswith('data: '):
        data_str = line[6:]
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            data = data_str
        events.append((event_type, data))
        event_type = ''

print(f"共 {len(events)} 个 SSE 事件:\n")

for evt, data in events:
    if isinstance(data, dict):
        t = data.get("type", evt)
        if t == "expert_start":
            print(f"  [{evt}] expert_start  expert={data.get('expert_type')}  node_id={data.get('node_id')}")
        elif t == "expert_chunk":
            ct = data.get("chunk_type", "?")
            c = data.get("content", "")
            print(f"  [{evt}] expert_chunk  type={ct}  len={len(c)}  content={c[:60]}...")
        elif t == "expert_speak":
            c = data.get("content", "")
            suggestions = data.get("suggestions", [])
            print(f"  [{evt}] expert_speak  expert={data.get('expert_type')}  content_len={len(c)}  suggestions={suggestions}")
        elif t == "pipeline_complete":
            output = data.get("output", {})
            nos = output.get("node_outputs", {})
            print(f"  [{evt}] pipeline_complete  speeches={output.get('total_speeches')}")
            for nid, nout in nos.items():
                print(f"         node_outputs[{nid}]: {len(nout)} 字符  preview={nout[:80]}")
        elif t == "pipeline_start":
            print(f"  [{evt}] pipeline_start  levels={data.get('levels')}  nodes={data.get('nodes')}")
        elif t in ("level_start", "level_complete"):
            print(f"  [{evt}] {t}  level={data.get('level')}")
        elif t == "done":
            print(f"  [{evt}] done  {data}")
        else:
            print(f"  [{evt}] {t}")
    else:
        print(f"  [{evt}] raw: {str(data)[:80]}")

# Check for issues
expert_chunks = sum(1 for evt, data in events if isinstance(data, dict) and data.get("type") == "expert_chunk")
expert_speaks = sum(1 for evt, data in events if isinstance(data, dict) and data.get("type") == "expert_speak")
pipeline_starts = sum(1 for evt, data in events if isinstance(data, dict) and data.get("type") == "pipeline_start")
pipeline_completes = sum(1 for evt, data in events if isinstance(data, dict) and data.get("type") == "pipeline_complete")

print(f"\n总结: pipeline_start={pipeline_starts}  expert_chunks={expert_chunks}  expert_speaks={expert_speaks}  pipeline_complete={pipeline_completes}")

if expert_chunks == 0:
    print("\n!! 警告: 没有收到任何 expert_chunk 事件! 流式输出未生效!")
if expert_speaks == 0:
    print("\n!! 警告: 没有收到 expert_speak 事件!")
