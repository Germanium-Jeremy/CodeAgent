# Gheremiah Agent

A minimal, provider-agnostic CLI coding agent. Runs entirely against local models (Ollama, LM Studio, llama.cpp) or any OpenAI-compatible endpoint, with no rate limits, no usage caps, and no vendor lock-in.

## Built from scratch as a learning project — every layer is visible and hackable.

## Why this exists

Hosted coding agents either impose rate limits, restrict which tools you can use, or lock you into a single provider. This project is a small, readable alternative you fully control: point it at a local model for free unlimited use, or at a custom API URL when you need more horsepower.

It's also a ground-up study of how agentic coding tools actually work.

---

## Features

- [x] Multi-turn conversation with in-session context
- [x] Tool calling: `read_file`, `list_files`, `write_file`, `run_shell`
- [x] Agent loop with max-iteration guard
- [x] Project-root restriction for file tools and confirmation for shell commands
- [x] Provider abstraction: Ollama + OpenAI-compatible endpoints
- [x] Config file for provider/model selection and tool permissions
- [x] Professional TUI with Rich (Markdown rendering, colored output)
- [x] Installable via `pip install -e .`
- [x] Dry-run mode for safe tool testing
- [ ] Shell command sandboxing
- [ ] Context trimming for long sessions
- [ ] Streaming output

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running (for local use)
- A model pulled, e.g.:
  ```bash
  ollama pull qwen2.5-coder:7b
  ```

---

## Install

### Editable Installation (Recommended)
Install Gheremiah as a package so you can run it from anywhere:

```bash
git clone https://github.com/Germanium-Jeremy/CodeAgent.git
cd CodeAgent
pip install -e .
```

Once installed, you can simply type `gheremiah` in your terminal to start the agent.

### Direct Run
Or run directly without installing:

```bash
python -m gheremiah
```

---

## Usage

### Basic
```bash
gheremiah
```

The agent sends the configured system prompt with each request and remembers
the current conversation while the CLI is running. Use `/clear` to discard
conversation turns without exiting; the system prompt remains in effect.
Conversation memory is not saved between runs.

### With Flags
You can override your configuration on a per-run basis using CLI flags:

```bash
# Override the model
gheremiah --model qwen2.5-coder:7b

# Override the provider (must be defined in config.json)
gheremiah --provider remote

# Override the API base URL
gheremiah --base-url http://localhost:1234/v1

# Set a different project root
gheremiah --project-root ./myproject

# Dry run: See what tools would be called without actually executing them
gheremiah --dry-run
```

### Exit
Type `/exit` or `/quit`, or press `Ctrl+D`. Use `/clear` to clear the
conversation while keeping the configured system prompt.

---

## UI Guide
Gheremiah uses a color-coded interface to help you distinguish between participants:
- **Cyan/Green**: Assistant responses (rendered as Markdown).
- **Magenta**: Your input prompts.
- **Yellow**: Tool calls being made by the AI.
- **Dim/Grey Panels**: Tool execution results.
- **Red**: System warnings and context budget alerts.

---

## Configuration
Create `~/.gheremiah/config.json`:

```json
{
  "system_prompt": "You are Gheremiah, a helpful AI coding assistant. Provide concise and relevant responses.",
  "default_provider": "ollama",
  "permissions": {
    "read_file": true,
    "list_files": true,
    "write_file": true,
    "run_shell": true
  },
  "providers": {
    "ollama": {
      "type": "ollama",
      "base_url": "http://localhost:11434",
      "model": "qwen2.5-coder:7b"
    },
    "local-openai": {
      "type": "openai_compatible",
      "base_url": "http://localhost:1234/v1",
      "model": "your-local-model",
      "api_key_env": null
    },
    "remote": {
      "type": "openai_compatible",
      "base_url": "https://your-endpoint.example/v1",
      "model": "your-model",
      "api_key_env": "GHEREMIAH_API_KEY"
    }
  }
}
```

When `--model` or `--base-url` is omitted, the CLI uses the values under the
configured default provider. Supplying either flag overrides only that value
for the current run. The `--system-prompt` flag similarly overrides the
configured `system_prompt`. Set `default_provider` to a key in `providers` to
select an adapter. Ollama uses its native chat API; providers with
`"type": "openai_compatible"` use the OpenAI chat-completions API. Set
`api_key_env` to the name of an environment variable when an endpoint needs
authentication.

`--project-root` sets the folder used by the file tools and as the working
directory for shell commands; it defaults to the current working directory.

---

## Architecture

```
CodeAgent/
├── cli.py            # terminal interface, argument parsing, agent loop
├── config.py         # config loading
├── pyproject.toml    # packaging and entry point
├── tools/
│   ├── base.py       # imports and registers tools; shared dispatch
│   ├── common.py     # shared project-path validation
│   ├── read_file.py  # read_file schema and implementation
│   ├── list_files.py # list_files schema and implementation
│   ├── write_file.py # write_file schema and implementation
│   └── run_shell.py  # run_shell schema and implementation
├── providers/
│   ├── base.py       # abstract interface and normalized response types
│   ├── ollama.py     # Ollama API adapter
│   └── openai.py     # OpenAI-compatible API adapter
└── requirements.txt  # dependency list
```

The agent loop calls the provider-neutral interface. Each adapter translates
the shared conversation and tool schemas to its API, then normalizes its
response once at the adapter boundary. The loop does not import or inspect a
specific provider. Tool schemas and handlers live in separate modules; the
tool registry in `tools/base.py` gathers them for permission filtering and
dispatch.

---

## How it works

The agent uses a loop:

1. Send normalized `messages` and enabled tool schemas through the provider
   interface.
2. If the model replies with text, print it and wait for the next user turn.
3. If the model requests a tool, execute it and append the result as a
   `role: "tool"` message.
4. Repeat until the model returns text or the iteration limit is reached.

Provider-specific request and response formats stay inside their adapters;
everything else plugs into the same agent loop. Streaming is not implemented.

---

## Safety

File tools are restricted to the configured project root, including when a
requested path traverses symlinks. `run_shell` executes commands with the
project root as its working directory, but it is not sandboxed and a command
may access files outside that directory. Every command requires confirmation;
review it before approving. File contents and command output are provided to
the model, so avoid reading secrets or files that should not be included in
model context.

Do not run it against untrusted models or untrusted prompts.

---

## Roadmap

- [x] Phase 1 — Chat with the model
- [x] Phase 2 — Memory and system prompt
- [x] Phase 3 — First tool and agent loop
- [x] Phase 4 — Core file and shell tools
- [x] Phase 5 — Provider abstraction
- [x] Phase 6 — Safety and context limits
- [x] Phase 7 — Polish and packaging

---

## License

MIT
