# Agents.md — Improved Code Agent Implementation Plan

## Goal

Turn the existing minimal CLI agent (currently: `list_files`, `read_file`,
`write_file`, `run_shell`, `edit_file`) into a self-contained coding agent that
can autonomously implement a project outline such as an `AGENTS.md` file by
creating/initializing projects (React, Next, Nest, etc.), generating components,
writing files, making and following plans, and running/test/build scripts while
diagnosing build failures.

## Current Gaps

The agent loop in `cli.py` is a single-turn, in-session tool dispatcher. It
does not plan, does not initiate scaffolded project creation, has no test/build
diagnosis, no failure-repair loop, and no structured memory. The model only
succeeds at described tasks if the user themselves prompts each sub-command.

## Planned Architecture

### 1. Agent Loop Improvements

- Add a multi-turn agent loop with a small scratchpad and a bounded conversation
  cache so repeated turns do not exceed context limits.
- Persist a small state file per project: `agent_state/session.json`,
  `agent_state/plan.yaml`, and a known output directory below the project root.
- Reproduce the loop on each turn so a single user message can trigger many
  tool calls, rather than one user message per tool call.
- Add a structured `tool` role handler that normalizes a tool call into a
  conversation item and returns control to the model loop.

### 2. Tool Set

- Add a `plan` tool that writes and reads execution stages under a stable
  project-relative plan file.
- Add a `tools_mgmt` tool that can initialize a project with a package manager,
  apply templates, and manage generated files.
- Add a `test` tool that runs commands (e.g., `pytest`, `npm test`) and returns
  structured exit status and failure summary.
- Add a `diagnose` tool that runs a build/test command and parses the last
  failure lines, emitting root-cause hints.
- Add a `run_shell` variant that returns a structured summary (exit code, stdout
  tail, stderr tail, elapsed seconds) instead of raw text.
- Add a `write_files` tool for writing multiple files in one turn.
- Add a `read_files` tool for reading multiple files in one turn.
- Keep `read_file`, `list_files`, `write_file`, `run_shell`, and `edit_file`
  for lower-level work.

### 3. Permission and Trust

- Model the tool-call schema and permission matrix in `config.py`.
- Make read-only tools (`read_file`, `list_files`, `read_files`, `plan`,
  `tools_mgmt`) always available.
- Require confirmation for destructive writes (`write_file`, `edit_file`,
  `write_files`, `tools_mgmt` delete/rename modes).
- Add a dry-run mode that reports what would be executed without side effects.

### 4. Project Initialization

- `tools_mgmt` action `init_project` maps a template name to a install command.
- Predefined templates: `react`, `next`, `nest`, `vite`, `django`, `fastapi`,
  `flask`, `express`, `poetry`, `pip`, `uv`, `cargo`.
- Each template stores the command and the dependency install command.
- Support a `install_deps` boolean to automatically run dependency installs.

### 5. Test and Build Diagnosis

- `test` tool: run a command, capture exit code, truncated output, and failure
  tail.
- `diagnose` tool: run the failing command, parse the tail, and suggest fixes.
- The agent should call `diagnose`, then `edit_file`/`write_file`, then rerun
  `test` automatically for first-pass build fixing.

## Files to Modify

### Core

- `cli.py`
  - Replace one-shot tool call handling with an agent loop.
  - Add plan/state persistence helpers and context trimming.
  - Add permission matrix and dry-run handling.
- `tools/base.py`
  - Export the new tool registry and dispatch table.
  - Add default permission matrix and tool ordering.
- `tools/__init__.py`
  - Re-export the new tools and permission helpers.

### New Tools

- `tools/plan.py`
  - Write/read plan YAML files under `.agent_state/`.
- `tools/tools_mgmt.py`
  - Initialize project scaffolds and manage generated files.
- `tools/test.py`
  - Run test commands and return structured status plus failure tail.
- `tools/diagnose.py`
  - Parse build/test failure output and suggest fixes.
- `tools/run_shell.py`
  - Return structured summaries (exit code, time, tails) instead of raw output.
- `tools/write_files.py`
  - Multi-file write helper.
- `tools/read_files.py`
  - Multi-file read helper.

### Providers

- `providers/base.py`
  - Extend normalized response types to support structured tool results.

### Config

- `config.py`
  - Add default permissions and tool permission matrix.
  - Add a `project_templates` default table.

### Documentation

- `README.md`
  - Update feature list, architecture tree, config example, and usage sections.
- `AGENTS.md`
  - This file.

## Tool-Call Workflow for a “write AGENTS.md” Prompt

1. User submits the prompt.
2. Agent calls `plan` to create a staged execution plan.
3. Agent calls `tools_mgmt` with template `npm` / `pip` / `poetry` to
   initialize a workspace if needed.
4. If project scaffolding is required, `tools_mgmt` returns command and
   dependency install steps; agent runs them.
5. Agent calls `write_files` to create the requested files.
6. Agent calls `test` then `diagnose` when a build/test fails.
7. Agent loops: `edit_file` or `write_file` + `test` until exit code is zero
   or the plan is complete.
8. Agent calls `read_files` to verify generated artifacts and summarize.

## Acceptance Criteria

- The agent can initialize a framework project (e.g., `next`, `nest`, `react`,
  `fastapi`, `django`) without manually issuing one command at a time.
- The agent can generate files from a write plan in one turn.
- The agent can run tests and, on failure, emit a diagnosis and iteratively fix
  the project until the suite passes.
- The model cannot bypass the project root or write outside it.
- The project still starts with existing tools enabled, and new tools are
  gated by the same config permission matrix.
- New Python files compile and the tool dispatch does not break current tool
  names.

## Implementation Order

1. Tools registry and schema extensions.
2. `plan`, `tools_mgmt`, `test`, `diagnose`, `write_files`, `read_files`.
3. Agent loop replacement in `cli.py`.
4. Project templates and permission matrix.
5. Documentation and config updates.

## Notes

- Do not add network or call external AI APIs for generation; rely on the
  configured local provider currently in use.
- No tool should require the user to confirm shell commands beyond what already
  exists in `run_shell`/`tools_mgmt`.
