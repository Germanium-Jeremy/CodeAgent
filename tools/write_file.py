from pathlib import Path

from tools.common import resolve_project_path

# Prevent DoS by refusing to write excessively large files.
MAX_WRITE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB

# Publish the write tool schema next to the implementation that enforces its rules.
TOOL_SCHEMA = {
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
}


def write_file(file_path: str, content: str, project_root: Path) -> str:
    """Write text under the project root, confirming before replacing a file."""
    # Validate both model-supplied values before touching the file system.
    if not isinstance(content, str):
        return "Error: file content must be a string."

    # Enforce a size limit on the content to prevent disk space exhaustion.
    if len(content.encode("utf-8")) > MAX_WRITE_SIZE_BYTES:
        return f"Error: content too large. Max limit is {MAX_WRITE_SIZE_BYTES} bytes."

    try:
        # Resolve the path first so writes through symlinks stay inside the root.
        resolved_file = resolve_project_path(file_path, project_root)

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
