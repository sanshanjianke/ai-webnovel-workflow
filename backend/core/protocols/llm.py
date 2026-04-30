from abc import ABC, abstractmethod
from typing import Iterator, Any, Tuple, Union


class BaseLLMProvider(ABC):
    @abstractmethod
    def invoke(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Iterator[Union[Tuple[str, str], str]]:
        pass
