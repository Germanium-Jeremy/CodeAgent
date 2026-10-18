from typing import Any

from providers.base import BaseProvider, ProviderError
from providers.ollama import OllamaProvider
from providers.openai import OpenAICompatibleProvider


def create_provider(
    name: str,
    provider_config: dict[str, Any],
    model_override: str | None = None,
    base_url_override: str | None = None,
) -> BaseProvider:
    """Create the configured adapter while keeping provider imports out of the CLI."""
    # Resolve common settings once and pass the selected values to the adapter.
    provider_type = provider_config.get("type")
    base_url = (
        base_url_override
        if base_url_override is not None
        else provider_config.get("base_url")
    )
    model = (
        model_override
        if model_override is not None
        else provider_config.get("model")
    )
    if not isinstance(base_url, str) or not base_url:
        raise ProviderError(f"Provider '{name}' must define a non-empty base_url.")
    if not isinstance(model, str) or not model:
        raise ProviderError(f"Provider '{name}' must define a non-empty model.")

    # Select the adapter from config data, not a provider branch in the agent loop.
    if provider_type == "ollama":
        return OllamaProvider(name, base_url, model)
    if provider_type == "openai_compatible":
        api_key_env = provider_config.get("api_key_env")
        if api_key_env is not None and not isinstance(api_key_env, str):
            raise ProviderError(
                f"Provider '{name}' api_key_env must be a string or null."
            )
        if api_key_env == "":
            raise ProviderError(
                f"Provider '{name}' api_key_env cannot be an empty string."
            )
        return OpenAICompatibleProvider(name, base_url, model, api_key_env)

    raise ProviderError(
        f"Provider '{name}' has unsupported type {provider_type!r}."
    )


__all__ = ["BaseProvider", "ProviderError", "create_provider"]
