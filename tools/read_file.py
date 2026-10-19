import os
from pathlib import Path

from tools.common import resolve_project_path

# Keep the returned file content small enough to use in model context.
MAX_READ_FILE_LINES = 200
# Prevent DoS by refusing to read excessively large files.
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB

# Publish the tool's model-facing schema beside its implementation.
TOOL_SCHEMA = {
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
}


def read_file(file_path: str, project_root: Path) -> str:
    """Read a UTF-8 text file and explicitly mark content that was truncated."""
    try:
        # Validate root containment before accessing any file-system content.
        resolved_file = resolve_project_path(file_path, project_root)

        # Missing paths return a readable result so the model can recover.
        if not resolved_file.exists():
            return f"Error: file not found: {file_path}"

        # Directories and special files are not readable text files.
        if not resolved_file.is_file():
            return f"Error: not a regular file: {file_path}"

        # Check file size on disk before reading to prevent memory exhaustion.
        if resolved_file.stat().st_size > MAX_FILE_SIZE_BYTES:
            return f"Error: file too large ({resolved_file.stat().st_size} bytes). Max limit is {MAX_FILE_SIZE_BYTES} bytes."

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
