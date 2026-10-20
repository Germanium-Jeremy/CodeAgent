from pathlib import Path
from typing import List, Dict, Any

from tools.common import resolve_project_path

def read_files(paths: List[str], project_root: Path, start_line: int = None, end_line: int = None) -> str:
    """
    Reads multiple files and returns their contents concatenated with delimiters.
    """
    if not paths or not isinstance(paths, list):
        return "Error: 'paths' must be a non-empty list of file paths."

    results = []
    for path_str in paths:
        full_path = resolve_project_path(path_str, project_root)
        if not full_path.exists() or not full_path.is_file():
            results.append(f"File not found: {path_str}")
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

                if start_line is not None:
                    lines = lines[max(0, start_line - 1):]
                if end_line is not None:
                    lines = lines[:end_line]

                content = "".join(lines)
                results.append(f"--- File: {path_str} ---\n{content}\n--- End of File ---")
        except Exception as e:
            results.append(f"Error reading {path_str}: {str(e)}")

    return "\n\n".join(results)

TOOL_SCHEMA = {
    "name": "read_files",
    "description": "Read multiple files in one turn to get a broader context of the project.",
    "parameters": {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of paths to read."
            },
            "start_line": {
                "type": "integer",
                "description": "Optional start line for all files."
            },
            "end_line": {
                "type": "integer",
                "description": "Optional end line for all files."
            }
        },
        "required": ["paths"]
    }
}
