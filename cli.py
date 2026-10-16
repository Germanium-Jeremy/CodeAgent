import argparse
import requests
import json
from config import DEFAULT_CONFIG, load_config

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

    # Construct the full API endpoint for chat completions.
    # This is based on Ollama's API documentation for chat.
    chat_endpoint = f"{base_url}/api/chat"

    print(f"Chatting with model: {model} (Ollama URL: {base_url})")
    print("Type '/clear' to clear conversation memory, or '/exit' or '/quit' to end.\n")

    # Start with a system message so its instructions apply to every model response.
    # Keep conversation memory in this list for the lifetime of this CLI process.
    messages = [{"role": "system", "content": system_prompt}]

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

        try:
            # Send the conversation history to the Ollama model.
            # We use requests.post to send a POST request to the chat endpoint.
            # The 'json' parameter automatically serializes the dictionary to JSON and sets the Content-Type header.
            response = requests.post(
                chat_endpoint,
                json={
                    "model": model,        # Specify the model we want to use.
                    "messages": messages,  # Pass the entire conversation history.
                    "stream": False        # We're not streaming the response for simplicity in this phase.
                },
                timeout=120  # Set a timeout for the request to prevent indefinite waiting.
            )
            # Raise an HTTPError for bad responses (4xx or 5xx).
            response.raise_for_status()

            # Parse the JSON response from Ollama.
            # The response contains the model's reply.
            data = response.json()

            # Extract the model's message content.
            # Ollama's chat API typically returns the message under ['message']['content'].
            assistant_message_content = data['message']['content']
            print(f"\nGheremiah AI :> {assistant_message_content}")

            # Append the assistant's message to the conversation history.
            # This ensures the model remembers its own replies for future turns.
            messages.append({"role": "assistant", "content": assistant_message_content})

        except requests.exceptions.ConnectionError as e:
            # Handle connection errors (e.g., Ollama server not running).
            print(f"Error: Could not connect to Ollama server at {base_url}. Is it running?")
            print(f"Details: {e}")
            # Do not append the error message to history to avoid polluting context with transient errors
        except requests.exceptions.RequestException as e:
            # Handle other request-related errors (e.g., network issues, invalid model).
            print(f"Error during Ollama API call: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            # Do not append the error message to history
        except json.JSONDecodeError:
            # Handle cases where the response is not valid JSON.
            print("Error: Could not decode JSON response from Ollama.")
            print(f"Raw response: {response.text}")
            # Do not append the error message to history
        except KeyError:
            # Handle cases where the expected 'message' or 'content' key is missing.
            print("Error: Unexpected response format from Ollama.")
            print(f"Raw response: {json.dumps(data, indent=2)}")
            # Do not append the error message to history

# This ensures that main() is called only when the script is executed directly.
if __name__ == "__main__":
    main()