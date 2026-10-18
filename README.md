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
- [ ] Provider abstraction: Ollama + OpenAI-compatible endpoints
- [ ] Config file for provider/model selection
- [ ] Shell command sandboxing
- [ ] Context trimming for long sessions
- [ ] Streaming output
- [ ] CLI flags (`--model`, `--provider`, `--dry-run`)
- [ ] Installable via `pip install -e .`

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

```bash
git clone https://github.com/Germanium-Jeremy/CodeAgent.git
cd CodeAgent
pip install -e .
```

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

```
> What's in README.md?
[tool] read_file({"path": "README.md"})
[assistant] The README describes Gheremiah, its setup, usage, and roadmap...
```

The tools operate relative to the project root (the current directory by
default). Set another root with `--project-root`. `list_files` returns a flat
list, skips common generated/dependency folders, and caps results at 200
entries. `read_file` returns UTF-8 text and marks files truncated after 200
lines. Each user turn allows up to 10 tool iterations.

New files can be written without a prompt; overwriting an existing file asks
for `y/n`. Every `run_shell` command displays the command and requires `y`
confirmation. Commands run in the project root, time out after 60 seconds,
and return combined output and exit status, with output capped at about 10,000
characters.

### With flags

```bash
python cli.py --model qwen2.5-coder:7b
python cli.py --base-url http://localhost:11434 --model qwen2.5-coder:7b
python cli.py --project-root .\myproject
```

### Exit

Type `/exit` or `/quit`, or press `Ctrl+D`. Use `/clear` to clear the
conversation while keeping the configured system prompt.

---

## Configuration

Create `~/.gheremiah/config.json`:

```json
{
  "system_prompt": "You are Gheremiah, a helpful AI coding assistant. Provide concise and relevant responses.",
  "default_provider": "ollama",
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
configured `system_prompt`. The current CLI supports the Ollama provider.
`--project-root` sets the folder used by the file tools and as the working
directory for shell commands; it defaults to the current working directory.

---

## Architecture

```
CodeAgent/
├── cli.py            # terminal interface, argument parsing, agent loop
├── tools.py          # tool schemas, implementations, and dispatch
└── config.py         # config loading
```

The CLI and first tool are kept in small, visible modules for learning. Later
phases can separate providers, context management, and safety policies.

---

## How it works

The agent uses a loop:

1. Send `messages` and the available tool schemas to the model.
2. If the model replies with text, print it and wait for the next user turn.
3. If the model requests a tool, execute it and append the result as a
   `role: "tool"` message.
4. Repeat until the model returns text or the iteration limit is reached.

Everything else — providers, tools, safety, context — plugs into that loop.

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
- [ ] Phase 5 — Provider abstraction
- [ ] Phase 6 — Safety and context limits
- [ ] Phase 7 — Polish and packaging

---

## License

MIT
