import argparse
import json
import os
from pathlib import Path

# Import Rich components for professional TUI output
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.live import Live
from rich.table import Table

from config import DEFAULT_CONFIG, load_config
from providers import ProviderError, create_provider
from tools import TOOL_NAMES, execute_tool, get_tools

# Limit a user turn so a model cannot request tools forever.
MAX_AGENT_ITERATIONS = 10

# Context Window Configuration (tokens)
MAX_OUTPUT_TOKENS = 2048
HEADROOM_TOKENS = 1500

# Initialize the Rich console for all terminal output.
console = Console()

# Give the model instructions for using tools while leaving execution to the loop.
TOOL_SYSTEM_INSTRUCTIONS = (
    "Use list_files to discover project paths before reading unfamiliar files, "
    "when that tool is available. Use read_file when a request depends on file "
    "contents. Use write_file only when the user asks to create or change a file; "
    "overwriting an existing file requires confirmation. Use run_shell only when "
    "needed; every command requires confirmation and may be declined. Never claim "
    "a tool action succeeded unless its result confirms success."
)


def estimate_tokens(text: str) -> int:
    """Roughly estimate tokens based on 1 token ~= 4 characters."""
    return len(text) // 4


def save_full_history(messages: list, project_root: Path) -> None:
    """Persist full conversation history to disk before any trimming occurs."""
    history_path = project_root / ".gheremiah_history.json"
    try:
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
    except OSError as error:
        console.print(f"[bold red]Warning:[/bold red] could not save history to disk: {error}")


def trim_context(messages: list, budget: int) -> list:
    """Apply sliding window trimming to stay within the token budget."""
    # Always keep the system prompt (index 0).
    system_prompt = messages[0]
    history = messages[1:]

    # Calculate current usage.
    current_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)

    if current_tokens <= budget:
        return messages

    # Trim oldest turns (user + assistant + optional tool results).
    while len(history) > 1 and sum(estimate_tokens(m.get("content", "")) for m in [system_prompt] + history) > budget:
        if history[0]["role"] == "user":
            try:
                next_user_idx = next(i for i, m in enumerate(history) if i > 0 and m["role"] == "user")
                history = history[next_user_idx:]
            except StopIteration:
                break
        else:
            history.pop(0)

    return [system_prompt] + history


def sanitize_tool_output(content: str) -> str:
    """Mitigate prompt injection by wrapping data and stripping common attack patterns."""
    if not content:
        return content

    sanitized = content.replace("ignore previous instructions", "[REDACTED]")
    sanitized = sanitized.replace("ignore all previous instructions", "[REDACTED]")

    return f"<untrusted-data>\n{sanitized}\n</untrusted-data>"


