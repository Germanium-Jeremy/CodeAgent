import os
import subprocess
from pathlib import Path
from typing import Optional

from config import DEFAULT_CONFIG
from tools.common import resolve_project_path

def tools_mgmt(action: str, mode: Optional[str], project_root: Path) -> str:
    """
    Initializes project scaffolds and manages generated files using templates from config.py.
    """
    if action != "init_project":
        return f"Error: Action '{action}' is not supported by tools_mgmt. Currently only 'init_project' is available."

    # The 'mode' here is used as the template name (e.g., 'react', 'fastapi')
    template_name = mode
    if not template_name:
        return "Error: 'mode' (template name) must be provided for 'init_project' action."

    config = DEFAULT_CONFIG # In a real app, this would be the loaded config
    templates = config.get("project_templates", {})

    template = templates.get(template_name)
    if not template:
        available = ", ".join(templates.keys())
        return f"Error: Template '{template_name}' not found. Available templates: {available}"

    init_cmd = template.get("init")
    deps_cmd = template.get("deps")

    if not init_cmd:
        return f"Error: No initialization command defined for template '{template_name}'."

    try:
        # Execute initialization
        # Note: We use shell=True because template commands often involve pipes or multiple commands
        subprocess.run(init_cmd, shell=True, cwd=project_root, check=True, capture_output=True, text=True)

        result = f"Successfully initialized {template_name} project at {project_root}."

        if deps_cmd:
            result += f"\n\nTo install dependencies, you can run: {deps_cmd}"

        return result
    except subprocess.CalledProcessError as e:
        return f"Error during initialization: {e.stderr or e.stdout}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

TOOL_SCHEMA = {
    "name": "tools_mgmt",
    "description": "Initialize project scaffolds (React, Next, FastAPI, etc.) using predefined templates.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["init_project"],
                "description": "The action to perform."
            },
            "mode": {
                "type": "string",
                "description": "The template name to use (e.g., 'react', 'fastapi', 'next')."
            }
        },
        "required": ["action", "mode"]
    }
}
