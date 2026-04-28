import pytest
from fastapi.testclient import TestClient
import json


@pytest.fixture
def client():
    from backend.main import app
    from backend.core.registry import discover_modules
    discover_modules()
    return TestClient(app)


@pytest.fixture
def project_with_l1(client):
    from backend.core.config import get_config
    from backend.core import registry
    from backend.modules.llm.mock import MockLLM
    
    registry.MODULE_REGISTRY["llm"]["mock"] = MockLLM
    config = get_config()
    config.llm.primary = "mock"
    
    resp = client.post("/api/projects/", json={"name": "L2测试项目"})
    project_id = resp.json()["id"]
    
    client.post(f"/api/projects/{project_id}/l1/generate", json={
        "idea": "主角穿越修真世界带AI系统"
    })
    
    return project_id


def test_l2_stream(client, project_with_l1):
    from backend.core.config import get_config
    from backend.core import registry
    from backend.modules.llm.mock import MockLLM
    
    registry.MODULE_REGISTRY["llm"]["mock"] = MockLLM
    config = get_config()
    config.llm.primary = "mock"
    
    response = client.get(f"/api/projects/{project_with_l1}/l2/stream?collaboration_mode=full_auto")
    
    assert response.status_code == 200
    
    content = response.text
    assert "event:" in content or "outline_ready" in content or "done" in content


def test_l2_outline_crud(client, project_with_l1):
    from backend.core.config import get_config
    from backend.core import registry
    from backend.modules.llm.mock import MockLLM
    
    registry.MODULE_REGISTRY["llm"]["mock"] = MockLLM
    config = get_config()
    config.llm.primary = "mock"
    
    client.get(f"/api/projects/{project_with_l1}/l2/stream?collaboration_mode=full_auto")
    
    get_resp = client.get(f"/api/projects/{project_with_l1}/l2/outline")
    assert get_resp.status_code == 200
    assert "outline" in get_resp.json()
    
    update_resp = client.put(f"/api/projects/{project_with_l1}/l2/outline", json={
        "sequences": [{"name": "测试序列"}]
    })
    assert update_resp.status_code == 200
