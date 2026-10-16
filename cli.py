import argparse
import requests
import json

# The main function that runs the CLI chat agent.
def main():
    # Create an argument parser to handle command-line arguments.
    parser = argparse.ArgumentParser(description="Gheremiah CLI Chat Agent")

    # Add an argument for the Ollama base URL.
    # This allows users to specify where their Ollama instance is running.
    parser.add_argument("--base-url", type=str, default="http://localhost:11434",
                        help="Base URL for the Ollama API (e.g., http://localhost:11434)")

    # Add an argument for the model name to use.
    # This lets users choose which model they want to chat with.
    parser.add_argument("--model", type=str, default="llama3.2:3b",
                        help="The model to use (e.g., llama3, qwen2.5-coder:7b)")

    # Parse the arguments provided by the user.
    args = parser.parse_args()

    # Construct the full API endpoint for chat completions.
    # This is based on Ollama's API documentation for chat.
    chat_endpoint = f"{args.base_url}/api/chat"

    print(f"Chatting with model: {args.model} (Ollama URL: {args.base_url})")
    print("Type '/exit' or '/quit' to end the conversation.")

    # Initialize a list to hold the conversation history.
    # This is crucial for multi-turn conversations, allowing the model to remember previous turns.
    messages = []

    # Start an infinite loop for continuous conversation.
    while True:
        # Prompt the user for input.
        user_input = input("Your message :> ")

        # Check if the user wants to exit the chat.
        if user_input.lower() in ["/exit", "/quit"]:
            print("Exiting chat. Goodbye!")
            break # Break out of the loop to end the program.

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
                    "model": args.model,   # Specify the model we want to use.
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
            print(f"Gheremiah AI :> {assistant_message_content}")

            # Append the assistant's message to the conversation history.
            # This ensures the model remembers its own replies for future turns.
            messages.append({"role": "assistant", "content": assistant_message_content})

        except requests.exceptions.ConnectionError as e:
            # Handle connection errors (e.g., Ollama server not running).
            print(f"Error: Could not connect to Ollama server at {args.base_url}. Is it running?")
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