"""
LLM Provider abstraction for shoe matching.

Supports:
- Replicate (cloud, pay-per-use)
- Ollama (local, free)
- None (disable LLM overlay)
"""

import os
import json
import logging
import re
from typing import Optional
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        """Generate text from prompt."""
        pass


class ReplicateProvider(LLMProvider):
    """Replicate.com API provider."""

    # IBM Granite 4.0 - available on Replicate
    # Options: ibm-granite/granite-4.0-h-small (32B), ibm-granite/granite-3.1-8b-instruct
    DEFAULT_MODEL = "ibm-granite/granite-4.0-h-small"

    def __init__(self, api_token: Optional[str] = None, model: Optional[str] = None):
        self.api_token = api_token or os.getenv("REPLICATE_API_TOKEN")
        self.model = model or os.getenv("REPLICATE_MODEL", self.DEFAULT_MODEL)

        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN not set")

    async def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        """Call Replicate API using the official model format."""
        async with httpx.AsyncClient(timeout=90.0) as client:
            # Use the models endpoint which handles versioning automatically
            # Format: POST /v1/models/{owner}/{name}/predictions
            model_parts = self.model.split("/")
            if len(model_parts) != 2:
                logger.error(f"Invalid model format: {self.model}")
                return ""

            url = f"https://api.replicate.com/v1/models/{self.model}/predictions"

            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                    "Prefer": "wait",  # Wait for result synchronously if fast enough
                },
                json={
                    "input": {
                        "prompt": prompt,
                        "max_new_tokens": max_tokens,
                        "temperature": 0.3,
                    },
                },
            )

            if response.status_code == 201:
                # Prediction started, need to poll
                prediction = response.json()
                return await self._poll_prediction(client, prediction)

            elif response.status_code == 200:
                # Synchronous response (fast model)
                result = response.json()
                return self._extract_output(result)

            else:
                logger.error(f"Replicate API error: {response.status_code} {response.text}")
                return ""

    async def _poll_prediction(self, client: httpx.AsyncClient, prediction: dict) -> str:
        """Poll for prediction completion."""
        prediction_url = prediction.get("urls", {}).get("get")
        if not prediction_url:
            logger.error("No prediction URL returned")
            return ""

        for _ in range(90):  # Max 90 seconds
            await asyncio.sleep(1)

            status_response = await client.get(
                prediction_url,
                headers={"Authorization": f"Bearer {self.api_token}"},
            )

            if status_response.status_code != 200:
                continue

            result = status_response.json()
            status = result.get("status")

            if status == "succeeded":
                return self._extract_output(result)

            elif status in ("failed", "canceled"):
                logger.error(f"Prediction {status}: {result.get('error')}")
                return ""

        logger.error("Prediction timed out")
        return ""

    def _extract_output(self, result: dict) -> str:
        """Extract text output from prediction result."""
        output = result.get("output", "")
        if isinstance(output, list):
            return "".join(str(x) for x in output)
        return str(output) if output else ""


class OllamaProvider(LLMProvider):
    """Local Ollama provider."""

    DEFAULT_MODEL = "granite4:latest"
    DEFAULT_URL = "http://localhost:11434/api/generate"

    def __init__(self, model: Optional[str] = None, url: Optional[str] = None):
        self.model = model or os.getenv("OLLAMA_MODEL", self.DEFAULT_MODEL)
        self.url = url or os.getenv("OLLAMA_URL", self.DEFAULT_URL)

    async def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        """Call Ollama API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.3,
                        },
                    },
                )

                if response.status_code != 200:
                    logger.error(f"Ollama error: {response.status_code}")
                    return ""

                return response.json().get("response", "")

            except httpx.RequestError as e:
                logger.error(f"Ollama request failed: {e}")
                return ""


class NoOpProvider(LLMProvider):
    """Disabled LLM provider - returns empty string."""

    async def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        return ""


def get_llm_provider() -> LLMProvider:
    """Factory function to get the configured LLM provider."""
    provider_name = os.getenv("LLM_PROVIDER", "none").lower()

    if provider_name == "replicate":
        try:
            return ReplicateProvider()
        except ValueError as e:
            logger.warning(f"Replicate not configured: {e}, falling back to none")
            return NoOpProvider()

    elif provider_name == "ollama":
        return OllamaProvider()

    else:
        return NoOpProvider()


def extract_json_from_response(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response."""
    if not text:
        return None

    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'(\{[\s\S]*\})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# Need asyncio for Replicate polling
import asyncio
