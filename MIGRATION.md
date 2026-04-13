# R1 Migration Map

This map connects legacy modules to their target locations in the new architecture.
It does not delete anything; it documents where each legacy behavior should land.

## API Layer

- `R1/api/server.py` -> Thin transport layer over `R1/agent/runtime.py`
- `R1/api/legacy.py` -> Legacy routes only (optional)

## Agent Runtime

- `R1/agent.py` -> `R1/agent/runtime.py` + `R1/agent/loop.py`
- `R1/planning.py` -> `R1/agent/planner.py`
- `R1/decisions.py`, `R1/cognitive.py` -> `R1/agent` helpers (if still needed)
- `R1/desktop_agent.py` -> optional integration layer or external tool

## Model Providers

- `R1/providers.py`, `R1/providers_v2.py` -> `R1/model/manager.py`
- `R1/local_ai.py` -> `R1/model/providers/local_stub.py`
- `R1/gguf_engine.py` -> `R1/model/providers/gguf.py`
- `R1/integrations.py` (model routing bits) -> `R1/model/manager.py`

## Memory

- `R1/memory_persistent.py` -> `R1/memory/store.py`
- `R1/core/memory.py` -> `R1/memory/retrieval.py` + `R1/memory/summarizer.py`

## Tools

- `R1/tools.py` -> `R1/tools/registry.py` + `R1/tools/base.py`
- `R1/browser.py` -> `R1/tools/browser.py`
- `R1/code_executor.py` -> `R1/tools/code_exec.py`
- `R1/system.py` (shell/file ops) -> `R1/tools/shell.py` + `R1/tools/filesystem.py`

## Skills / Plugins

- `R1/skills.py`, `R1/plugins.py` -> `R1/skills/schema.py`, `R1/skills/registry.py`, `R1/skills/loader.py`, `R1/skills/runtime.py`
- `R1/workspace_skills/*` -> `R1/skills/loader.py` discovery path

## Jobs / Background Work

- `R1/cron.py` -> `R1/jobs/manager.py`, `R1/jobs/heartbeat.py`, `R1/jobs/reminders.py`

## Integrations / Messaging

- `R1/webhooks.py`, `R1/gateway.py` -> `R1/integrations/base.py`
- `R1/integrations.py` -> split into `R1/integrations/telegram.py`, `R1/integrations/discord.py`, `R1/integrations/slack.py`

## Observability / Ops

- `R1/diagnostics.py`, `R1/analytics.py` -> keep in `R1/core` or a future `R1/ops` package

## Optional Packs

- `R1/voice.py`, `R1/voice_system.py`, `R1/tts.py`, `R1/multimodal.py` -> optional packs (Phase 11)

## UI

- `R1/web`, `R1/gui`, `R1/cli.py` -> keep, but refactor to reflect new runtime APIs
