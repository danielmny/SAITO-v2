# MERIDIAN-ORCHESTRATOR — Project Notes
*Founders OS v2.1 · April 2026*

## Core architectural decisions

### 1. Codex-first runtime
The runtime is designed around Codex-compatible agent execution rather than older session-based tooling. Prompts remain the intelligence layer, while orchestration remains thin plumbing around dispatch, state, and communication.

### 2. Repo as canonical message bus
Agent handoffs, escalations, and state stay in the repo so they remain auditable, diffable, and easy to recover after failures. External systems receive mirrored outputs, not canonical ownership.

### 3. MERIDIAN-ORCHESTRATOR as the only normalizer
All other agents are stateless per run. `MERIDIAN-ORCHESTRATOR` alone owns shared-state normalization in `outputs/state.json`. This keeps concurrency manageable when runs are triggered throughout the day.

### 4. Event-driven 24/7 scheduling
"24/7" is implemented as event-driven responsiveness plus a 15-minute heartbeat dispatcher. No-work cycles should skip quickly and cheaply instead of generating repeated narrative output.

### 5. Google Workspace remains optional
Drive, Docs, and Gmail are future adapters for artifact delivery and founder communications. Repo files remain the source of truth for state and workflow, and file-based founder comms are the current default.

### 6. Communication abstraction
Founder communication goes through a channel interface. `FileChannel` is the v1 implementation. `EmailChannel` and `SlackChannel` are later adapters, not separate logic paths.

## Design principles

- Agents are prompt + context, not business logic services.
- Outputs are markdown first; mirrored external artifacts are optional derivatives.
- Scheduling is policy-driven, not hardcoded to fixed weekly cadences.
- Lean token usage is a hard constraint, not a nice-to-have.
- Never invent data. Escalate unknowns that materially affect decisions.

## Open implementation items

| Question | Owner | Status |
|----------|-------|--------|
| Which Codex invocation path will production runs use? | Founder / FORGE-ENGINEERING | Open |
| Which production delivery adapter should follow the file channel first: Gmail or Slack? | Founder | Open |
| Which Google Drive folders should map to each artifact class once adapters are real? | Founder / HERALD-COMMS | Deferred |
| When should second-wave agents move from disabled to active? | MERIDIAN-ORCHESTRATOR | Deferred |
