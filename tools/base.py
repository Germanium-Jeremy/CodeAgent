from pathlib import Path

from tools.common import resolve_project_path
from tools.edit_file import TOOL_SCHEMA as EDIT_FILE_SCHEMA
from tools.edit_file import edit_file
from tools.list_files import TOOL_SCHEMA as LIST_FILES_SCHEMA
from tools.list_files import list_files
from tools.plan import TOOL_SCHEMA as PLAN_SCHEMA
from tools.plan import plan
from tools.read_file import TOOL_SCHEMA as READ_FILE_SCHEMA
from tools.read_file import read_file
from tools.read_files import TOOL_SCHEMA as READ_FILES_SCHEMA
from tools.read_files import read_files
from tools.run_shell import TOOL_SCHEMA as RUN_SHELL_SCHEMA
from tools.run_shell import run_shell
from tools.test import TOOL_SCHEMA as TEST_SCHEMA
from tools.test import run_test
from tools.tools_mgmt import TOOL_SCHEMA as TOOLS_MGMT_SCHEMA
from tools.tools_mgmt import tools_mgmt
from tools.write_file import TOOL_SCHEMA as WRITE_FILE_SCHEMA
from tools.write_file import write_file
from tools.write_files import TOOL_SCHEMA as WRITE_FILES_SCHEMA
from tools.write_files import write_files

# Register every tool in the order it should be advertised to the model.
TOOL_REGISTRY = {
    "read_file": {
        "schema": READ_FILE_SCHEMA,
        "handler": lambda arguments, project_root: read_file(
            arguments.get("path"),
            project_root,
            start_line=arguments.get("start_line"),
            end_line=arguments.get("end_line"),
        ),
    },
    "list_files": {
        "schema": LIST_FILES_SCHEMA,
        "handler": lambda arguments, project_root: list_files(
            arguments.get("path", "."), project_root
        ),
    },
    "read_files": {
        "schema": READ_FILES_SCHEMA,
        "handler": lambda arguments, project_root: read_files(
            arguments.get("paths"),
            project_root,
            start_line=arguments.get("start_line"),
            end_line=arguments.get("end_line"),
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
    "write_files": {
        "schema": WRITE_FILES_SCHEMA,
        "handler": lambda arguments, project_root: write_files(
            arguments.get("files"),
            project_root,
            allow_overwrite=arguments.get("allow_overwrite", False),
        ),
    },
    "run_shell": {
        "schema": RUN_SHELL_SCHEMA,
        "handler": lambda arguments, project_root: run_shell(
            arguments.get("command"), project_root
        ),
    },
    "edit_file": {
        "schema": EDIT_FILE_SCHEMA,
        "handler": lambda arguments, project_root: edit_file(
            arguments.get("path"),
            arguments.get("start_line"),
            arguments.get("end_line"),
            arguments.get("new_content"),
            project_root,
        ),
    },
    "plan": {
        "schema": PLAN_SCHEMA,
        "handler": lambda arguments, project_root: plan(
            arguments.get("title"),
            arguments.get("phases"),
            project_root,
        ),
    },
    "tools_mgmt": {
        "schema": TOOLS_MGMT_SCHEMA,
        "handler": lambda arguments, project_root: tools_mgmt(
            arguments.get("action"),
            arguments.get("mode"),
            project_root,
        ),
    },
    "test": {
        "schema": TEST_SCHEMA,
        "handler": lambda arguments, project_root: run_test(
            arguments.get("command"),
            arguments.get("target"),
            arguments.get("timeout"),
            project_root,
        ),
    },
}


# These tools are low-shot, data-only, and cheap; they are always usable so the
# agent can maintain project state without begging the user for a permission toggle.
ALWAYS_ENABLED = {
    "plan",
    "tools_mgmt",
    "read_files",
    "read_file",
    "list_files",
}

# Export common schema and name lists for provider config and agent setup.
TOOLS = [entry["schema"] for entry in TOOL_REGISTRY.values()]
TOOL_SCHEMAS = {name: entry["schema"] for name, entry in TOOL_REGISTRY.items()}
TOOL_NAMES = tuple(TOOL_REGISTRY)
__all__ = ["TOOL_NAMES", "TOOLS", "TOOL_REGISTRY", "ALWAYS_ENABLED", "execute_tool", "get_tools"]


def get_tools(permissions: dict) -> list[dict]:
    """Return only tool schemas enabled by the configured permissions."""
    # Always-on tools are not gated by the user permission table.
    if permissions.get("__force_tool_names__"):
        return [entry["schema"] for entry in TOOL_REGISTRY.values()]

    filtered = {
        name
        for name, entry in TOOL_REGISTRY.items()
        if name in ALWAYS_ENABLED or permissions.get(name, False)
    }

    # Reproduce the tool-call advertisement order expected by permission-aware clients.
    return [entry["schema"] for name, entry in TOOL_REGISTRY.items() if name in filtered]


def execute_tool(
    tool_name: str,
    arguments: dict,
    project_root: Path,
    permissions: dict,
    dry_run: bool = False,
) -> str:
    """Validate and dispatch one model-requested tool."""
    # Reject names not registered in this module before inspecting arguments.
    entry = TOOL_REGISTRY.get(tool_name)
    if entry is None:
        return f"Error: unknown tool '{tool_name}'."

    # Always-on tools (plan, tools_mgmt, read tools) cannot be disabled after startup.
    if tool_name not in ALWAYS_ENABLED and not permissions.get(tool_name, False):
        return f"Error: permission denied for tool '{tool_name}'."

    # Require a decoded object before tool-specific argument handling.
    if not isinstance(arguments, dict):
        return "Error: tool arguments must be a JSON object."

    # Intercept mutating tools if dry_run is enabled to prevent actual side effects.
    # We allow read-only tools (read_file, list_files) to run normally so the agent can still see project state.
    if dry_run and tool_name in ("write_file", "write_files", "run_shell"):
        return f"[DRY RUN] Would have executed {tool_name} with arguments: {arguments}"

    # Delegate validation and behavior to the dedicated module for this tool.
    return entry["handler"](arguments, project_root)
