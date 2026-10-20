import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any
import json

def run_test(command: str, target: Optional[str], timeout: Optional[int], project_root: Path) -> str:
    """
    Runs a test command and returns a structured summary of the result.
    """
    if not command:
        return "Error: No test command provided."

    # Construct full command if target is provided
    full_cmd = command
    if target:
        full_cmd = f"{command} {target}"

    start_time = time.time()
    try:
        process = subprocess.run(
            full_cmd,
            shell=True,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        duration = time.time() - start_time

        exit_code = process.returncode
        stdout = process.stdout
        stderr = process.stderr

        # Extract failure tail if it failed
        failure_tail = ""
        if exit_code != 0:
            combined = stdout + "\n" + stderr
            lines = combined.splitlines()
            failure_tail = "\n".join(lines[-20:])

        result = {
            "exit_code": exit_code,
            "duration": f"{duration:.2f}s",
            "summary": "\n".join(stdout.splitlines()[:10]),
            "failure_tail": failure_tail if exit_code != 0 else "No failures detected."
        }

        return json.dumps(result, indent=2)

    except subprocess.TimeoutExpired as e:
        return json.dumps({
            "exit_code": -1,
            "error": f"Test timed out after {timeout} seconds.",
            "stdout": e.stdout.decode() if e.stdout else ""
        }, indent=2)
    except Exception as e:
        return f"Error executing test: {str(e)}"

TOOL_SCHEMA = {
    "name": "test",
    "description": "Run a test or build command and return a structured summary of the result, including a failure tail on error.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The test command to run (e.g., 'pytest', 'npm test')."
            },
            "target": {
                "type": "string",
                "description": "Optional target file or directory to test."
            },
            "timeout": {
                "type": "integer",
                "description": "Optional timeout in seconds."
            }
        },
        "required": ["command"]
    }
}
