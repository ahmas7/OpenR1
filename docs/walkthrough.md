# Phase 7 Walkthrough

This repository completed the Phase 7 API refactor cleanup around the new R1 core runtime.

## What Changed

- `R1/api/server.py` now serves as the main thin transport layer for the core runtime.
- Core endpoints are owned only by `server.py`.
- `R1/api/legacy.py` is reserved for non-core legacy endpoints and is disabled by default.
- Legacy routes are controlled by the explicit environment flag:
  - `R1_ENABLE_LEGACY_ROUTES=true`
- `/chat` is normalized on the `provider` response field.
- The API defect test suite verifies:
  - core server importability
  - legacy router importability
  - `/chat` schema consistency
  - no duplicate core routes inside `legacy.py`
  - no duplicate core path/method ownership when legacy routes are enabled

## Core Route Ownership

Owned by `R1/api/server.py`:

- `/`
- `/health`
- `/providers`
- `/tools`
- `/skills`
- `/chat`
- `/agent/run`
- `/agent/status/{session_id}`
- `/agent/stop/{session_id}`
- `/sessions`
- `/memory/{session_id}`
- `/v1/*` compatibility aliases for the core route set

Owned by `R1/api/legacy.py`:

- non-core and legacy operational routes only
- browser, shell, file, cron, webhooks, gateway, and subsystem endpoints

## Status

Phase 7 is considered complete when:

- legacy routes are optional
- the core route surface is not duplicated
- the server remains importable with or without legacy routes
- the core API contracts are stable
