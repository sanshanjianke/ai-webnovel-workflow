"""Generation stop manager - 管理活跃的生成任务，支持停止操作"""

import threading
from typing import Dict, Optional


class GenerationManager:
    """管理生成任务，支持停止操作"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._stop_flags: Dict[str, bool] = {}
        self._lock = threading.Lock()
    
    def start_generation(self, project_id: str) -> None:
        """开始新的生成任务"""
        with self._lock:
            self._stop_flags[project_id] = False
    
    def stop_generation(self, project_id: str) -> bool:
        """停止指定项目的生成"""
        with self._lock:
            if project_id in self._stop_flags:
                self._stop_flags[project_id] = True
                return True
            return False
    
    def should_stop(self, project_id: str) -> bool:
        """检查是否应该停止"""
        with self._lock:
            return self._stop_flags.get(project_id, False)
    
    def end_generation(self, project_id: str) -> None:
        """结束生成任务"""
        with self._lock:
            if project_id in self._stop_flags:
                del self._stop_flags[project_id]


# 全局实例
def get_generation_manager() -> GenerationManager:
    return GenerationManager()
