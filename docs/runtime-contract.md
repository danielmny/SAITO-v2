# Runtime Contract

This repo is the canonical runtime model for **Startup AI Team - One**. The current surface is repo-native and serial, and every contract in this file is intended to be portable into a future standalone web application without redesign.

## Core design rule

- Repo files remain canonical for now.
- Cloud integrations are adapters, not core runtime assumptions.
- The future web app should be able to read, render, and mutate the same concepts defined here:
  - projects
  - tasks
  - runs
  - handoffs
  - communications
  - escalations
  - dashboard summaries

## Dispatch request

Every runtime invocation should be reducible to this request object:

```json
{
  "agent_id": "MERIDIAN-ORCHESTRATOR",
  "trigger_type": "heartbeat",
  "reason": "project status changed",
  "run_timestamp": "2026-04-14T12:00:00+02:00",
  "changed_context": [
    "outputs/handoffs/HANDOFF-2026-04-14-MERIDIAN-ORCHESTRATOR-001.md"
  ],
  "instance_path": "/workspace/startup-ai-team-one",
  "project": "SIGNAL",
  "task_type": "status_review",
  "origin": "scheduler"
}
```

Dispatch fields:

- `agent_id`: canonical agent identifier from `config/schedule.json`
- `trigger_type`: one of `heartbeat`, `event`, or `manual`
- `reason`: short explanation for why the run was scheduled
- `run_timestamp`: ISO-8601 timestamp for the planned invocation
- `changed_context`: files or folders that made the run eligible
- `instance_path`: repo root for the current runtime instance
- `project`: active project or `startup_ops`
- `task_type`: normalized task classification for routing and dashboard use
- `origin`: source of the work such as `founder_request`, `scheduler`, `handoff`, or `integration`

## Dispatch flow

The runtime is driven in this order:

1. GitHub Actions or a future app scheduler triggers the dispatcher.
2. The planner reads `config/schedule.json` and `outputs/state.json`.
3. Eligible agents are selected using schedule rules, project/task state, and changed context.
4. `MERIDIAN-ORCHESTRATOR` handles founder intake, project selection, status synthesis, and delegation.
5. Specialist agents execute project-scoped work from handoffs or normalized founder requests.
6. The repo-native planner writes request manifests to `runtime/requests/`, enqueues them in `runtime/queue/`, and drains them serially into `runtime/results/`.
7. A MERIDIAN run is a real orchestration pass: it may skip cleanly when nothing meaningful changed, or it may write a founder-facing briefing and normalize shared state.
8. Outputs, handoffs, escalations, communications, and run records are written back to canonical state.

`config/schedule.json` remains the sequencing authority. The future web app may replace the scheduler surface, but not the core runtime concepts.

## State ownership

- `outputs/state.json` is the canonical structured state snapshot.
- `MERIDIAN-ORCHESTRATOR` is the only shared-state normalizer.
- Specialist agents produce outputs and handoffs with enough metadata for MERIDIAN or a future app backend to update state safely.

## Canonical statuses

Use these statuses wherever applicable:

- `queued`
- `in_progress`
- `waiting_on_founder`
- `blocked`
- `completed`
- `processed`
- `stale`

For agent lifecycle states, `success` may remain as the run-result status, but dashboard-facing task and workflow objects should prefer the canonical statuses above.

## Projects contract

State must support a first-class project registry with:

- `project_id`
- `name`
- `slug`
- `type`
- `status`
- `owner_agent`
- `priority`
- `summary`
- `work_mode`
- `last_activity_at`

Every task, handoff, founder request, and agent output must belong to either:

- a named project, or
- the startup-wide operating lane `startup_ops`

## Tasks contract

Task records should support dashboard rendering and routing with:

- `task_id`
- `project`
- `title`
- `task_type`
- `status`
- `owner_agent`
- `origin`
- `source_handoff_id`
- `created_at`
- `updated_at`
- `blocked_by`
- `depends_on`
- `result_output`

## Runs contract

Run records should support auditability and a future execution dashboard:

- `run_id`
- `agent`
- `project`
- `task_type`
- `trigger_type`
- `origin`
- `status`
- `started_at`
- `finished_at`
- `output`

MERIDIAN runs may end in two normal modes:

- `skipped`: no meaningful changed context was found, so state was updated without a new founder artifact
- `success`: a founder-facing output was created and shared state was normalized

## Handoff contract

Every new handoff must include this front matter:

```yaml
handoff_id: HANDOFF-YYYY-MM-DD-FROM-001
from: MERIDIAN-ORCHESTRATOR
to: FORGE-ENGINEERING
project: SIGNAL
task_type: implementation_plan
origin: founder_request
status: queued
created_at: 2026-04-14T12:00:00+02:00
reason: Founder asked for the next build plan for SIGNAL.
source_output: outputs/MERIDIAN-ORCHESTRATOR/2026-04-14-signal-status.md
compatibility: canonical
```

Legacy handoffs that use old agent names or omit required metadata should be marked as:

- `status: stale`
- `compatibility: legacy`

## Output metadata

All founder-facing or app-visible outputs should include front matter:

```yaml
artifact_type: founder_status
audience: founder
project: SIGNAL
task_type: status_review
origin: founder_request
source_run_id: MERIDIAN-ORCHESTRATOR-2026-04-14-signal-status
status: completed
google_drive_id: ""
google_doc_id: ""
communication_thread_id: ""
```

## Communication contract

Outbound communication is channel-agnostic and file-first by default:

- `message_type`
- `subject`
- `body_markdown`
- `attachments`
- `thread_key`
- `requires_reply`
- `reply_deadline`
- `project`
- `task_type`
- `origin`

Default v1 paths:

- outbound: `outputs/communications/outbox/`
- inbound: `inputs/founder-replies/`

Inbound communication must be normalizable into:

- linked project
- linked escalation or founder request thread
- founder response timestamp
- delivery and ingestion status
- unblock or routing action

## Adapter boundary

These are delivery adapters, not core runtime requirements:

- GitHub Actions scheduler
- File-backed founder communication channel
- Gmail communication
- Google Drive / Docs mirroring

The future standalone web app should be another adapter and control surface over the same contracts.

## Lean-token rules

- unchanged effective context should yield a skip via context hashing
- only changed inputs, pending handoffs, unresolved escalations, and recent relevant outputs may be injected
- long-running history should be summarized into rolling notes
- budgets should be enforced per agent and per day, with fallback defaults when an agent lacks an explicit model or token entry
