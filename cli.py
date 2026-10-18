import argparse
import requests
import json
from pathlib import Path
from config import DEFAULT_CONFIG, load_config
from tools import TOOLS, execute_tool

# Limit a user turn so a model cannot request tools forever.
MAX_AGENT_ITERATIONS = 10

# Explain the available tools and safety prompts to the model for every turn.
TOOL_SYSTEM_INSTRUCTIONS = (
    "Use list_files to discover project paths before reading unfamiliar files. "
    "Use read_file when a request depends on file contents. Use write_file only "
    "when the user asks to create or change a file; existing files require the "
    "user's confirmation. Use run_shell only when needed; every command requires "
    "the user's confirmation and may be declined. Never claim a tool action "
    "succeeded unless its result confirms success."
)

# The main function that runs the CLI chat agent.
def main():
    # Create an argument parser to handle command-line arguments.
    parser = argparse.ArgumentParser(description="Gheremiah CLI Chat Agent")

    # Add an argument for the Ollama base URL.
    # Leaving it unset allows the configured provider URL to be used.
    parser.add_argument("--base-url", type=str, default=None,
                        help="Base URL for the Ollama API (e.g., http://localhost:11434)")

    # Add an argument for the model name to use.
    # Leaving it unset allows the configured provider model to be used.
    parser.add_argument("--model", type=str, default=None,
                        help="The model to use (e.g., llama3, qwen2.5-coder:7b)")

    # Add an optional argument for replacing the configured system prompt.
    # This lets a user quickly change the agent's behavior for one run.
    parser.add_argument("--system-prompt", type=str, default=None,
                        help="System instructions for the model (overrides config.json)")

    # Set the working directory and file-access boundary for the project tools.
    parser.add_argument("--project-root", type=Path, default=Path.cwd(),
                        help="Root folder that read_file is allowed to access")

    # Parse the arguments provided by the user.
    args = parser.parse_args()

    # Load the saved settings, creating a default config file on the first run.
    config = load_config()

    # Read which configured provider should be used for this run.
    provider_name = config.get("default_provider", DEFAULT_CONFIG["default_provider"])

    # The current chat endpoint implements Ollama's API, so reject other providers clearly.
    if provider_name != "ollama":
        parser.error(
            f"The configured provider '{provider_name}' is not supported yet; "
            "this CLI currently supports Ollama."
        )

    # Get settings for the selected provider, falling back to its built-in defaults.
    providers = config.get("providers", {})
    if not isinstance(providers, dict):
        parser.error("The providers setting in config.json must be an object.")
    provider_config = providers.get("ollama", DEFAULT_CONFIG["providers"]["ollama"])

    # Ensure the selected provider settings have the expected object shape.
    if not isinstance(provider_config, dict):
        parser.error("The Ollama provider settings in config.json must be an object.")

    # Prefer an explicitly supplied CLI option over the configured provider value.
    base_url = args.base_url
    if base_url is None:
        base_url = provider_config.get(
            "base_url", DEFAULT_CONFIG["providers"]["ollama"]["base_url"]
        )

    # Apply the same CLI-over-config precedence rule to the model name.
    model = args.model
    if model is None:
        model = provider_config.get(
            "model", DEFAULT_CONFIG["providers"]["ollama"]["model"]
        )

    # Reject missing or incorrectly typed connection settings before making a request.
    if not isinstance(base_url, str) or not base_url:
        parser.error("The Ollama base_url setting must be a non-empty string.")
    if not isinstance(model, str) or not model:
        parser.error("The Ollama model setting must be a non-empty string.")

    # Use the CLI value when supplied, otherwise use the configured system prompt.
    system_prompt = args.system_prompt
    if system_prompt is None:
        system_prompt = config.get("system_prompt", DEFAULT_CONFIG["system_prompt"])

    # Reject malformed config values rather than sending an invalid message to Ollama.
    if not isinstance(system_prompt, str):
        parser.error("The system_prompt setting in config.json must be a string.")

    # Resolve the root once so relative tool paths always use the same base folder.
    project_root = args.project_root.resolve()

    # Require a real directory before starting a session with file-reading access.
    if not project_root.is_dir():
        parser.error(f"The project root is not a directory: {project_root}")

    # Construct the full API endpoint for chat completions.
    # This is based on Ollama's API documentation for chat.
    chat_endpoint = f"{base_url}/api/chat"

    print(f"Chatting with model: {model} (Ollama URL: {base_url})")
    print(f"File access is limited to: {project_root}")
    print("Type '/clear' to clear conversation memory, or '/exit' or '/quit' to end.\n")

    # Combine configured instructions with guidance for the tool available in this phase.
    effective_system_prompt = "\n\n".join(
        instruction for instruction in (system_prompt.strip(), TOOL_SYSTEM_INSTRUCTIONS)
        if instruction
    )

    # Keep the system message and conversation memory for this CLI process.
    messages = [{"role": "system", "content": effective_system_prompt}]

    # Start an infinite loop for continuous conversation.
    while True:
        # Prompt the user for input.
        user_input = input("\nYour message :> ")

        # Check if the user wants to exit the chat.
        if user_input.lower() in ["/exit", "/quit"]:
            print("\nExiting chat. Goodbye!")
            break # Break out of the loop to end the program.

        # Clear prior turns while retaining the system prompt for future requests.
        if user_input.lower() == "/clear":
            messages[:] = [messages[0]]
            print("\nConversation memory cleared.")
            continue

        # Append the user's message to the conversation history.
        # Each message is a dictionary with a 'role' (user) and 'content' (the actual message).
        messages.append({"role": "user", "content": user_input})

        # Repeat model requests while it is asking for one of the advertised tools.
        for iteration in range(MAX_AGENT_ITERATIONS):
            # Initialize the response for accurate error reporting in this iteration.
            data = None

            try:
                # Send conversation history and available tool schemas to Ollama.
                response = requests.post(
                    chat_endpoint,
                    json={
                        "model": model,
                        "messages": messages,
                        "tools": TOOLS,
                        "stream": False,
                    },
                    timeout=120,
                )

                # Raise an HTTPError for bad responses (4xx or 5xx).
                response.raise_for_status()

                # Parse and validate the response before reading nested fields.
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Ollama response must be a JSON object.")
                assistant_message = data.get("message")
                if not isinstance(assistant_message, dict):
                    raise ValueError("Ollama response 'message' must be an object.")
                assistant_content = assistant_message.get("content")
                if not isinstance(assistant_content, str):
                    raise ValueError("Ollama response message 'content' must be text.")
                tool_calls = assistant_message.get("tool_calls", [])
                if not isinstance(tool_calls, list):
                    raise ValueError("Ollama response 'tool_calls' must be a list.")

                # Keep tool-call details in history so Ollama can connect results to requests.
                history_message = {
                    "role": "assistant",
                    "content": assistant_content,
                }
                if tool_calls:
                    history_message["tool_calls"] = tool_calls
                messages.append(history_message)

                # A normal assistant response completes this user turn.
                if not tool_calls:
                    print(f"\nGheremiah AI :> {assistant_content}")
                    break

                # Show any text the assistant included alongside its tool requests.
                if assistant_content:
                    print(f"\nGheremiah AI :> {assistant_content}")

                # Run each requested tool and feed its result back as a tool message.
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        raise ValueError("Each Ollama tool call must be an object.")
                    function = tool_call.get("function")
                    if not isinstance(function, dict):
                        raise ValueError("Ollama tool call is missing its function object.")
                    tool_name = function.get("name")
                    tool_arguments = function.get("arguments")
                    if not isinstance(tool_name, str):
                        raise ValueError("Ollama tool call function name must be text.")

                    # Print tool activity so the agent's work is visible while learning.
                    print(f"[tool] {tool_name}({json.dumps(tool_arguments)})")

                    # Execute only the registered tool within the chosen project root.
                    tool_result = execute_tool(tool_name, tool_arguments, project_root)
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": tool_result,
                    })

                    # Display the exact result being sent back to the model.
                    print(f"[tool result] {tool_result}")

                # Stop after a bounded number of tool rounds for this user request.
                if iteration == MAX_AGENT_ITERATIONS - 1:
                    print(
                        "\nAgent stopped after reaching the maximum of "
                        f"{MAX_AGENT_ITERATIONS} tool iterations."
                    )

            except requests.exceptions.ConnectionError as error:
                # Explain connection failures without adding transient errors to memory.
                print(f"Error: Could not connect to Ollama server at {base_url}. Is it running?")
                print(f"Details: {error}")
                break
            except requests.exceptions.RequestException as error:
                # Report other HTTP or network failures and any server response body.
                print(f"Error during Ollama API call: {error}")
                if error.response is not None:
                    print(f"Response content: {error.response.text}")
                break
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                # Report malformed JSON or unexpected response structures explicitly.
                print(f"Error: Unexpected response from Ollama: {error}")
                if data is not None:
                    print(f"Response content: {json.dumps(data, indent=2)}")
                break

# This ensures that main() is called only when the script is executed directly.
if __name__ == "__main__":
    main()