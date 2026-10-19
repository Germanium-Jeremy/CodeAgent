import json
import os
import uuid
from typing import Any

import requests

from providers.base import AssistantResponse, BaseProvider, ProviderError, ToolCall


class OpenAICompatibleProvider(BaseProvider):
    """Adapt the common agent interface to OpenAI-compatible chat completions."""

    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key_env: str | None = None,
    ) -> None:
        # Keep endpoint and authentication details inside this adapter.
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key_env = api_key_env

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        """Return a reasonable default context window for OpenAI-compatible providers."""
        # Many OpenAI-compatible providers use large windows; default to 16384 for safety.
        return 16384

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AssistantResponse:
        # Convert the normalized conversation into OpenAI's tool-call format.
        openai_messages = []
        for message in messages:
            converted = {
                "role": message["role"],
                "content": message.get("content", ""),
            }
            if message["role"] == "assistant" and message.get("tool_calls"):
                converted["tool_calls"] = [
                    {
                        "id": tool_call["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call["name"],
                            "arguments": json.dumps(tool_call["arguments"]),
                        },
                    }
                    for tool_call in message["tool_calls"]
                ]
            elif message["role"] == "tool":
                converted["tool_call_id"] = message["tool_call_id"]
            openai_messages.append(converted)

        # Add authentication only when the selected endpoint uses an API-key env var.
        headers = {"Content-Type": "application/json"}
        if self._api_key_env:
            api_key = os.environ.get(self._api_key_env)
            if not api_key:
                raise ProviderError(
                    f"API key environment variable '{self._api_key_env}' is not set."
                )
            headers["Authorization"] = f"Bearer {api_key}"

        # Send OpenAI-specific request details only from this adapter.
        try:
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self._model,
                    "messages": openai_messages,
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
                f"OpenAI-compatible request failed: {error}"
                + (f"\nResponse: {response_text}" if response_text else "")
            ) from error
        except ValueError as error:
            # Requests uses ValueError for malformed JSON response bodies.
            raise ProviderError(
                f"OpenAI-compatible provider returned invalid JSON: {error}"
            ) from error

        # Normalize OpenAI's choices and tool calls at the adapter boundary.
        if not isinstance(data, dict):
            raise ProviderError("OpenAI-compatible response must be an object.")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("OpenAI-compatible response must contain choices.")
        choice = choices[0]
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            raise ProviderError("OpenAI-compatible response must contain a message.")
        message = choice["message"]
        content = message.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise ProviderError("OpenAI-compatible message content must be text.")

        raw_tool_calls = message.get("tool_calls", [])
        if not isinstance(raw_tool_calls, list):
            raise ProviderError("OpenAI-compatible tool_calls must be a list.")

        normalized_calls = []
        for index, raw_tool_call in enumerate(raw_tool_calls):
            if not isinstance(raw_tool_call, dict):
                raise ProviderError("OpenAI-compatible tool call must be an object.")
            function = raw_tool_call.get("function")
            if not isinstance(function, dict):
                raise ProviderError("OpenAI-compatible tool call is missing its function.")
            name = function.get("name")
            raw_arguments = function.get("arguments", "{}")
            if not isinstance(name, str):
                raise ProviderError("OpenAI-compatible tool call name must be text.")
            if isinstance(raw_arguments, str):
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError as error:
                    raise ProviderError(
                        f"OpenAI-compatible tool arguments are invalid JSON: {error}"
                    ) from error
            else:
                arguments = raw_arguments
            if not isinstance(arguments, dict):
                raise ProviderError(
                    "OpenAI-compatible tool call arguments must be an object."
                )
            call_id = raw_tool_call.get("id")
            if not isinstance(call_id, str) or not call_id:
                call_id = f"openai-{uuid.uuid4().hex}-{index}"
            normalized_calls.append(ToolCall(call_id, name, arguments))

        return AssistantResponse(content, normalized_calls)
