from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class VisionDocument(BaseModel):
    core_idea: str
    target_readers: str = ""
    core_appeal: str = ""
    style: str = ""
    rough_outline: str = ""
    world_setting: str = ""
    protagonist: str = ""
    golden_finger: str = ""
    hot_elements: str = ""
    expected_length: str = ""


class BaseSeedGenerator(ABC):
    @abstractmethod
    def generate(self, user_input: dict) -> VisionDocument:
        pass
