from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generator, Optional, Union


class ProviderError(Exception):
    """Describe a provider request or response failure in a provider-neutral way."""


@dataclass(frozen=True)
class ToolCall:
    """Normalized tool-call data shared by every provider adapter."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class StreamChunk:
    """A fragment of a streaming response, containing either text or a completed tool call."""
    text: Optional[str] = None
    tool_call: Optional[ToolCall] = None


@dataclass(frozen=True)
class AssistantResponse:
    """Normalized assistant response shared by every provider adapter."""

    content: str
    tool_calls: list[ToolCall]


class BaseProvider(ABC):
    """Define the provider interface without implementing shared behavior."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider's user-facing configured name."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the selected model name."""

    @property
    @abstractmethod
    def context_window(self) -> int:
        """Return the model's context window size in tokens."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AssistantResponse:
        """Send normalized history and tool schemas, then normalize the response."""

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Generator[StreamChunk, None, None]:
        """Stream normalized response fragments including text and tool calls."""
