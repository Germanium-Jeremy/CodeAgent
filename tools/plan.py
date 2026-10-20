import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

def get_state_dir() -> Path:
    """Returns the global state directory for Gheremiah."""
    return Path(os.path.expanduser("~")).joinpath(".gheremiah")

def plan(title: str, phases: List[Dict[str, Any]], project_root: Path) -> str:
    """
    Creates or updates a staged execution plan in the global state directory.
    """
    state_dir = get_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    plan_path = state_dir / "plan.yaml"

    # In a real implementation, we might merge with an existing plan.
    # For now, we overwrite or initialize.
    plan_data = {
        "title": title,
        "phases": phases,
        "status": "in-progress"
    }

    try:
        with open(plan_path, "w", encoding="utf-8") as f:
            yaml.dump(plan_data, f, sort_keys=False)
        return f"Plan '{title}' has been saved to {plan_path}.\n\nPhases:\n" + \
               "\n".join([f"- {p.get('name', 'Unnamed Phase')}" for p in phases])
    except Exception as e:
        return f"Error saving plan: {str(e)}"

def read_plan(project_root: Path) -> str:
    """
    Reads the current execution plan.
    """
    plan_path = get_state_dir() / "plan.yaml"
    if not plan_path.exists():
        return "No active plan found."

    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return "Plan file is empty."

        output = f"Current Plan: {data.get('title', 'Untitled')}\nStatus: {data.get('status', 'unknown')}\n\nPhases:\n"
        for i, phase in enumerate(data.get("phases", []), 1):
            name = phase.get("name", "Unnamed Phase")
            tasks = phase.get("tasks", [])
            output += f"{i}. {name}\n"
            for task in tasks:
                status = task.get("status", "pending")
                checkbox = "[x]" if status == "completed" else "[ ]"
                output += f"   {checkbox} {task.get('description', 'No description')}\n"

        return output
    except Exception as e:
        return f"Error reading plan: {str(e)}"

TOOL_SCHEMA = {
    "name": "plan",
    "description": "Create or update a staged execution plan to track progress on complex tasks.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "A short title for the plan."
            },
            "phases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Phase name (e.g., 'Scaffolding')"},
                        "tasks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "status": {"type": "string", "enum": ["pending", "in-progress", "completed"]}
                                },
                                "required": ["description"]
                            }
                        }
                    },
                    "required": ["name"]
                },
                "description": "The stages of the plan."
            }
        },
        "required": ["title", "phases"]
    }
}