def main() -> None:
    """Run the provider-independent interactive agent loop with a polished Rich UI and streaming."""

    # Define CLI arguments including new provider and dry-run flags.
    parser = argparse.ArgumentParser(
        description="Gheremiah: A provider-agnostic CLI coding agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
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
        "--provider",
        type=str,
        default=None,
        help="Override the default provider from config.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate tool execution without making changes to the filesystem or shell",
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

    args = parser.parse_args()

    # Load configuration and resolve which provider to use.
    config = load_config()

    # Use CLI flag if provided, otherwise fallback to config, then to DEFAULT_CONFIG.
    provider_name = args.provider or config.get(
        "default_provider", DEFAULT_CONFIG["default_provider"]
    )

    if not isinstance(provider_name, str) or not provider_name:
        parser.error("The default_provider setting must be a valid string.")

    providers = config.get("providers")
    if not isinstance(providers, dict):
        parser.error("The providers setting in config.json must be an object.")

    provider_config = providers.get(provider_name)
    if not isinstance(provider_config, dict):
        parser.error(f"Provider '{provider_name}' is not defined in config.json.")

    try:
        provider = create_provider(
            provider_name,
            provider_config,
            model_override=args.model,
            base_url_override=args.base_url,
        )
    except ProviderError as error:
        parser.error(str(error))

    # Resolve tool permissions.
    permissions = config.get("permissions", DEFAULT_CONFIG["permissions"])
    if not isinstance(permissions, dict):
        parser.error("The permissions setting in config.json must be an object.")

    tool_names = set(TOOL_NAMES)
    unknown_permissions = set(permissions) - tool_names
    if unknown_permissions:
        parser.error("Unknown tool permissions in config.json: " + ", ".join(sorted(unknown_permissions)))

    effective_permissions = {name: permissions.get(name, False) for name in tool_names}
    available_tools = get_tools(effective_permissions)

    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        parser.error(f"The project root is not a directory: {project_root}")

    system_prompt = args.system_prompt or config.get("system_prompt", DEFAULT_CONFIG["system_prompt"])
    if not isinstance(system_prompt, str):
        parser.error("The system_prompt setting in config.json must be a string.")

    # Construct the final system prompt.
    enabled_tool_names = ", ".join(tool["function"]["name"] for tool in available_tools) or "none"
    effective_system_prompt = "\n\n".join(
        instruction for instruction in (
            system_prompt.strip(),
            TOOL_SYSTEM_INSTRUCTIONS,
            f"Enabled tools for this session: {enabled_tool_names}.",
        ) if instruction
    )

    # Display a professional welcome header using a Rich Panel.
    console.print(Panel(
        f"[bold cyan]Gheremiah AI Agent[/bold cyan]\n"
        f"[dim]Model: {provider.model} | Provider: {provider.name}[/dim]\n"
        f"[dim]Root: {project_root}[/dim]",
        expand=False,
        border_style="cyan"
    ))
    console.print("[dim]Type '/clear' to reset memory, or '/exit' to quit.[/dim]\n")

    messages = [{"role": "system", "content": effective_system_prompt}]
    window_size = provider.context_window
    context_budget = window_size - MAX_OUTPUT_TOKENS - HEADROOM_TOKENS

    while True:
        # Styled user input prompt.
        user_input = Prompt.ask("\n[bold magenta]Your message :>[/bold magenta]")

        if user_input.lower() in ["/exit", "/quit"]:
            console.print("\n[bold cyan]Exiting chat. Goodbye![/bold cyan]")
            break

        if user_input.lower() == "/clear":
            messages[:] = [messages[0]]
            console.print("\n[yellow]Conversation memory cleared.[/yellow]")
            continue

        messages.append({"role": "user", "content": user_input})

        for iteration in range(MAX_AGENT_ITERATIONS):
            # Calculate context usage.
            current_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
            usage_pct = (current_tokens / window_size) * 100

            # Context status line: printed as a single line to reduce clutter.
            usage_color = "red" if usage_pct >= 80 else "green"
            console.print(f" [bold {usage_color}]Context: {current_tokens}/{window_size} ({usage_pct:.1f}%)[/bold {usage_color}]", end="\r")

            if usage_pct >= 80:
                messages.append({"role": "system", "content": "System Note: Context is filling up. Please wrap up your current task."})

            if current_tokens > context_budget:
                save_full_history(messages, project_root)
                messages = trim_context(messages, context_budget)
                console.print(f"\n[bold red]System:[/bold red] Context budget exceeded; trimmed oldest turns. Full history saved to .gheremiah_history.json")

            try:
                # --- STREAMING IMPLEMENTATION ---
                # We now use the stream_chat interface to provide real-time feedback.
                full_content = ""
                collected_tool_calls = []

                console.print("\n[bold cyan]Gheremiah AI :>[/bold cyan]")

                # Iterate over the generator yielded by the provider.
                for chunk in provider.stream_chat(messages, available_tools):
                    if chunk.text:
                        # Print token immediately to the console without a newline.
                        console.print(chunk.text, end="")
                        full_content += chunk.text
                    if chunk.tool_call:
                        # Collect tool calls to execute after the stream completes.
                        collected_tool_calls.append(chunk.tool_call)

                # Add a newline after the stream is finished.
                console.print()

            except ProviderError as error:
                console.print(f"\n[bold red]Error communicating with provider '{provider.name}': {error}[/bold red]")
                break

            # Store the full accumulated response in the history for subsequent turns.
            history_message = {"role": "assistant", "content": full_content}
            if collected_tool_calls:
                history_message["tool_calls"] = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in collected_tool_calls
                ]
            messages.append(history_message)

            # If no tools were called, the turn is complete.
            if not collected_tool_calls:
                # Optional: Re-render the accumulated content as Markdown for better formatting
                # if the model provided significant structure.
                if full_content:
                    # To avoid double-printing, we could have printed plain text during streaming
                    # and then a "final" rendered version, but for simplicity and speed,
                    # we've already streamed it. If we wanted high-quality markdown, we could
                    # use a Live display to replace the plain text with a Markdown object.
                    pass
                break

            # Execute collected tool calls with visual feedback.
            for tool_call in collected_tool_calls:
                # Highlight tool calls in yellow.
                console.print(f"\n[bold yellow]⚙ Tool Call: {tool_call.name}[/bold yellow]")
                console.print(f"[dim]{json.dumps(tool_call.arguments, ensure_ascii=False)}[/dim]")

                # Pass the dry_run flag to the execution engine.
                tool_result = execute_tool(
                    tool_call.name,
                    tool_call.arguments,
                    project_root,
                    effective_permissions,
                    dry_run=args.dry_run
                )

                safe_result = sanitize_tool_output(tool_result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": safe_result,
                })

                # Render tool results in a dim panel.
                console.print(Panel(
                    Markdown(tool_result),
                    title="[dim]Tool Result[/dim]",
                    border_style="dim",
                    expand=False
                ))

            if iteration == MAX_AGENT_ITERATIONS - 1:
                console.print(f"\n[bold red]Agent stopped after reaching the maximum of {MAX_AGENT_ITERATIONS} tool iterations.[/bold red]")

if __name__ == "__main__":
    main()
