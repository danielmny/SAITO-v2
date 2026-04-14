# MERIDIAN-ORCHESTRATOR — Next Steps & Build Roadmap
*Founders OS v2.1 · Codex Runtime · April 2026*

## Immediate next steps

### Step 1 — Runtime docs and contracts
- [x] Rewrite entrypoint docs for Codex runtime
- [x] Define dispatch contract and event-driven scheduling model
- [x] Define canonical state, artifact metadata, and communication contracts

### Step 2 — Config migration
- [x] Replace cadence-only scheduling with event + heartbeat policy in `config/schedule.json`
- [x] Add `communications.json`, `google-workspace.json`, `models.json`, and `token-policy.json`
- [x] Expand `outputs/state.json` for context hashes, cooldowns, run budgets, communications, and external artifacts

### Step 3 — Repo-native runtime harness
- [x] Implement `runner/orchestrate.py` planner, queue runner, reply ingest, and reconciliation commands
- [x] Add communication abstraction with file-first founder channel support
- [x] Feature-flag Google Workspace adapters so they fail clearly instead of returning stub IDs

### Step 4 — Scheduling and operations
- [x] Add GitHub Actions plan and drain steps for 15-minute dispatch and daily digest checks
- [ ] Wire runtime execution to the chosen Codex invocation path
- [ ] Add reply ingestion beyond the file-backed founder inbox

### Step 5 — Lean-token enforcement
- [x] Define per-agent budgets and model tiers
- [ ] Add prompt-context summarization cache
- [ ] Add token accounting from real model responses

## Recommendations

### Keep the active core small
Stabilize `MERIDIAN-ORCHESTRATOR`, `ATLAS-RESEARCH`, `CURRENT-SALES`, `FORGE-ENGINEERING`, and `HERALD-COMMS` before enabling the second-wave agents. This prevents low-value loops from consuming budget before the trigger model is proven.

### Treat founder comms as transport, not source of truth
File-drop founder messages should create or update repo state, not become the canonical record. This keeps auditability intact and preserves the ability to swap in Gmail or Slack later.

### Prefer mirrored artifacts over Google-first writes
Generate markdown locally first, then mirror selected outputs to Docs or Drive. This avoids state drift and makes reruns and diffing cheaper.

### Measure skipped work as a success metric
An efficient 24/7 system should show many heartbeat cycles that intentionally do nothing. Track skip reasons and no-op rate as operating metrics, not failures.

## Build order summary

```text
1. Runtime contracts and docs
2. Schedule / state / comms / workspace config
3. Repo-native planner, queue, and adapters
4. GitHub Actions heartbeat workflows
5. Real Codex execution and richer reply ingestion
6. Token accounting and summarization cache
7. Publish branch and open PR
```
