from typing import Optional
import json

def diagnose(failure_output: str, project_root: Optional[None] = None) -> str:
    """
    Analyzes failure output from a test or shell command and suggests potential fixes.

    In a full implementation, this could use an LLM. For the current tool logic,
    it uses pattern matching for common development errors.
    """
    if not failure_output or failure_output == "No failures detected.":
        return "No failure output provided to diagnose."

    # Common error patterns
    patterns = {
        "ModuleNotFoundError": "A required Python module is missing. Suggestion: run 'pip install <module_name>'.",
        "ImportError": "A module could not be imported. Check if the package is installed or the path is correct.",
        "SyntaxError": "There is a syntax error in the code. Check the line number in the failure output.",
        "TypeError": "A function was called with an incorrect argument type. Review the function signature.",
        "ValueError": "A function received an argument of correct type but improper value.",
        "npm ERR!": "An NPM error occurred. Suggestion: run 'npm install' or check package.json.",
        "cannot find module": "A JavaScript module is missing. Suggestion: run 'npm install'.",
        "ConnectionRefusedError": "Could not connect to a service. Ensure the server is running on the expected port.",
        "Permission denied": "The process lacks necessary permissions. Suggestion: check file permissions or use sudo if appropriate.",
        "FileNotFoundError": "A required file was not found. Verify the path and ensure the file was created.",
    }

    findings = []
    for pattern, suggestion in patterns.items():
        if pattern in failure_output:
            findings.append(f"Detected {pattern}: {suggestion}")

    if not findings:
        return "Could not automatically diagnose the failure. Please review the logs manually and identify the root cause."

    return "Diagnosis Findings:\n" + "\n".join(findings)

TOOL_SCHEMA = {
    "name": "diagnose",
    "description": "Analyze build or test failure output and suggest potential root causes and fixes.",
    "parameters": {
        "type": "object",
        "properties": {
            "failure_output": {
                "type": "string",
                "description": "The error logs or failure tail from a previous tool call."
            }
        },
        "required": ["failure_output"]
    }
}
