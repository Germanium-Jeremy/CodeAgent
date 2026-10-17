import os
from pathlib import Path

from tools.common import resolve_project_path

# Prevent DoS by refusing to write excessively large files.
MAX_WRITE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB

# Publish the edit tool schema next to the implementation.
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Replace a specific range of lines in a UTF-8 text file inside the project root. "
            "This is used for targeted edits without overwriting the entire file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to a file relative to the project root.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "The first line number to be replaced (1-indexed).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "The last line number to be replaced (inclusive, 1-indexed).",
                },
                "new_content": {
                    "type": "string",
                    "description": "The replacement text to insert in the specified range.",
                },
            },
            "required": ["path", "start_line", "end_line", "new_content"],
            "additionalProperties": False,
        },
    },
}


def edit_file(file_path: str, start_line: int, end_line: int, new_content: str, project_root: Path) -> str:
    """Replace a range of lines in a file, ensuring the path is within the project root."""
    try:
        # Validate root containment before accessing any file-system content.
        resolved_file = resolve_project_path(file_path, project_root)

        if not resolved_file.exists():
            return f"Error: file not found: {file_path}"
        if not resolved_file.is_file():
            return f"Error: not a regular file: {file_path}"

        # Read existing content.
        content = resolved_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Validation of line ranges.
        if start_line < 1 or start_line > len(lines) + 1:
            return f"Error: start_line {start_line} is out of range (1-{len(lines)+1})."
        if end_line < start_line:
            return f"Error: end_line {end_line} cannot be less than start_line {start_line}."

        # Clamp end_line to file length.
        actual_end_line = min(end_line, len(lines))

        # Split new_content into lines to integrate into the list.
        replacement_lines = new_content.splitlines()

        # Replace the specified slice.
        # Slice is [start-1 : end] because list is 0-indexed and end_line is inclusive.
        lines[start_line - 1 : actual_end_line] = replacement_lines

        # Reconstruct file content.
        new_full_content = "\n".join(lines)

        # Enforce size limit on the resulting file.
        if len(new_full_content.encode("utf-8")) > MAX_WRITE_SIZE_BYTES:
            return f"Error: resulting file too large. Max limit is {MAX_WRITE_SIZE_BYTES} bytes."

        # Write the updated content back to disk.
        resolved_file.write_text(new_full_content, encoding="utf-8")

        # Report the change: lines removed and lines added.
        lines_removed = actual_end_line - (start_line - 1)
        lines_added = len(replacement_lines)
        return f"Successfully edited {file_path}. Removed {lines_removed} lines, added {lines_added} lines."

    except ValueError as error:
        return f"Error: {error}"
    except (OSError, UnicodeError) as error:
        return f"Error editing '{file_path}': {error}"
