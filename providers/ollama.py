import json
import uuid
from typing import Any, Generator

import requests

from providers.base import AssistantResponse, BaseProvider, ProviderError, ToolCall, StreamChunk


class OllamaProvider(BaseProvider):
    """Adapt the common agent interface to Ollama's native chat API."""

    def __init__(self, name: str, base_url: str, model: str) -> None:
        # Keep provider-specific configuration inside this adapter.
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        """Dynamically retrieve the model's context window from Ollama's /api/show endpoint."""
        try:
            # Query the model details to find the context window parameter.
            response = requests.post(
                f"{self._base_url}/api/show",
                json={"name": self._model},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            # Ollama stores model details in model_info. Look for context_length or num_ctx.
            info = data.get("model_info", {})
            # The parameter name can vary by model family; check common patterns.
            for key in info:
                if "context_length" in key.lower() or "num_ctx" in key.lower():
                    val = info[key]
                    if isinstance(val, int):
                        return val

            # If not found in model_info, check the template or parameters directly if available.
            parameters = data.get("parameters", {})
            if isinstance(parameters, dict) and "num_ctx" in parameters:
                val = parameters["num_ctx"]
                if isinstance(val, int):
                    return val

        except (requests.exceptions.RequestException, ValueError, KeyError):
            # Fallback to a sensible default if retrieval fails.
            pass

        return 16384

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AssistantResponse:
        # For consistency, the synchronous chat method now uses the streaming implementation
        # and aggregates all chunks into a single final response.
        full_content = ""
        tool_calls = []

        for chunk in self.stream_chat(messages, tools):
            if chunk.text:
                full_content += chunk.text
            if chunk.tool_call:
                tool_calls.append(chunk.tool_call)

        return AssistantResponse(full_content, tool_calls)

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Generator[StreamChunk, None, None]:
        """Stream normalized response fragments using Ollama's /api/chat streaming mode."""
        # Convert normalized tool-call history into Ollama's message format.
        ollama_messages = []
        for message in messages:
            converted = {
                "role": message["role"],
                "content": message.get("content", ""),
            }
            if message["role"] == "assistant" and message.get("tool_calls"):
                converted["tool_calls"] = [
                    {
                        "function": {
                            "name": tool_call["name"],
                            "arguments": tool_call["arguments"],
                        }
                    }
                    for tool_call in message["tool_calls"]
                ]
            elif message["role"] == "tool":
                converted["name"] = message["name"]
            ollama_messages.append(converted)

        try:
            # Use stream=True to receive responses as a sequence of JSON objects.
            response = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": ollama_messages,
                    "tools": tools,
                    "stream": True,
                },
                timeout=120,
                stream=True,
            )
            response.raise_for_status()

            # Iterate over the response line by line.
            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    # Each line is a standalone JSON object.
                    data = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                if not isinstance(data, dict) or "message" not in data:
                    continue

                message = data["message"]

                # 1. Handle streaming text content.
                content = message.get("content")
                if content:
                    yield StreamChunk(text=content)

                # 2. Handle tool calls.
                # Ollama typically sends tool calls as complete objects in the stream.
                raw_tool_calls = message.get("tool_calls")
                if raw_tool_calls:
                    if not isinstance(raw_tool_calls, list):
                        continue

                    for index, raw_tool_call in enumerate(raw_tool_calls):
                        if not isinstance(raw_tool_call, dict):
                            continue

                        function = raw_tool_call.get("function")
                        if not isinstance(function, dict):
                            continue

                        name = function.get("name")
                        arguments = function.get("arguments", {})

                        if not isinstance(name, str):
                            continue

                        # Normalize arguments from string to dict if necessary.
                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                continue

                        if not isinstance(arguments, dict):
                            continue

                        call_id = raw_tool_call.get("id")
                        if not isinstance(call_id, str) or not call_id:
                            call_id = f"ollama-stream-{uuid.uuid4().hex}-{index}"

                        yield StreamChunk(tool_call=ToolCall(call_id, name, arguments))

        except requests.exceptions.RequestException as error:
            raise ProviderError(f"Ollama streaming request failed: {error}") from error
