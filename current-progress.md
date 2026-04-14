# Current Progress

## Repository Context

- Active repo: `danielmny/startup-ai-team-one`
- Local workspace: `/Users/d3/Codex/startup-ai-team-one`
- Active branch at time of export: `main`
- Latest commit from this chat: `cac7dfe` — `Refactor runtime for project-scoped app readiness`

## What Was Done In This Chat

### Repo and runtime context

- Switched the working context to `startup-ai-team-one`
- Verified the local checkout, remote, and runtime files
- Read the repo runtime instructions and current state

### Documentation and runtime clarification

- Added a canonical run-sequence document:
  - `docs/agent-run-sequence.md`
- Updated `docs/runtime-contract.md` to match current agent naming and dispatch flow
- Fixed stale runtime references in `docs/google-workspace.md`

### MERIDIAN run

- Ran `MERIDIAN-ORCHESTRATOR` manually
- Wrote:
  - `outputs/MERIDIAN-ORCHESTRATOR/2026-04-14-operating-checkpoint.md`
- Updated:
  - `outputs/state.json`

### Behavior changes for Startup AI Team - One

- Reframed the system as a 24/7 multi-project startup team
- Updated founder interaction behavior so MERIDIAN:
  - asks which project the founder wants to work on
  - offers startup-wide status, project status, and task status views
  - routes work to specialists and synthesizes results back to the founder
- Preserved `SIGNAL` as an active project inside a broader project portfolio

### Future standalone web app readiness

- Refactored the repo to act as an app-ready backend domain model
- Added first-class project/task/origin concepts across:
  - runtime docs
  - state model
  - handoffs
  - agent prompts
  - runner scaffolding
- Defined the future web app boundary as:
  - founder control center
  - autonomous execution engine
  - project and agent dashboard

### Agent prompt normalization

- Updated all specialist prompts in `agents/`
- Replaced old workspace paths
- Made prompts project-scoped instead of assuming a single SIGNAL-only workflow

### Runtime and state model refactor

- Reworked `outputs/state.json` to include:
  - project registry
  - task board
  - founder requests
  - dashboard summaries
  - app-oriented run records
- Normalized canonical statuses for dashboard and workflow use

### Handoff normalization

- Updated canonical `MERIDIAN-ORCHESTRATOR-*` handoffs with:
  - `project`
  - `task_type`
  - `origin`
  - `compatibility: canonical`
  - queued status model
- Preserved old `MERIDIAN-*` handoffs as compatibility artifacts and marked them stale

### Runner scaffolding

- Implemented a real scaffold for:
  - `runner/orchestrate.py`
- Extended:
  - `runner/communications.py`
  - `runner/google_workspace.py`
- Kept cloud integrations as adapters rather than core runtime assumptions

### Validation

- Verified no remaining active references to the old workspace path in runtime docs/prompts
- Verified runner Python syntax with `py_compile` using a local cache override

## Key Files Changed

- `AGENTS.md`
- `README.md`
- `FOUNDERS_OS_AGENT_SYSTEM.md`
- `config/company-brief.md`
- `docs/runtime-contract.md`
- `docs/agent-run-sequence.md`
- `docs/google-workspace.md`
- `outputs/state.json`
- `runner/orchestrate.py`
- `agents/*.md`
- `outputs/handoffs/*.md`

## Current Runtime Direction

- `MERIDIAN-ORCHESTRATOR` is the founder-facing intake layer
- All work should be project-scoped or explicitly classified as `startup_ops`
- The repo is now structured so a future standalone web app can use the same backend concepts without redesign
- Cloud services such as GitHub Actions, Gmail, and Google Workspace remain supported as adapters

## Current Known State

- Canonical queue is the `MERIDIAN-ORCHESTRATOR-*` handoff set
- Legacy `MERIDIAN-*` handoffs remain in the repo as stale compatibility artifacts
- The runtime is still document-driven today, but the backend model is now much closer to app-ready

## Latest Commit

```text
cac7dfe Refactor runtime for project-scoped app readiness
```
