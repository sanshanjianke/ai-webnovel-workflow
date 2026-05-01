from pydantic import BaseModel
from typing import Optional
from backend.core.protocols.llm import BaseLLMProvider
from backend.core.protocols.rag import BaseRAGAgent
from backend.core.protocols.worldbook import BaseWorldBook
from backend.core.protocols.l1 import BaseSeedGenerator
from backend.core.protocols.expert import BaseExpert
from backend.core.protocols.meeting import BaseMeetingProtocol
from backend.core.protocols.l3 import BaseL3Narrative
from backend.core.protocols.l4 import BaseL4Renderer


MODULE_REGISTRY: dict[str, dict[str, type]] = {
    "llm": {},
    "rag": {},
    "worldbook": {},
    "l1": {},
    "l3": {},
    "l4": {},
    "expert": {},
    "meeting_protocol": {},
}


def _camel_to_snake(name: str) -> str:
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def register_module(category: str):
    def decorator(cls):
        key = _camel_to_snake(cls.__name__)
        suffixes = ['_provider', '_agent', '_generator', '_architect',
                    '_editor', '_designer', '_renderer', '_narrative',
                    '_protocol', '_world_book', '_retriever']
        for suffix in suffixes:
            if key.endswith(suffix):
                key = key[:-len(suffix)]
                break
        if key.startswith('base_'):
            return cls
        MODULE_REGISTRY[category][key] = cls
        return cls
    return decorator


def get_module(category: str, key: str):
    if category not in MODULE_REGISTRY:
        raise ValueError(f"Unknown category: {category}")
    if key not in MODULE_REGISTRY[category]:
        raise ValueError(f"Unknown module: {category}/{key}")
    return MODULE_REGISTRY[category][key]


def list_modules(category: str) -> list[str]:
    return list(MODULE_REGISTRY.get(category, {}).keys())


def discover_modules():
    import importlib
    import pkgutil
    from pathlib import Path

    backend_path = Path(__file__).parent.parent

    # LLM, RAG, Worldbook, L1, L3, L4
    for category in ["llm", "rag", "worldbook", "l1", "l3", "l4"]:
        module_path = backend_path / "modules" / category
        if module_path.exists():
            try:
                importlib.import_module(f"backend.modules.{category}")
            except Exception as e:
                print(f"Warning: Failed to import {category}.__init__: {e}")
            for _, module_name, _ in pkgutil.iter_modules([str(module_path)]):
                try:
                    importlib.import_module(f"backend.modules.{category}.{module_name}")
                except Exception as e:
                    print(f"Warning: Failed to import {category}.{module_name}: {e}")

    # Unified experts
    experts_path = backend_path / "modules" / "experts"
    if experts_path.exists():
        try:
            importlib.import_module("backend.modules.experts")
        except Exception as e:
            print(f"Warning: Failed to import experts: {e}")

    # Orchestration engine
    orch_path = backend_path / "modules" / "orchestration"
    if orch_path.exists():
        try:
            importlib.import_module("backend.modules.orchestration")
        except Exception as e:
            print(f"Warning: Failed to import orchestration: {e}")

    # Meeting protocols
    meeting_path = backend_path / "meeting_protocols"
    if meeting_path.exists():
        for _, module_name, _ in pkgutil.iter_modules([str(meeting_path)]):
            try:
                importlib.import_module(f"backend.meeting_protocols.{module_name}")
            except Exception as e:
                print(f"Warning: Failed to import meeting_protocols.{module_name}: {e}")

    # Legacy: import old l2 experts and l1_5 for backward compat
    _import_legacy_modules(backend_path)


def _import_legacy_modules(backend_path):
    """Import legacy modules for backward compatibility during migration"""
    import importlib
    import pkgutil

    # Old l2 experts are consolidated into modules/experts/,
    # but import to pick up any @register_module decorators that may remain
    for legacy in ["l1_5"]:
        module_path = backend_path / "modules" / legacy
        if module_path.exists():
            try:
                importlib.import_module(f"backend.modules.{legacy}")
            except Exception as e:
                print(f"Warning: Failed to import legacy {legacy}: {e}")
            for _, module_name, _ in pkgutil.iter_modules([str(module_path)]):
                try:
                    importlib.import_module(f"backend.modules.{legacy}.{module_name}")
                except Exception as e:
                    print(f"Warning: Failed to import legacy {legacy}.{module_name}: {e}")
