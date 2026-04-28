import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProjectConfig(BaseModel):
    name: str
    description: str = ""
    genre: str = ""
    target_platform: str = ""
    driving_mode: str = "plot_driven"
    created_at: str = ""
    updated_at: str = ""


class Project:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.config_path = project_path / "project.json"
        self.config: Optional[ProjectConfig] = None
        self._load()

    def _load(self):
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.config = ProjectConfig(**data)

    def _save(self):
        self.project_path.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.model_dump(), f, ensure_ascii=False, indent=2)

    def update_config(self, **kwargs):
        if self.config:
            self.config.updated_at = datetime.now().isoformat()
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            self._save()

    @property
    def id(self) -> str:
        return self.project_path.name


class ProjectManager:
    def __init__(self, data_path: Path = None):
        if data_path is None:
            data_path = Path(__file__).parent.parent.parent / "data" / "projects"
        self.data_path = data_path
        self.data_path.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str, **kwargs) -> Project:
        project_id = kwargs.get("id") or str(uuid.uuid4())[:8]
        project_path = self.data_path / project_id
        project_path.mkdir(parents=True, exist_ok=True)
        
        config = ProjectConfig(
            name=name,
            description=kwargs.get("description", ""),
            genre=kwargs.get("genre", ""),
            target_platform=kwargs.get("target_platform", ""),
            driving_mode=kwargs.get("driving_mode", "plot_driven"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        config_path = project_path / "project.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)
        
        project = Project(project_path)
        
        worldbook_path = project_path / "worldbook.json"
        if not worldbook_path.exists():
            with open(worldbook_path, "w", encoding="utf-8") as f:
                json.dump({"entries": {}}, f, ensure_ascii=False, indent=2)
        
        outputs_path = project_path / "outputs"
        outputs_path.mkdir(exist_ok=True)
        
        logs_path = project_path / "logs"
        logs_path.mkdir(exist_ok=True)
        
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        project_path = self.data_path / project_id
        if project_path.exists():
            return Project(project_path)
        return None

    def list_projects(self) -> list[Project]:
        projects = []
        for path in self.data_path.iterdir():
            if path.is_dir() and (path / "project.json").exists():
                projects.append(Project(path))
        return sorted(projects, key=lambda p: p.config.updated_at if p.config else "", reverse=True)

    def delete_project(self, project_id: str) -> bool:
        import shutil
        project_path = self.data_path / project_id
        if project_path.exists():
            shutil.rmtree(project_path)
            return True
        return False


_project_manager: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager
