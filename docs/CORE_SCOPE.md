# R1 Core Scope

This document defines which parts of the repository are considered core vs optional,
and which legacy modules are deprecated by the new architecture.

## Core Runtime Modules

The core runtime is the minimal set of packages required to run the autonomous agent:

- `R1/api` (transport layer + schemas)
- `R1/agent` (runtime, loop, planner, verifier, session, state)
- `R1/model` (model manager + providers)
- `R1/memory` (store, retrieval, summarizer)
- `R1/tools` (tool base + registry + built-in tools)
- `R1/skills` (skill schema + registry + loader + runtime)
- `R1/jobs` (background jobs, heartbeat, reminders)
- `R1/integrations` (transport adapters)
- `R1/config` (settings/config)
- `R1/core` (core shared utilities used by the above)

## Optional Modules

These are useful but not required to boot the core runtime:

- `R1/web`, `R1/gui` (UI)
- `R1/stack` (Spark/PyTorch/JAX/Rust demo stack)
- `R1/workspace_skills` (examples and local skills)
- `R1/data` (runtime data stores)
- `models/`, `TTS/`, `Real-ESRGAN/` (heavy optional packs)
- `R1/voice*`, `R1/tts.py`, `R1/multimodal.py` (optional multimodal packs)

## Deprecated / Legacy Modules

These legacy single-file modules are retained temporarily but should be migrated into
the new package layout and then retired:

- `R1/agent.py`
- `R1/tools.py`
- `R1/skills.py`
- `R1/plugins.py`
- `R1/providers.py`, `R1/providers_v2.py`
- `R1/local_ai.py`, `R1/gguf_engine.py`
- `R1/memory_persistent.py`
- `R1/cron.py`
- `R1/webhooks.py`, `R1/gateway.py`
- `R1/system.py`, `R1/unified.py`, `R1/capabilities.py`, `R1/capability_engine.py`
- `R1/diagnostics.py`, `R1/analytics.py`

Any legacy module still in use should be mapped in `MIGRATION.md` and progressively
rerouted through the core packages.
