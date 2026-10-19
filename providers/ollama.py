import json
import uuid
from typing import Any

import requests

from providers.base import AssistantResponse, BaseProvider, ProviderError, ToolCall


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

        # Send Ollama-specific request details only from this adapter.
        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": ollama_messages,
                    "tools": tools,
                    "stream": False,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as error:
            # Expose server response detail through the provider-neutral error.
            response_text = ""
            if error.response is not None:
                response_text = error.response.text
            raise ProviderError(
                f"Ollama request failed: {error}"
                + (f"\nResponse: {response_text}" if response_text else "")
            ) from error
        except ValueError as error:
            # Requests uses ValueError for malformed JSON response bodies.
            raise ProviderError(f"Ollama returned invalid JSON: {error}") from error

        # Normalize Ollama's message and tool calls exactly once at the adapter edge.
        if not isinstance(data, dict) or not isinstance(data.get("message"), dict):
            raise ProviderError("Ollama response must contain a message object.")
        message = data["message"]
        content = message.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise ProviderError("Ollama message content must be text.")

        raw_tool_calls = message.get("tool_calls", [])
        if not isinstance(raw_tool_calls, list):
            raise ProviderError("Ollama tool_calls must be a list.")

        normalized_calls = []
        for index, raw_tool_call in enumerate(raw_tool_calls):
            if not isinstance(raw_tool_call, dict):
                raise ProviderError("Ollama tool call must be an object.")
            function = raw_tool_call.get("function")
            if not isinstance(function, dict):
                raise ProviderError("Ollama tool call is missing its function.")
            name = function.get("name")
            arguments = function.get("arguments", {})
            if not isinstance(name, str):
                raise ProviderError("Ollama tool call name must be text.")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as error:
                    raise ProviderError(
                        f"Ollama tool call arguments are invalid JSON: {error}"
                    ) from error
            if not isinstance(arguments, dict):
                raise ProviderError("Ollama tool call arguments must be an object.")
            call_id = raw_tool_call.get("id")
            if not isinstance(call_id, str) or not call_id:
                call_id = f"ollama-{uuid.uuid4().hex}-{index}"
            normalized_calls.append(ToolCall(call_id, name, arguments))

        return AssistantResponse(content, normalized_calls)
