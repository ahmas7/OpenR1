# R1 Master Rebuild Plan

This document turns the R1 rebuild into a sequence of concrete implementation passes that can be handed to OpenCode/Codex one at a time.

## Goal

Rebuild R1 into a lightweight, plugin-first, OpenClaw-style personal agent with:

- a real model backend
- persistent memory
- a safe tool system
- an autonomous agent loop
- skills/plugins
- messaging integrations
- optional multimodal packs

Not the goal:

- merging entire external codebases directly
- preserving every current R1 subsystem in the default runtime
- building every feature at once

## Target Architecture

```text
R1/
  api/
    server.py
    schemas.py

  agent/
    runtime.py
    loop.py
    planner.py
    verifier.py
    state.py
    session.py

  model/
    manager.py
    providers/
      base.py
      ollama.py
      gguf.py
      local_stub.py

  memory/
    store.py
    retrieval.py
    summarizer.py

  tools/
    base.py
    registry.py
    shell.py
    filesystem.py
    browser.py
    code_exec.py

  skills/
    schema.py
    registry.py
    loader.py
    runtime.py

  jobs/
    manager.py
    heartbeat.py
    reminders.py

  integrations/
    base.py
    telegram.py
    discord.py
    slack.py

  web/
  cli.py
```

## Build Order

### Phase 0: Freeze Scope

Deliverables:

- `CORE_SCOPE.md`
- `MIGRATION.md`
- new package structure

Success condition:

- core vs optional systems are explicitly defined

### Phase 1: Model Runtime

Deliverables:

- `ModelManager`
- provider health checks
- explicit provider fallback
- no silent fake-AI fallback in production mode

Success condition:

- `/health` reports requested and effective provider
- `/chat` uses a real model path

### Phase 2: Sessions and Memory

Deliverables:

- unified session store
- persistent messages/facts/task history
- retrieval helpers for prompt context

Success condition:

- session state persists and can be reloaded

### Phase 3: Tool Registry

Deliverables:

- tool base class
- tool registry
- structured tool results
- action audit logs

Initial tools:

- shell
- filesystem
- browser
- code execution

Success condition:

- tools are invocable through one interface

### Phase 4: Agent Loop

Deliverables:

- planner
- executor
- verifier
- iteration controls

Success condition:

- R1 can complete a multi-step task with visible status

### Phase 5: Skills / Plugins

Deliverables:

- skill manifest format
- registry
- loader
- install/uninstall/list/load flow

Success condition:

- workspace skills run without being hardcoded into core

### Phase 6: Jobs / Background Work

Deliverables:

- heartbeat loop
- reminders
- cron-like jobs

Success condition:

- R1 can do proactive background work

### Phase 7: Messaging Integrations

Start with:

- Telegram
- Discord
- Slack

Success condition:

- one agent core works through multiple transports

### Phase 8: UI / CLI Cleanup

Deliverables:

- provider health view
- session/task view
- skill list
- recent tool/action log

Success condition:

- operator can see what R1 is doing without reading logs

### Phase 9: Multimodal Packs

Optional capability packs:

- `text-pack`
- `code-pack`
- `docs-pack`
- `audio-pack`
- `vision-pack`

These must be lazy-loaded and non-core.

### Phase 10: Hardening

Deliverables:

- permission policy
- dangerous-action gates
- retry/rollback rules
- test coverage for critical paths

Success condition:

- risky actions are controlled and auditable

## Exact OpenCode Prompt Sequence

Use these in order.

### Prompt 1: Core Scaffolding

```text
Refactor this repository toward a new R1 core architecture. Create these packages and placeholder modules if they do not exist yet:

R1/api
R1/agent
R1/model/providers
R1/memory
R1/tools
R1/skills
R1/jobs
R1/integrations

Add CORE_SCOPE.md and MIGRATION.md at the repo root.

CORE_SCOPE.md should define:
- core runtime modules
- optional modules
- deprecated current modules

MIGRATION.md should map current files to new architecture targets.

Do not remove existing functionality yet. This pass is structural only.
```

### Prompt 2: Model Manager

```text
Implement a unified model runtime for R1.

Create:
- R1/model/manager.py
- R1/model/providers/base.py
- R1/model/providers/ollama.py
- R1/model/providers/gguf.py
- R1/model/providers/local_stub.py

Requirements:
- one unified chat interface
- provider health check support
- explicit requested vs effective provider reporting
- provider priority and fallback logic from config
- no silent production fallback to fake local AI unless explicitly allowed

Refactor existing provider logic out of R1/api/server.py into the new model layer while preserving current behavior.
```

### Prompt 3: Sessions and Memory

