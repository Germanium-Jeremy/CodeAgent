import os
import subprocess
from pathlib import Path

# Keep tool output and command runtime bounded so small models can use the results.
MAX_LIST_ENTRIES = 200
MAX_READ_FILE_LINES = 200
MAX_SHELL_OUTPUT_CHARACTERS = 10_000
SHELL_TIMEOUT_SECONDS = 60

# Avoid spending model context on generated files, dependency trees, and VCS metadata.
IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "env",
    "node_modules",
    "target",
    "venv",
}

# Describe available tools in the format expected by Ollama's chat API.
# These schemas tell the model which names and arguments it may request.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file inside the project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to a file relative to the project root.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files", 
            "description": (
                "List project files as a flat path list. Generated and dependency "
                "directories are shown as skipped and are not traversed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Optional project-relative directory to list; defaults to '.'."
                        ),
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write or create UTF-8 text to a file inside the project root. Existing files "
                "require user confirmation before they are overwritten."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to a file relative to the project root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete text content to write to the file.",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
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
    },
]

# Only explicitly registered functions can be dispatched from model output.
AVAILABLE_TOOLS = {"read_file", "list_files", "write_file", "run_shell"}


def _resolve_project_path(file_path: str, project_root: Path) -> Path:
    """Resolve a relative path and reject anything outside the project root."""
    # Model arguments must be non-empty relative paths, never arbitrary absolute paths.
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("the path must be a non-empty string")

    requested_path = Path(file_path)
    if requested_path.is_absolute():
        raise ValueError("use a path relative to the project root")

    # Resolve symlinks before checking containment so they cannot escape the root.
    resolved_root = project_root.resolve()
    resolved_path = (resolved_root / requested_path).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError("the requested path is outside the project root")

    return resolved_path


def read_file(file_path: str, project_root: Path) -> str:
    """Read a UTF-8 text file and explicitly mark content that was truncated."""
    try:
        # Validate root containment before accessing any file-system content.
        resolved_file = _resolve_project_path(file_path, project_root)

        # Missing paths return a readable result so the model can recover.
        if not resolved_file.exists():
            return f"Error: file not found: {file_path}"

        # Directories and special files are not readable text files.
        if not resolved_file.is_file():
            return f"Error: not a regular file: {file_path}"

        # Read text as UTF-8; binary or invalidly encoded content reports an error.
        content = resolved_file.read_text(encoding="utf-8")
    except ValueError as error:
        # Return invalid or out-of-root paths to the model without raising an exception.
        return f"Error: {error}"
    except FileNotFoundError:
        # Handle a path removed between resolution and reading.
        return f"Error: file not found: {file_path}"
    except (OSError, UnicodeError) as error:
        # Surface file-system and decoding failures as tool output.
        return f"Error reading '{file_path}': {error}"

    # Preserve line endings while determining whether the result exceeds our limit.
    lines = content.splitlines(keepends=True)
    if len(lines) <= MAX_READ_FILE_LINES:
        return content

    # Mark truncated output and disclose the original line count for the model.
    truncated_content = "".join(lines[:MAX_READ_FILE_LINES])
    if truncated_content and not truncated_content.endswith(("\n", "\r")):
        truncated_content += "\n"
    return f"{truncated_content}[... truncated, {len(lines)} lines total]"


