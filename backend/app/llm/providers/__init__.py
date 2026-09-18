"""Model provider adapters. Each one speaks one vendor's API and nothing else."""

from typing import Protocol

from app.llm.types import ModelRequest, ModelResponse


class ModelProvider(Protocol):
    """What the gateway needs from a provider."""

    name: str

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """One request, one answer. Raises `ModelError` on failure."""
        ...
