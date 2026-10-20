from pathlib import Path
from typing import List, Dict, Any

from tools.common import resolve_project_path

def write_files(files: List[Dict[str, str]], project_root: Path, allow_overwrite: bool = False) -> str:
    """
    Writes multiple files in one turn.
    """
    if not files or not isinstance(files, list):
        return "Error: 'files' must be a non-empty list of file objects."

    written = []
    errors = []

    for file_data in files:
        path_str = file_data.get("path")
        content = file_data.get("content")

        if not path_str or content is None:
            errors.append(f"Invalid file data: {file_data}")
            continue

        full_path = resolve_project_path(path_str, project_root)

        if full_path.exists() and not allow_overwrite:
            errors.append(f"File already exists and allow_overwrite is False: {path_str}")
            continue

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            written.append(path_str)
        except Exception as e:
            errors.append(f"Error writing {path_str}: {str(e)}")

    result = f"Successfully wrote {len(written)} files: {', '.join(written)}" if written else "No files were written."
    if errors:
        result += "\n\nErrors:\n" + "\n".join(errors)

    return result

TOOL_SCHEMA = {
    "name": "write_files",
    "description": "Create or overwrite multiple files in one turn. Useful for scaffolding projects.",
    "parameters": {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                },
                "description": "List of files to write, each with a path and content."
            },
            "allow_overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite existing files. Defaults to False."
            }
        },
        "required": ["files"]
    }
}
