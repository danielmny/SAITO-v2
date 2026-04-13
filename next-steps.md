# MERIDIAN — Next Steps & Build Roadmap
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

### Step 3 — Dispatcher scaffolding
- [x] Add `runner/orchestrate.py` CLI scaffold for heartbeat planning and one-off run request assembly
- [x] Add communication abstraction with email-first channel support
- [x] Add Google Workspace adapter scaffolding for Drive / Docs / Gmail

### Step 4 — Scheduling and operations
- [x] Add GitHub Actions workflow scaffolds for 15-minute dispatch and daily digest checks
- [ ] Wire runtime execution to the chosen Codex invocation path
- [ ] Add reply ingestion from the configured founder email inbox

### Step 5 — Lean-token enforcement
- [x] Define per-agent budgets and model tiers
- [ ] Add prompt-context summarization cache
- [ ] Add token accounting from real model responses

## Recommendations

### Keep the active core small
Stabilize `MERIDIAN`, `ATLAS`, `CURRENT`, `FORGE`, `HERALD`, and `LEDGER` before enabling the second-wave agents. This prevents low-value loops from consuming budget before the trigger model is proven.

### Treat email as transport, not source of truth
Founder emails should create or update repo state, not become the canonical record. This keeps auditability intact and preserves the ability to swap in Slack later.

### Prefer mirrored artifacts over Google-first writes
Generate markdown locally first, then mirror selected outputs to Docs or Drive. This avoids state drift and makes reruns and diffing cheaper.

### Measure skipped work as a success metric
An efficient 24/7 system should show many heartbeat cycles that intentionally do nothing. Track skip reasons and no-op rate as operating metrics, not failures.

## Build order summary

```text
1. Runtime contracts and docs
2. Schedule / state / comms / workspace config
3. Dispatcher and adapter scaffolding
4. GitHub Actions heartbeat workflows
5. Real Codex execution and reply ingestion
6. Token accounting and summarization cache
7. Publish branch and open PR
```
