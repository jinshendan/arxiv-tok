from __future__ import annotations

import json
import os

import httpx

from .config import ModelConfig


class LLMProviderClient:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.provider = config.provider.strip().lower()
        self.base_url = config.base_url.rstrip("/")
        self.api_key = os.getenv(config.api_key_env, "").strip()

    @property
    def chat_enabled(self) -> bool:
        if not self.config.enabled or not self.config.model:
            return False
        if self.provider == "openai" and not self.api_key:
            return False
        if self.config.require_api_key and not self.api_key and self.provider != "ollama":
            return False
        return True

    @property
    def embedding_enabled(self) -> bool:
        if not self.chat_enabled:
            return False
        return bool(self.config.embedding_model)

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.chat_enabled:
            raise ValueError("model provider is not enabled for chat")

        if self.provider in {"openai", "openai_compatible"}:
            text = self._chat_via_chat_completions(system_prompt, user_prompt)
            return json.loads(text)
        if self.provider == "ollama":
            text = self._chat_via_ollama(system_prompt, user_prompt)
            return json.loads(text)

        raise ValueError(f"unsupported provider: {self.provider}")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding_enabled:
            raise ValueError("model provider is not enabled for embeddings")

        if self.provider in {"openai", "openai_compatible"}:
            return self._embed_via_openai_compatible(texts)
        if self.provider == "ollama":
            return self._embed_via_ollama(texts)

        raise ValueError(f"unsupported provider: {self.provider}")

    def _chat_via_chat_completions(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("empty chat completions response")
        msg = choices[0].get("message", {})
        content = msg.get("content", "")
        if isinstance(content, list):
            content = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in content
            )
        text = str(content).strip()
        if not text:
            raise ValueError("empty chat content")
        return text

    def _chat_via_ollama(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }

        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        message = data.get("message", {})
        text = str(message.get("content", "")).strip()
        if not text:
            raise ValueError("empty ollama chat content")
        return text

    def _embed_via_openai_compatible(self, texts: list[str]) -> list[list[float]]:
        url = f"{self.base_url}/embeddings"
        payload = {"model": self.config.embedding_model, "input": texts}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        items = data.get("data", [])
        if len(items) != len(texts):
            raise ValueError("unexpected embedding response size")
        return [item["embedding"] for item in items]

    def _embed_via_ollama(self, texts: list[str]) -> list[list[float]]:
        # Prefer newer /api/embed, fallback to /api/embeddings for compatibility.
        url = f"{self.base_url}/api/embed"
        payload = {"model": self.config.embedding_model, "input": texts}
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(url, json=payload)
            if response.status_code == 404:
                return [self._embed_single_via_legacy(client, text) for text in texts]
            response.raise_for_status()
            data = response.json()

        vectors = data.get("embeddings", [])
        if len(vectors) != len(texts):
            raise ValueError("unexpected ollama embedding response size")
        return vectors

    def _embed_single_via_legacy(self, client: httpx.Client, text: str) -> list[float]:
        url = f"{self.base_url}/api/embeddings"
        payload = {"model": self.config.embedding_model, "prompt": text}
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        vector = data.get("embedding")
        if not vector:
            raise ValueError("empty legacy ollama embedding")
        return vector