def list_files(directory_path: str, project_root: Path) -> str:
    """Return a capped, flat path listing and identify ignored directories."""
    try:
        # Resolve and validate the requested directory inside the project root.
        resolved_directory = _resolve_project_path(directory_path, project_root)
        if not resolved_directory.exists():
            return f"Error: directory not found: {directory_path}"
        if not resolved_directory.is_dir():
            return f"Error: not a directory: {directory_path}"

        # Keep the listing relative to the root even when a subdirectory was requested.
        resolved_root = project_root.resolve()
        entries = []

        # Walk top-down so ignored directories can be pruned before descending into them.
        for current_directory, directory_names, file_names in os.walk(
            resolved_directory, topdown=True, followlinks=False
        ):
            current_path = Path(current_directory)

            # Sort traversal for stable, predictable output from one run to the next.
            directory_names.sort()
            file_names.sort()
            visible_directories = []

            # Report ignored folders as flat entries, but never traverse their contents.
            for directory_name in directory_names:
                child_directory = current_path / directory_name
                relative_path = child_directory.relative_to(resolved_root).as_posix()
                if directory_name.lower() in IGNORED_DIRECTORIES:
                    entries.append(f"[skipped directory] {relative_path}/")
                else:
                    entries.append(f"{relative_path}/")
                    visible_directories.append(directory_name)

            # Only include files from directories that os.walk actually visits.
            for file_name in file_names:
                file_path = current_path / file_name
                relative_path = file_path.relative_to(resolved_root).as_posix()
                entries.append(relative_path)

            # Do not follow symlinked directories, even if their names are not ignored.
            directory_names[:] = [
                name
                for name in visible_directories
                if not (current_path / name).is_symlink()
            ]

        # Emit flat paths in a deterministic order without a tree's indentation.
        entries.sort()
    except ValueError as error:
        # Return invalid or out-of-root paths as a tool result.
        return f"Error: {error}"
    except OSError as error:
        # Report listing failures rather than returning an incomplete success result.
        return f"Error listing '{directory_path}': {error}"

    # Make both the listing limit and any omitted entries clear to the model.
    visible_entries = entries[:MAX_LIST_ENTRIES]
    output_lines = [f"Project paths (flat list, up to {MAX_LIST_ENTRIES} entries):"]
    output_lines.extend(visible_entries)
    if len(entries) > MAX_LIST_ENTRIES:
        output_lines.append(f"... and {len(entries) - MAX_LIST_ENTRIES} more")
    if not entries:
        output_lines.append("(no files or directories found)")

    return "\n".join(output_lines)


def write_file(file_path: str, content: str, project_root: Path) -> str:
    """Write text under the project root, confirming before replacing a file."""
    # Validate both model-supplied values before touching the file system.
    if not isinstance(content, str):
        return "Error: file content must be a string."

    try:
        # Resolve the path first so writes through symlinks stay inside the root.
        resolved_file = _resolve_project_path(file_path, project_root)

        # Existing files always require the user's explicit approval to overwrite.
        if resolved_file.exists():
            if not resolved_file.is_file():
                return f"Error: not a regular file: {file_path}"
            print(f"Overwrite existing file '{file_path}'? [y/n]")
            if input().strip().lower() != "y":
                return f"Write cancelled; existing file was not changed: {file_path}"

        # Create parent folders for new files, then write UTF-8 text.
        resolved_file.parent.mkdir(parents=True, exist_ok=True)
        resolved_file.write_text(content, encoding="utf-8")
    except ValueError as error:
        # Return invalid or out-of-root paths as a tool result.
        return f"Error: {error}"
    except OSError as error:
        # Surface write failures; do not report success-shaped fallback results.
        return f"Error writing '{file_path}': {error}"

    # Report a concise confirmation rather than copying file content into context.
    line_count = len(content.splitlines())
    return f"Wrote {line_count} lines to {file_path}"


def run_shell(command: str, project_root: Path) -> str:
    """Run one confirmed shell command and return bounded output plus its exit code."""
    # Do not execute missing or non-text command arguments.
    if not isinstance(command, str) or not command.strip():
        return "Error: command must be a non-empty string."

    # Ask for approval on every invocation; there is intentionally no bypass flag.
    print(f"Command: {command}")
    print("Run this command? [y/n]")
    if input().strip().lower() != "y":
        return "Command not run; user declined."

    try:
        # Combine stderr with stdout, enforce a timeout, and keep this in the project.
        result = subprocess.run(
            command,
            cwd=project_root,
            shell=True,
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


def execute_tool(tool_name: str, arguments: dict, project_root: Path) -> str:
    """Validate and run a tool requested by the model."""
    # Refuse any function name not explicitly advertised to the model.
    if tool_name not in AVAILABLE_TOOLS:
        return f"Error: unknown tool '{tool_name}'."

    # Model arguments must be decoded into an object before dispatch.
    if not isinstance(arguments, dict):
        return "Error: tool arguments must be a JSON object."

    # Dispatch each known tool with its declared arguments and project boundary.
    if tool_name == "read_file":
        return read_file(arguments.get("path"), project_root)
    if tool_name == "list_files":
        return list_files(arguments.get("path", "."), project_root)
    if tool_name == "write_file":
        return write_file(
            arguments.get("path"),
            arguments.get("content"),
            project_root,
        )
    if tool_name == "run_shell":
        return run_shell(arguments.get("command"), project_root)

    # This branch is defensive: every advertised tool should be handled above.
    return f"Error: tool '{tool_name}' has no implementation."
