import argparse
import json
from pathlib import Path

from config import DEFAULT_CONFIG, load_config
from providers import ProviderError, create_provider
from tools import TOOL_NAMES, execute_tool, get_tools

# Limit a user turn so a model cannot request tools forever.
MAX_AGENT_ITERATIONS = 10

# Give the model instructions for using tools while leaving execution to the loop.
TOOL_SYSTEM_INSTRUCTIONS = (
    "Use list_files to discover project paths before reading unfamiliar files, "
    "when that tool is available. Use read_file when a request depends on file "
    "contents. Use write_file only when the user asks to create or change a file; "
    "overwriting an existing file requires confirmation. Use run_shell only when "
    "needed; every command requires confirmation and may be declined. Never claim "
    "a tool action succeeded unless its result confirms success."
)


def main() -> None:
    """Run the provider-independent interactive agent loop."""
    # Define generic overrides without selecting or importing a particular provider.
    parser = argparse.ArgumentParser(description="Gheremiah CLI Coding Agent")
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Override the configured provider URL for this run",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the configured model for this run",
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default=None,
        help="System instructions for the model (overrides config.json)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root for file tools and shell commands",
    )

    # Parse CLI arguments before resolving configuration defaults.
    args = parser.parse_args()

    # Load provider selection, connection settings, prompt, and permissions.
    config = load_config()
    provider_name = config.get(
        "default_provider", DEFAULT_CONFIG["default_provider"]
    )
    if not isinstance(provider_name, str) or not provider_name:
        parser.error("The default_provider setting in config.json must be a string.")

    # Find the named provider from configuration instead of hard-coding a provider.
    providers = config.get("providers")
    if not isinstance(providers, dict):
        parser.error("The providers setting in config.json must be an object.")
    provider_config = providers.get(provider_name)
    if not isinstance(provider_config, dict):
        parser.error(
            f"Provider '{provider_name}' is not defined in config.json."
        )

    # Use CLI overrides only when explicitly supplied; otherwise the adapter uses config.
    try:
        provider = create_provider(
            provider_name,
            provider_config,
            model_override=args.model,
            base_url_override=args.base_url,
        )
    except ProviderError as error:
        parser.error(str(error))

    # Check configured permissions before exposing tools or accepting tool calls.
    permissions = config.get("permissions", DEFAULT_CONFIG["permissions"])
    if not isinstance(permissions, dict):
        parser.error("The permissions setting in config.json must be an object.")
    tool_names = set(TOOL_NAMES)
    unknown_permissions = set(permissions) - tool_names
    if unknown_permissions:
        parser.error(
            "Unknown tool permissions in config.json: "
            + ", ".join(sorted(unknown_permissions))
        )
    if any(not isinstance(permissions.get(name, False), bool) for name in tool_names):
        parser.error("Every configured tool permission must be true or false.")
    effective_permissions = {
        name: permissions.get(name, False)
        for name in tool_names
    }
    available_tools = get_tools(effective_permissions)

    # Resolve and validate the file/shell working boundary before the session begins.
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        parser.error(f"The project root is not a directory: {project_root}")

    # Use the configured system prompt unless this run explicitly overrides it.
    system_prompt = args.system_prompt
    if system_prompt is None:
        system_prompt = config.get(
            "system_prompt", DEFAULT_CONFIG["system_prompt"]
        )
    if not isinstance(system_prompt, str):
        parser.error("The system_prompt setting in config.json must be a string.")

    # Let the model know exactly which tools configuration permits for this run.
    enabled_tool_names = ", ".join(
        tool["function"]["name"] for tool in available_tools
    ) or "none"
    effective_system_prompt = "\n\n".join(
        instruction
        for instruction in (
            system_prompt.strip(),
            TOOL_SYSTEM_INSTRUCTIONS,
            f"Enabled tools for this session: {enabled_tool_names}.",
        )
        if instruction
    )

    # Keep provider details behind the common name/model interface.
    print(f"Chatting with model: {provider.model} (provider: {provider.name})")
    print(f"File access and shell working directory: {project_root}")
    print("Type '/clear' to clear conversation memory, or '/exit' or '/quit' to end.\n")

    # Store provider-neutral messages for the duration of this CLI process.
    messages = [{"role": "system", "content": effective_system_prompt}]

    # Start an interactive conversation and preserve the phase-3 agent loop.
    while True:
        # Read the next user turn from the terminal.
        user_input = input("\nYour message :> ")

        # End the process on either supported exit command.
        if user_input.lower() in ["/exit", "/quit"]:
            print("\nExiting chat. Goodbye!")
            break

        # Clear remembered turns but retain the active system prompt.
        if user_input.lower() == "/clear":
            messages[:] = [messages[0]]
            print("\nConversation memory cleared.")
            continue

        # Add the user turn before the provider-independent tool loop begins.
        messages.append({"role": "user", "content": user_input})

        # Repeat model calls while normalized responses request tools.
        for iteration in range(MAX_AGENT_ITERATIONS):
            try:
                # The adapter owns transport details and returns one normalized response.
                assistant_response = provider.chat(messages, available_tools)
            except ProviderError as error:
                # Report provider failures without adding them to conversation history.
                print(f"Error communicating with provider '{provider.name}': {error}")
                break

            # Store normalized assistant content and tool calls in shared history.
            history_message = {
                "role": "assistant",
                "content": assistant_response.content,
            }
            if assistant_response.tool_calls:
                history_message["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    }
                    for tool_call in assistant_response.tool_calls
                ]
            messages.append(history_message)

            # A response without tool calls completes this user turn.
            if not assistant_response.tool_calls:
                print(f"\nGheremiah AI :> {assistant_response.content}")
                break

            # Show any assistant text accompanying the requested tool calls.
            if assistant_response.content:
                print(f"\nGheremiah AI :> {assistant_response.content}")

            # Execute normalized calls and feed results back using common message fields.
            for tool_call in assistant_response.tool_calls:
                print(
                    f"[tool] {tool_call.name}"
                    f"({json.dumps(tool_call.arguments, ensure_ascii=False)})"
                )
                tool_result = execute_tool(
                    tool_call.name,
                    tool_call.arguments,
                    project_root,
                    effective_permissions,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": tool_result,
                    }
                )
                print(f"[tool result] {tool_result}")

            # Stop after the configured loop guard rather than running forever.
            if iteration == MAX_AGENT_ITERATIONS - 1:
                print(
                    "\nAgent stopped after reaching the maximum of "
                    f"{MAX_AGENT_ITERATIONS} tool iterations."
                )


# Run the CLI only when this file is executed as the program entry point.
if __name__ == "__main__":
    main()
