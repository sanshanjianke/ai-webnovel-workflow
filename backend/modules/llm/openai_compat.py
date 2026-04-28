from typing import Iterator, Optional
import httpx
from backend.core.protocols.llm import BaseLLMProvider
from backend.core.registry import register_module
from backend.core.config import get_config


@register_module("llm")
class OpenAICompat(BaseLLMProvider):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        config = get_config()
        self.model = model or getattr(config.llm, 'model', 'GLM-5')
        self.api_key = api_key or config.llm.api_key
        self.base_url = base_url or config.llm.base_url

    def invoke(self, prompt: str, **kwargs) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = kwargs.get("messages", [{"role": "user", "content": prompt}])
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        with httpx.Client(timeout=180.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = kwargs.get("messages", [{"role": "user", "content": prompt}])
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        with httpx.Client(timeout=180.0) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        import json
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
