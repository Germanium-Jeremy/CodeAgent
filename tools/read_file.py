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
        "description": "Read a UTF-8 text file inside the project root. Supports reading specific line ranges.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to a file relative to the project root.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "The line number to start reading from (1-indexed).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "The line number to stop reading at (inclusive, 1-indexed).",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}


def read_file(file_path: str, project_root: Path, start_line: int = None, end_line: int = None) -> str:
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

    # Split content into lines to handle range-based reading and line numbering.
    lines = content.splitlines()
    total_lines = len(lines)

    # Determine the range of lines to return.
    # If no start_line is given, we start at 1.
    start_idx = max(0, (start_line or 1) - 1)

    # If no end_line is given, we read up to MAX_READ_FILE_LINES from the start_idx.
    if end_line:
        end_idx = min(total_lines, end_line)
    else:
        end_idx = min(total_lines, start_idx + MAX_READ_FILE_LINES)

    # Slice the lines and add line numbers for the model's reference.
    selected_lines = lines[start_idx:end_idx]
    formatted_lines = [
        f"{i + 1}: {text}" for i, text in enumerate(selected_lines, start=start_idx + 1)
    ]

    result_text = "\n".join(formatted_lines)

    # Provide metadata about the range and the total file size.
    range_info = f"Lines {start_idx + 1}-{end_idx} of {total_lines}"

    # Mark as truncated if we hit the max limit or if there are more lines after the end_idx.
    if end_idx < total_lines:
        return f"{result_text}\n\n[... truncated, {total_lines} lines total. {range_info}]"

    return f"{result_text}\n\n[{range_info}]"
