from pathlib import Path

# Describe the tool in the format expected by Ollama's chat API.
# The schema teaches the model which arguments it must provide.
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
    }
]

# Keep the allowed tools explicit so model output cannot invoke arbitrary Python.
AVAILABLE_TOOLS = {"read_file"}


def read_file(file_path: str, project_root: Path) -> str:
    """Read one UTF-8 text file without allowing paths outside the project."""
    # Require a string argument because this value comes from model-generated JSON.
    if not isinstance(file_path, str) or not file_path:
        return "Error: the file path must be a non-empty string."

    # Keep the tool interface simple by requiring paths relative to the project.
    requested_path = Path(file_path)
    if requested_path.is_absolute():
        return "Error: use a path relative to the project root."

    try:
        # Resolve symlinks before checking containment to prevent escaping the root.
        resolved_root = project_root.resolve()
        resolved_file = (resolved_root / requested_path).resolve()

        # Python 3.10+ provides is_relative_to for a clear containment check.
        if not resolved_file.is_relative_to(resolved_root):
            return "Error: the requested file is outside the project root."

        # Refuse directories and other non-file paths with a readable tool result.
        if not resolved_file.is_file():
            return f"Error: '{file_path}' is not a file inside the project root."

        # Decode as UTF-8 so binary files fail explicitly instead of producing noise.
        return resolved_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as error:
        # Return expected file-system and decoding failures to the model as tool output.
        return f"Error reading '{file_path}': {error}"


def execute_tool(tool_name: str, arguments: dict, project_root: Path) -> str:
    """Validate and run a tool requested by the model."""
    # Do not let a model invoke names beyond the tools advertised in TOOLS.
    if tool_name not in AVAILABLE_TOOLS:
        return f"Error: unknown tool '{tool_name}'."

    # Check the argument container before indexing model-generated values.
    if not isinstance(arguments, dict):
        return "Error: tool arguments must be a JSON object."

    # Dispatch the one implemented tool using its declared path argument.
    if tool_name == "read_file":
        return read_file(arguments.get("path"), project_root)

    # This branch is defensive: every advertised tool should be handled above.
    return f"Error: tool '{tool_name}' has no implementation."
