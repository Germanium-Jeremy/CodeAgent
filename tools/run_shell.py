import subprocess
import shlex
from pathlib import Path

# Bound command execution time and output size for predictable tool results.
MAX_SHELL_OUTPUT_CHARACTERS = 1 * 1024 * 1024  # 1 MB
SHELL_TIMEOUT_SECONDS = 120

# Commands that are generally safe to run.
PREFERRED_ALLOWLIST = {"ls", "cat", "python", "pytest", "git", "echo", "mkdir", "pwd"}

# Characters that typically signal injection intent.
INJECTION_CHARACTERS = {";", "|", "&", "`", "$(", "&&", "||", "\n", "\r"}

# Publish this tool schema beside the implementation requiring confirmation.
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_shell",
        "description": (
            "Run a shell command in the project root. The user must approve every "
            "command before it runs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run after user confirmation.",
                }
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
}


def run_shell(command: str, project_root: Path) -> str:
    """Run one confirmed shell command and return bounded output plus its exit code."""
    # Do not execute missing or non-text command arguments.
    if not isinstance(command, str) or not command.strip():
        return "Error: command must be a non-empty string."

    # Reject commands containing characters that signal shell injection.
    for char in INJECTION_CHARACTERS:
        if char in command:
            return f"Error: command contains forbidden character '{char}'. Shell injection is prohibited."

    # Parse the command string into a list for shell=False execution.
    try:
        args = shlex.split(command)
    except ValueError as error:
        return f"Error parsing command: {error}"

    if not args:
        return "Error: no executable command found."

    # Identify the base command to check against the preferred allowlist.
    base_cmd = args[0]
    if base_cmd not in PREFERRED_ALLOWLIST:
        print(f"Warning: '{base_cmd}' is not in the preferred allowlist of safe commands.")

    # Ask for approval on every invocation; there is intentionally no bypass flag.
    print(f"Command: {command}")
    print("Run this command? [y/n]")
    if input().strip().lower() != "y":
        return "Command not run; user declined."

    try:
        # Execute with shell=False to prevent shell injection.
        result = subprocess.run(
            args,
            cwd=project_root,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SHELL_TIMEOUT_SECONDS,
            check=False,
        )
        exit_code = result.returncode
        output = result.stdout or ""
    except subprocess.TimeoutExpired as error:
        # Preserve any captured output and report timeout distinctly from a normal exit.
        exit_code = f"timed out after {SHELL_TIMEOUT_SECONDS} seconds"
        captured_output = error.stdout or ""
        if isinstance(captured_output, bytes):
            output = captured_output.decode("utf-8", errors="replace")
        else:
            output = captured_output
    except OSError as error:
        # Return launch failures explicitly so the model can reason about them.
        return f"Error running command: {error}"

    # Limit output while stating how much was omitted.
    if len(output) > MAX_SHELL_OUTPUT_CHARACTERS:
        omitted_characters = len(output) - MAX_SHELL_OUTPUT_CHARACTERS
        output = (
            output[:MAX_SHELL_OUTPUT_CHARACTERS]
            + f"\n[... truncated, {omitted_characters} characters omitted]"
        )

    # Include command status and combined output in every completed execution result.
    displayed_output = output if output else "(no output)"
    return f"Exit code: {exit_code}\nOutput:\n{displayed_output}"
