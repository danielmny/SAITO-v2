# Founders OS Autonomous Scheduling Plan

## Summary

Run Founders OS as a Codex-first split system with:

- a reusable runtime layer that owns dispatch logic, scheduling policy, escalation handling, optional Google Workspace adapters, and communication adapters
- an instance workspace that owns company context, outputs, handoffs, and live state

Use a hybrid operating model:

- GitHub Actions is the unattended scheduler and source of truth for dispatch timing
- the runtime dispatcher evaluates work every 15 minutes
- agents run when triggered by new events, changed context, unresolved escalations, or digest deadlines

Authority stays internal-only:

- agents may read context, generate outputs, update repo state, create handoffs, optionally mirror artifacts to Google Workspace later, and send founder messages through the configured channel
- agents do not merge code, publish externally, or mutate external business systems without a later approval phase

## Key Design Changes

### Runtime and repo structure

Keep the runtime thin and Codex-compatible:

- `runner/orchestrate.py` is the entrypoint for dispatch planning, queue draining, reply ingestion, and state reconciliation
- Google Workspace integration lives behind adapter classes, not inside prompts
- founder communication lives behind a channel interface so the file backend can later be replaced by Gmail or Slack

Inputs per run:

- `agent_id`
- `trigger_type`
- `reason`
- `run_timestamp`
- `changed_context`
- `instance_path`

Outputs per run:

- markdown artifact
- optional handoff files
- updated state summary
- communication records
- optional Google Drive / Docs identifiers when adapters are eventually enabled

`MERIDIAN` stays the only normalizer of shared state to avoid race conditions.

### Scheduling and orchestration behavior

Use event-driven scheduling with a heartbeat:

- dispatcher heartbeat every 15 minutes
- agents run only when there is a meaningful trigger or an overdue review threshold
- unchanged context skips a run and records a skip reason
- `NEXUS` and `COUNSEL` remain event/manual only

Recommended defaults:

1. `MERIDIAN`: `heartbeat + event`
2. `ATLAS`, `CURRENT`, `FORGE`, `HERALD`: `event`
3. `CANVAS`, `MARKETING`, `LEDGER`, `VECTOR`, `NEXUS`, `COUNSEL`: disabled at launch

### Communications and optional Google adapters

Use repo-native communications in v1:

- file outbox for founder digests and escalations
- file inbox for founder replies
- optional later adapters for Drive, Docs, and Gmail once implemented

Keep repo files canonical:

- handoffs, state, escalations, and logs stay in-repo
- Google artifacts are mirrors with external IDs stored in metadata

### Lean-token rules

Every run must enforce:

- per-agent daily budget
- per-run input and output caps
- context limited to changed inputs, pending handoffs, unresolved escalations, and the most recent relevant outputs
- no re-run when effective context hash is unchanged

## Schema Additions

### `config/schedule.json`

Per-agent policy should include:

- `enabled`
- `phase`
- `priority`
- `trigger_mode`
- `heartbeat_minutes`
- `cooldown_minutes`
- `max_runs_per_day`
- `run_if_changed`
- `depends_on`
- `context_inputs`
- `quiet_hours_policy`

### `outputs/state.json`

Per-agent state should include:

- `last_run`
- `last_success`
- `status`
- `last_output`
- `last_trigger`
- `context_hash`
- `cooldown_until`
- `run_budget`
- `skip_reason`
- `communications`
- `external_artifacts`

Global state should include:

- `system_version`
- `pending_events`
- `open_escalations`
- `run_queue`
- `founder_digest_due_at`
- `communications`

## Test Plan

1. Simulate heartbeat dispatch and verify only agents with new work are queued.
2. Simulate unchanged context and verify the runtime records a skip instead of a run.
3. Simulate a blocking escalation and confirm dependent agents are held.
4. Simulate file-based founder message delivery and reply ingestion through the communication interface.
5. Simulate optional future artifact mirroring and verify Google IDs are written back to metadata/state only after real adapter success.
6. Verify token budgets suppress runaway loops and expose a clear skip or throttle reason.

## Assumptions and defaults

- GitHub Actions remains the unattended scheduler of record.
- “24/7” means event-driven responsiveness plus a 15-minute dispatcher heartbeat.
- Google Workspace remains disabled until the real adapters exist.
- File-based comms are the founder channel in v1; Gmail and Slack remain later adapters.
- Repo state remains canonical; Google Workspace is a collaboration and delivery layer.
