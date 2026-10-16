# Gheremiah Agent

A minimal, provider-agnostic CLI coding agent. Runs entirely against local models (Ollama, LM Studio, llama.cpp) or any OpenAI-compatible endpoint, with no rate limits, no usage caps, and no vendor lock-in.

## Built from scratch as a learning project — every layer is visible and hackable.

## Why this exists

Hosted coding agents either impose rate limits, restrict which tools you can use, or lock you into a single provider. This project is a small, readable alternative you fully control: point it at a local model for free unlimited use, or at a custom API URL when you need more horsepower.

It's also a ground-up study of how agentic coding tools actually work.

---

## Features

- [x] Multi-turn conversation with persistent context
- [ ] Tool calling: `read_file`, `write_file`, `list_files`, `run_shell`
- [ ] Agent loop with max-iteration guard
- [ ] Provider abstraction: Ollama + OpenAI-compatible endpoints
- [ ] Config file for provider/model selection
- [ ] Path allowlist and command confirmation
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

```
> what's in README.md?
[tool] read_file(path="README.md")
[assistant] This is the README for a CLI coding agent...
```

### With flags

```bash
gheremiah --provider ollama --model qwen2.5-coder:7b
gheremiah --provider openai --base-url http://localhost:1234/v1 --model local-model
gheremiah --project-root ./myproject --dry-run
```

### Exit

Type `exit` or `quit`, or press `Ctrl+D`.

---

## Configuration

Create `~/.gheremiah/config.json`:

```json
{
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

CLI flags override config values.

---

## Architecture

```
CodeAgent/
├── cli.py            # terminal interface, arg parsing
├── core/
│   ├── agent.py      # the agent loop
│   ├── provider.py   # Ollama + OpenAI-compatible adapters
│   ├── tools.py      # tool definitions and implementations
│   ├── context.py    # history management and trimming
│   └── safety.py     # path allowlist, command confirmation
└── config.py         # config loading
```

The core is deliberately decoupled from the CLI. A future VS Code extension
can import `core/` directly or spawn the CLI in a JSON-lines mode.

---

## How it works

The agent is a loop:

1. Send `messages` + tool schemas to the model.
2. If the model replies with text, print it and wait for the next user turn.
3. If the model requests a tool, execute it and append the result as a
   `role: "tool"` message.
4. Repeat from step 1 until no tool calls are returned.

Everything else — providers, tools, safety, context — plugs into that loop.

---

## Safety

This tool can read files, write files, and run shell commands. It is
**not sandboxed by default**.

- Reads and writes are restricted to `--project-root` when set.
- Shell commands require confirmation unless `--yes` is passed.
- Use `--dry-run` to see what the agent _would_ do without executing.

Do not run it against untrusted models or untrusted prompts.

---

## Roadmap

- [x] Phase 1 — Chat with the model
- [ ] Phase 2 — Memory and system prompt
- [ ] Phase 3 — First tool and agent loop
- [ ] Phase 4 — Full toolset
- [ ] Phase 5 — Provider abstraction
- [ ] Phase 6 — Safety and context limits
- [ ] Phase 7 — Polish and packaging

---

## License

MIT
