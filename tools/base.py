from pathlib import Path

from tools.list_files import TOOL_SCHEMA as LIST_FILES_SCHEMA
from tools.list_files import list_files
from tools.read_file import TOOL_SCHEMA as READ_FILE_SCHEMA
from tools.read_file import read_file
from tools.run_shell import TOOL_SCHEMA as RUN_SHELL_SCHEMA
from tools.run_shell import run_shell
from tools.write_file import TOOL_SCHEMA as WRITE_FILE_SCHEMA
from tools.write_file import write_file

# Register every tool in the order it should be advertised to the model.
TOOL_REGISTRY = {
    "read_file": {
        "schema": READ_FILE_SCHEMA,
        "handler": lambda arguments, project_root: read_file(
            arguments.get("path"), project_root
        ),
    },
    "list_files": {
        "schema": LIST_FILES_SCHEMA,
        "handler": lambda arguments, project_root: list_files(
            arguments.get("path", "."), project_root
        ),
    },
    "write_file": {
        "schema": WRITE_FILE_SCHEMA,
        "handler": lambda arguments, project_root: write_file(
            arguments.get("path"),
            arguments.get("content"),
            project_root,
        ),
    },
    "run_shell": {
        "schema": RUN_SHELL_SCHEMA,
        "handler": lambda arguments, project_root: run_shell(
            arguments.get("command"), project_root
        ),
    },
}

# Export common schema and name lists for provider config and agent setup.
TOOLS = [entry["schema"] for entry in TOOL_REGISTRY.values()]
TOOL_SCHEMAS = {name: entry["schema"] for name, entry in TOOL_REGISTRY.items()}
TOOL_NAMES = tuple(TOOL_REGISTRY)


def get_tools(permissions: dict) -> list[dict]:
    """Return only tool schemas enabled by the configured permissions."""
    # Keep advertised capabilities consistent with the user's configured access.
    return [
        entry["schema"]
        for name, entry in TOOL_REGISTRY.items()
        if permissions.get(name, False)
    ]


def execute_tool(
    tool_name: str,
    arguments: dict,
    project_root: Path,
    permissions: dict,
) -> str:
    """Validate and dispatch one model-requested tool."""
    # Reject names not registered in this module before inspecting arguments.
    entry = TOOL_REGISTRY.get(tool_name)
    if entry is None:
        return f"Error: unknown tool '{tool_name}'."

    # Enforce permission again at execution time, even if a model requests a hidden tool.
    if not permissions.get(tool_name, False):
        return f"Error: permission denied for tool '{tool_name}'."

    # Require a decoded object before tool-specific argument handling.
    if not isinstance(arguments, dict):
        return "Error: tool arguments must be a JSON object."

    # Delegate validation and behavior to the dedicated module for this tool.
    return entry["handler"](arguments, project_root)
