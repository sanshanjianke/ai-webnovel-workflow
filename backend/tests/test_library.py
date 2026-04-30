import pytest
import tempfile
import shutil
from pathlib import Path
import json

from backend.services.library_manager import (
    LibraryManager,
    DocEntry,
    DocSource,
    DocStatus,
    LibraryManifest,
)


@pytest.fixture
def temp_project_path():
    temp_dir = tempfile.mkdtemp()
    project_path = Path(temp_dir) / "test_project"
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "outputs").mkdir(parents=True, exist_ok=True)
    yield project_path
    shutil.rmtree(temp_dir)


def test_library_init(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    assert library.library_path.exists()
    assert library.files_path.exists()
    assert library.manifest_path.exists()
    assert library.manifest is not None
    assert library.manifest.project_id == "test_project"


def test_add_document(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    content = {"idea": "废土倒爷", "target_readers": "男频"}
    uid = library.add_document(
        name="L1 愿景 — 废土倒爷",
        layer="l1",
        content=content,
    )
    
    assert uid is not None
    assert len(uid) == 8
    
    result = library.get_document(uid)
    assert result is not None
    entry, loaded_content = result
    
    assert entry.name == "L1 愿景 — 废土倒爷"
    assert entry.layer == "l1"
    assert entry.source == DocSource.GENERATE
    assert loaded_content == content


def test_update_entry(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    uid = library.add_document(
        name="Test Doc",
        layer="l1",
        content={"test": "data"},
    )
    
    updated = library.update_entry(uid, name="Updated Name", tags=["tag1", "tag2"])
    
    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.tags == ["tag1", "tag2"]
    
    entry = library.get_entry(uid)
    assert entry.name == "Updated Name"


def test_update_content(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    uid = library.add_document(
        name="Test Doc",
        layer="l1",
        content={"old": "data"},
    )
    
    success = library.update_content(uid, {"new": "data"})
    assert success is True
    
    result = library.get_document(uid)
    _, content = result
    assert content == {"new": "data"}


def test_delete_document(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    uid = library.add_document(
        name="Test Doc",
        layer="l1",
        content={"test": "data"},
    )
    
    success = library.delete_document(uid)
    assert success is True
    
    result = library.get_document(uid)
    assert result is None


def test_archive_document(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    uid = library.add_document(
        name="Test Doc",
        layer="l1",
        content={"test": "data"},
    )
    
    entry = library.archive_document(uid, archive=True)
    assert entry.status == DocStatus.ARCHIVED
    
    entry = library.archive_document(uid, archive=False)
    assert entry.status == DocStatus.ACTIVE


def test_active_document(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    uid1 = library.add_document(
        name="Doc 1",
        layer="l1",
        content={"test": "1"},
    )
    
    uid2 = library.add_document(
        name="Doc 2",
        layer="l1",
        content={"test": "2"},
    )
    
    library.set_active("l1", uid1)
    assert library.get_active("l1") == uid1
    
    library.set_active("l1", uid2)
    assert library.get_active("l1") == uid2


def test_parent_child_relationship(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    parent_uid = library.add_document(
        name="L1 Vision",
        layer="l1",
        content={"vision": "data"},
    )
    
    child_uid = library.add_document(
        name="L2 Outline",
        layer="l2",
        content={"outline": "data"},
        parent_uid=parent_uid,
    )
    
    children = library.get_children(parent_uid)
    assert len(children) == 1
    assert children[0].uid == child_uid
    
    chain = library.get_provenance_chain(child_uid)
    assert len(chain) == 2
    assert chain[0].uid == child_uid
    assert chain[1].uid == parent_uid


def test_list_documents(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    library.add_document(name="L1 Doc 1", layer="l1", content={})
    library.add_document(name="L1 Doc 2", layer="l1", content={})
    library.add_document(name="L2 Doc 1", layer="l2", content={})
    
    all_docs = library.list_documents()
    assert len(all_docs) == 3
    
    l1_docs = library.list_documents(layer="l1")
    assert len(l1_docs) == 2
    
    l2_docs = library.list_documents(layer="l2")
    assert len(l2_docs) == 1


def test_directories(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    success = library.create_directory("/草稿")
    assert success is True
    
    assert "/草稿" in library.manifest.directories
    
    success = library.create_directory("/草稿")
    assert success is False
    
    library.add_document(
        name="Test",
        layer="l1",
        content={},
        directory="/草稿",
    )
    
    docs = library.list_documents(directory="/草稿")
    assert len(docs) == 1


def test_import_file(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    uid = library.import_file(
        name="导入 — test.json",
        content={"imported": "data"},
        format="json",
    )
    
    entry = library.get_entry(uid)
    assert entry.layer == "imported"
    assert entry.source == DocSource.IMPORT


def test_migrate_old_outputs(temp_project_path):
    outputs_path = temp_project_path / "outputs"
    
    old_vision = {"idea": "old vision", "target_readers": "男频"}
    with open(outputs_path / "l1_vision.json", "w", encoding="utf-8") as f:
        json.dump(old_vision, f)
    
    old_outline = {"sequences": []}
    with open(outputs_path / "l2_outline.json", "w", encoding="utf-8") as f:
        json.dump(old_outline, f)
    
    library = LibraryManager(temp_project_path)
    
    docs = library.list_documents()
    assert len(docs) >= 2
    
    l1_docs = [d for d in docs if d.layer == "l1"]
    assert len(l1_docs) >= 1
    
    migrated_marker = outputs_path / ".migrated"
    assert migrated_marker.exists()
    
    library2 = LibraryManager(temp_project_path)
    assert len(library2.list_documents()) == len(docs)


def test_word_count(temp_project_path):
    library = LibraryManager(temp_project_path)
    
    text_content = "这是一段测试文本，用于测试字数统计功能。"
    uid = library.add_document(
        name="Test",
        layer="l1",
        content=text_content,
    )
    
    entry = library.get_entry(uid)
    assert entry.word_count > 0
    
    dict_content = {"text": "这是字典内容的测试"}
    uid2 = library.add_document(
        name="Test 2",
        layer="l1",
        content=dict_content,
    )
    
    entry2 = library.get_entry(uid2)
    assert entry2.word_count > 0
