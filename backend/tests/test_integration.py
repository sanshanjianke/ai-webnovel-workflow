import pytest
import tempfile
import os
from backend.modules.rag.simple_vector import SimpleVectorRetriever
from backend.modules.l3.mapping_compiler import MappingCompiler
from backend.modules.l4.constrained import ConstrainedRenderer
from backend.core.protocols.rag import Document
from backend.core.protocols.worldbook import Entry
from backend.services.worldbook_manager import WorldBookManager
from backend.modules.worldbook.st_style import STStyleWorldBook


class TestRAGIntegration:
    def test_rag_index_and_retrieve(self):
        rag = SimpleVectorRetriever()
        docs = [
            Document(id="doc1", content="主角是一个穿越者，拥有现代知识"),
            Document(id="doc2", content="世界观设定：修仙世界，等级分为练气、筑基、金丹"),
            Document(id="doc3", content="反派角色：魔教教主，心狠手辣"),
        ]
        rag.index(docs)
        
        results = rag.retrieve("主角")
        assert len(results) > 0
        
        rag.delete(["doc1", "doc2", "doc3"])
        assert rag.count() == 0


class TestL3Integration:
    def test_mapping_compiler_init(self):
        compiler = MappingCompiler()
        assert compiler is not None


class TestL4Integration:
    def test_constrained_renderer_init(self):
        renderer = ConstrainedRenderer()
        assert renderer is not None


class TestWorldBookManager:
    def test_worldbook_manager_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            worldbook = STStyleWorldBook(tmpdir)
            manager = WorldBookManager(worldbook)
            assert manager is not None
    
    def test_worldbook_crud(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            worldbook = STStyleWorldBook(tmpdir)
            
            entry = Entry(id="protagonist", keys=["主角", "张三"], content="张三，穿越者")
            worldbook.create_entry(entry)
            
            retrieved = worldbook.get_entry("protagonist")
            assert retrieved.content == "张三，穿越者"
            
            worldbook.update_entry("protagonist", {"content": "张三，穿越者，拥有系统"})
            updated = worldbook.get_entry("protagonist")
            assert "系统" in updated.content
            
            worldbook.delete_entry("protagonist")
            assert worldbook.get_entry("protagonist") is None
