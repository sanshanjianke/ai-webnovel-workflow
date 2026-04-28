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
def project_with_vision(client):
    resp = client.post("/api/projects/", json={"name": "L1测试项目"})
    return resp.json()["id"]


def test_l1_generate(client, project_with_vision):
    from backend.core.config import get_config
    from backend.core import registry
    from backend.modules.llm.mock import MockLLM
    
    registry.MODULE_REGISTRY["llm"]["mock"] = MockLLM
    
    config = get_config()
    config.llm.primary = "mock"
    
    response = client.post(f"/api/projects/{project_with_vision}/l1/generate", json={
        "idea": "主角穿越修真世界带AI系统",
        "target_readers": "男频"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "generated"
    assert "vision" in data
    assert "核心梗" in data["vision"]["core_idea"] or data["vision"]["core_idea"]


def test_l1_get_vision(client, project_with_vision):
    from backend.core.config import get_config
    from backend.core import registry
    from backend.modules.llm.mock import MockLLM
    
    registry.MODULE_REGISTRY["llm"]["mock"] = MockLLM
    
    config = get_config()
    config.llm.primary = "mock"
    
    client.post(f"/api/projects/{project_with_vision}/l1/generate", json={
        "idea": "测试创意"
    })
    
    response = client.get(f"/api/projects/{project_with_vision}/l1/vision")
    assert response.status_code == 200
    assert "vision" in response.json()


def test_l1_update_vision(client, project_with_vision):
    from backend.core.config import get_config
    from backend.core import registry
    from backend.modules.llm.mock import MockLLM
    
    registry.MODULE_REGISTRY["llm"]["mock"] = MockLLM
    
    config = get_config()
    config.llm.primary = "mock"
    
    client.post(f"/api/projects/{project_with_vision}/l1/generate", json={
        "idea": "测试创意"
    })
    
    response = client.put(f"/api/projects/{project_with_vision}/l1/vision", json={
        "core_idea": "更新后的核心梗"
    })
    
    assert response.status_code == 200
    assert response.json()["vision"]["core_idea"] == "更新后的核心梗"
