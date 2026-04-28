import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def temp_data_dir():
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_create_project(client):
    response = client.post("/api/projects/", json={
        "name": "测试小说",
        "description": "一本测试用的小说",
        "genre": "玄幻",
        "target_platform": "起点"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["config"]["name"] == "测试小说"
    assert data["config"]["genre"] == "玄幻"


def test_list_projects(client):
    client.post("/api/projects/", json={"name": "项目1"})
    client.post("/api/projects/", json={"name": "项目2"})
    
    response = client.get("/api/projects/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_get_project(client):
    create_resp = client.post("/api/projects/", json={"name": "获取测试"})
    project_id = create_resp.json()["id"]
    
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["config"]["name"] == "获取测试"


def test_update_project(client):
    create_resp = client.post("/api/projects/", json={"name": "更新测试"})
    project_id = create_resp.json()["id"]
    
    response = client.put(f"/api/projects/{project_id}/config", json={
        "description": "更新后的描述"
    })
    assert response.status_code == 200
    assert response.json()["config"]["description"] == "更新后的描述"


def test_worldbook_crud(client):
    create_resp = client.post("/api/projects/", json={"name": "世界书测试"})
    project_id = create_resp.json()["id"]
    
    entry_resp = client.post(f"/api/projects/{project_id}/worldbook", json={
        "id": "char_001",
        "keys": ["老周", "周师傅"],
        "content": "老周，金丹期鉴定师，青云拍卖行首席。",
        "secondary_keys": ["拍卖行"],
        "priority": 10
    })
    assert entry_resp.status_code == 200
    assert entry_resp.json()["status"] == "created"
    
    list_resp = client.get(f"/api/projects/{project_id}/worldbook")
    assert list_resp.status_code == 200
    entries = list_resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["content"] == "老周，金丹期鉴定师，青云拍卖行首席。"
    
    get_resp = client.get(f"/api/projects/{project_id}/worldbook/entry/char_001")
    assert get_resp.status_code == 200
    assert get_resp.json()["keys"] == ["老周", "周师傅"]
    
    update_resp = client.put(f"/api/projects/{project_id}/worldbook/entry/char_001", json={
        "content": "老周，元婴期鉴定师，青云拍卖行首席。"
    })
    assert update_resp.status_code == 200
    
    delete_resp = client.delete(f"/api/projects/{project_id}/worldbook/entry/char_001")
    assert delete_resp.status_code == 200
    
    list_resp = client.get(f"/api/projects/{project_id}/worldbook")
    assert len(list_resp.json()["entries"]) == 0


def test_worldbook_commit(client):
    create_resp = client.post("/api/projects/", json={"name": "提交测试"})
    project_id = create_resp.json()["id"]
    
    client.post(f"/api/projects/{project_id}/worldbook", json={
        "id": "char_001",
        "keys": ["测试"],
        "content": "测试条目"
    })
    
    commit_resp = client.post(f"/api/projects/{project_id}/worldbook/commit?message=添加测试条目")
    assert commit_resp.status_code == 200
    assert "hash" in commit_resp.json()
    
    commits_resp = client.get(f"/api/projects/{project_id}/worldbook/commits")
    assert commits_resp.status_code == 200
    commits = commits_resp.json()["commits"]
    assert len(commits) == 1
    assert commits[0]["message"] == "添加测试条目"
