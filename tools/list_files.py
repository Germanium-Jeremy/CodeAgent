import os
from pathlib import Path

from tools.common import resolve_project_path

# Bound directory discovery and avoid common generated/dependency directories.
MAX_LIST_ENTRIES = 200
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

# Publish this tool's schema next to its implementation.
TOOL_SCHEMA = {
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
}


def list_files(directory_path: str, project_root: Path) -> str:
    """Return a capped, flat path listing and identify ignored directories."""
    try:
        # Resolve and validate the requested directory inside the project root.
        resolved_directory = resolve_project_path(directory_path, project_root)
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
