import json
import os

# Define the default path for the configuration file.
# This follows the XDG Base Directory Specification for user-specific configuration files.
DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".gheremiah", "config.json")

# A dictionary to hold default configuration values.
# These values will be used if a config file is not found or if specific keys are missing.
DEFAULT_CONFIG = {
    "default_provider": "ollama", # Specifies the default provider to use.
    "system_prompt": "You are Gheremiah, a helpful AI coding assistant. Provide concise and relevant responses.", # Default system prompt for the AI.
    "providers": {
        "ollama": {
            "type": "ollama", # Type of the provider.
            "base_url": "http://localhost:11434", # Default base URL for Ollama.
            "model": "qwen2.5:3b" # Default model to use with Ollama.
        },
        "local-openai": {
            "type": "openai_compatible", # Type for OpenAI-compatible local servers (e.g., LM Studio).
            "base_url": "http://localhost:1234/v1", # Default base URL for local OpenAI-compatible server.
            "model": "your-local-model", # Placeholder for the model name.
            "api_key_env": None # Environment variable for API key (not needed for local).
        },
        "remote": {
            "type": "openai_compatible", # Type for remote OpenAI-compatible servers.
            "base_url": "https://your-endpoint.example/v1", # Placeholder for remote endpoint.
            "model": "your-model", # Placeholder for the model name.
            "api_key_env": "GHEREMIAH_API_KEY" # Environment variable for API key for remote.
        }
    }
}

# Function to load the configuration from a JSON file.
def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Loads the configuration from a specified JSON file.
    If the file does not exist, it creates a default one and loads from it.
    
    Args:
        config_path: The path to the configuration file.
        
    Returns:
        A dictionary containing the loaded configuration.
    """
    
    # Check if the configuration file exists.
    if not os.path.exists(config_path):
        # If it doesn't exist, create the directory for it.
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        # Write the default configuration to the new file.
        with open(config_path, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"Created default config file at {config_path}")
    
    try:
        # Open and load the configuration from the file.
        with open(config_path, "r") as f:
            config = json.load(f)
        # Merge with defaults to ensure all keys are present, especially if the file is old or incomplete.
        # This gives precedence to values in the loaded config.
        merged_config = DEFAULT_CONFIG.copy()
        _deep_update(merged_config, config) # Use a helper to deeply merge configurations.
        return merged_config
    except json.JSONDecodeError:
        # Handle cases where the config file is not valid JSON.
        print(f"Warning: Invalid JSON in config file {config_path}. Using default configuration.")
        return DEFAULT_CONFIG
    except Exception as e:
        # Catch any other potential errors during file reading.
        print(f"Warning: Could not load config file {config_path}: {e}. Using default configuration.")
        return DEFAULT_CONFIG

# Helper function for deep merging dictionaries.
def _deep_update(base_dict: dict, update_dict: dict):
    """
    Recursively updates a dictionary with values from another dictionary.
    
    Args:
        base_dict: The dictionary to be updated.
        update_dict: The dictionary with new values.
    """
    for key, value in update_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            # If both are dictionaries, recurse.
            _deep_update(base_dict[key], value)
        else:
            # Otherwise, update or add the value.
            base_dict[key] = value

# Example of how to use the function if this file were run directly.
if __name__ == "__main__":
    # Load the configuration.
    config = load_config()
    # Print the loaded configuration for verification.
    print(json.dumps(config, indent=2))
