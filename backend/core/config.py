import yaml
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class LLMConfig(BaseModel):
    primary: str = "open_ai_compat"
    embedding: str = "text-embedding-v3"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"


class RAGConfig(BaseModel):
    history: str = "hybrid_retriever"
    technique: str = "simple_vector"


class WorldBookConfig(BaseModel):
    strategy: str = "st_style"
    auto_manage: bool = True


class ExpertConfig(BaseModel):
    architect: str = "plot_architect_v1"
    editor: str = "web_editor_v1"
    character: str = "character_designer_v1"


class L15ExpertConfig(BaseModel):
    author: str = "senior_author_v1"
    reader: str = "reader_representative_v1"


class L15Config(BaseModel):
    meeting_protocol: str = "editor_reader"
    collaboration_mode: str = "semi_auto"
    max_rounds: int = 3
    experts: L15ExpertConfig = L15ExpertConfig()


class L2Config(BaseModel):
    meeting_protocol: str = "plot_driven"
    collaboration_mode: str = "semi_auto"
    max_rounds: int = 3
    experts: ExpertConfig = ExpertConfig()


class L3Config(BaseModel):
    strategy: str = "mapping_compiler"


class L4Config(BaseModel):
    strategy: str = "constrained_renderer"


class PipelineConfig(BaseModel):
    l1_5: L15Config = L15Config()
    l2: L2Config = L2Config()
    l3: L3Config = L3Config()
    l4: L4Config = L4Config()


class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    rag: RAGConfig = RAGConfig()
    worldbook: WorldBookConfig = WorldBookConfig()
    pipeline: PipelineConfig = PipelineConfig()


_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    global _config
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "data" / "user" / "config.yaml"
    
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _config = AppConfig(**data)
    else:
        _config = AppConfig()
        save_config(_config, config_path)
    
    return _config


def save_config(config: AppConfig, config_path: Optional[Path] = None):
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "data" / "user" / "config.yaml"
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config.model_dump(), f, allow_unicode=True, default_flow_style=False)