```text
Implement a unified session and memory layer for R1.

Create:
- R1/agent/session.py
- R1/agent/state.py
- R1/memory/store.py
- R1/memory/retrieval.py
- R1/memory/summarizer.py

Requirements:
- persistent conversation history
- persistent facts/preferences
- task/action history
- session-aware context loading
- typed interfaces

Unify the current memory implementations so the rest of the system uses one canonical memory API.
```

### Prompt 4: Tool Registry

```text
Implement a unified tool system for R1.

Create:
- R1/tools/base.py
- R1/tools/registry.py
- R1/tools/shell.py
- R1/tools/filesystem.py
- R1/tools/browser.py
- R1/tools/code_exec.py

Requirements:
- common Tool interface
- structured ToolResult
- safety tier for each tool
- execution logging
- discoverable registry

Migrate current shell/filesystem/browser/code execution logic into this registry without deleting existing behavior until migration is complete.
```

### Prompt 5: Agent Loop

```text
Implement the R1 autonomous agent loop.

Create:
- R1/agent/runtime.py
- R1/agent/loop.py
- R1/agent/planner.py
- R1/agent/verifier.py

Requirements:
- session-aware execution
- planner -> executor -> verifier loop
- structured plan steps with statuses
- max iteration limit
- failure/blocked states
- memory integration
- tool registry integration
- model manager integration

The agent loop should be the new core of R1.
```

### Prompt 6: Skills / Plugins

```text
Implement a canonical skill/plugin runtime for R1.

Create:
- R1/skills/schema.py
- R1/skills/registry.py
- R1/skills/loader.py
- R1/skills/runtime.py

Requirements:
- skill manifest format
- local workspace skill loading
- skill list/load/unload/install interfaces
- lazy loading
- integration with the tool registry and agent runtime

Unify the current plugin and skill implementations behind this one system.
```

### Prompt 7: Jobs and Heartbeats

```text
Implement background jobs for R1.

Create:
- R1/jobs/manager.py
- R1/jobs/heartbeat.py
- R1/jobs/reminders.py

Requirements:
- cron-like scheduled jobs
- reminders
- periodic heartbeat summaries
- structured job state and logs

Migrate current cron logic into this package and connect it to the new runtime.
```

### Prompt 8: API Refactor

```text
Refactor R1/api/server.py so it becomes a thin transport layer over the new runtime.

Keep only the core routes in the main default path:
- POST /chat
- POST /agent/run
- GET /agent/status/{session_id}
- POST /agent/stop/{session_id}
- GET /health
- GET /providers
- GET /tools
- GET /skills
- GET /sessions

Optional legacy routes may remain temporarily, but move business logic out of the API layer into agent/model/tools/memory/skills/jobs.
```

### Prompt 9: Messaging Integrations

```text
Implement transport adapters for R1 messaging integrations.

Create:
- R1/integrations/base.py
- R1/integrations/telegram.py
- R1/integrations/discord.py
- R1/integrations/slack.py

Requirements:
- one normalized inbound message format
- one normalized outbound response format
- map transport identities to R1 session identities
- route all message handling through the new agent runtime
```

### Prompt 10: UI / CLI Cleanup

```text
Refactor the R1 web UI and CLI to reflect the new core architecture.

Requirements:
- show active provider and effective provider
- show provider health
- show session/task status
- show recent tool calls
- show loaded skills
- remove stale assumptions from the current CLI

Focus on observability, not decorative dashboards.
```

### Prompt 11: Multimodal Packs

```text
Add optional multimodal capability packs to R1 as plugins, not core dependencies.

Create plugin groups for:
- text-pack
- code-pack
- docs-pack
- audio-pack
- vision-pack

Use lazy imports and isolate heavy dependencies. These packs must not be required for R1 startup.
```

### Prompt 12: Hardening

```text
Harden the R1 runtime for autonomous use.

Requirements:
- tool permission policy
- dangerous-action confirmations or gates
- structured audit log
- retry and rollback strategy where appropriate
- tests for model manager, tool registry, and agent loop
```

## Operational Rule

Do not ask OpenCode to "merge OpenClaw and ZeroClaw into R1".

Do ask OpenCode to:

- port architecture patterns
- refactor boundaries
- migrate selected behavior
- preserve working paths while simplifying the core

## Milestones

### Milestone 1

- R1 starts
- real model works
- `/chat` is reliable

### Milestone 2

- R1 completes one multi-step tool-using task autonomously

### Milestone 3

- R1 works from Telegram or Discord

### Milestone 4

- R1 can load and use skills/plugins

### Milestone 5

- R1 supports optional multimodal packs without bloating core startup
