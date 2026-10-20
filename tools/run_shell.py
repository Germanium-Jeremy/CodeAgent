import subprocess
import shlex
import time
import json
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
    """Run one confirmed shell command and return a structured summary of the result."""
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

    start_time = time.time()
    try:
        # Execute with shell=False to prevent shell injection.
        result = subprocess.run(
            args,
            cwd=project_root,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SHELL_TIMEOUT_SECONDS,
            check=False,
        )
        duration = time.time() - start_time
        exit_code = result.returncode
        stdout = result.stdout or ""
        stderr = result.stderr or ""
    except subprocess.TimeoutExpired as error:
        duration = time.time() - start_time
        exit_code = -1
        stdout = error.stdout.decode("utf-8", errors="replace") if error.stdout else ""
        stderr = error.stderr.decode("utf-8", errors="replace") if error.stderr else "Timed out"
    except OSError as error:
        return f"Error running command: {error}"

    # Tail the output
    def get_tail(text, lines_count=20):
        if not text: return "(no output)"
        ls = text.splitlines()
        return "\n".join(ls[-lines_count:]) if len(ls) > lines_count else text

    summary = {
        "exit_code": exit_code,
        "duration": f"{duration:.2f}s",
        "stdout_tail": get_tail(stdout),
        "stderr_tail": get_tail(stderr)
    }

    return json.dumps(summary, indent=2)
