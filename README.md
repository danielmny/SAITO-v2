# Founders OS — Codex Runtime

Founders OS is a multi-agent operating system for startup work. In `Startup AI Team - One`, it behaves like a 24/7 team of startup operators working across clearly defined projects, with `MERIDIAN-ORCHESTRATOR` acting as the founder-facing project intake and coordination layer.

## Operating Model

- Codex-compatible runner executes agents as stateless jobs
- GitHub Actions remains the scheduler of record
- A 15-minute dispatcher heartbeat scans for new events, changed context, and overdue work
- Handoffs and state stay in-repo for auditability
- Google Drive, Docs, and Gmail mirror founder-facing work products
- Founder replies arrive by email and are normalized back into repo state
- Founder conversations start with project selection unless the request is clearly startup-wide
- Specialist agents receive scoped, project-specific work through handoffs and return outputs that MERIDIAN synthesizes back to the founder
- The runtime contracts are being prepared so a future standalone web app can become the founder control center, dashboard, and execution surface without redesigning the backend model

## Agent Activation

The initial always-active core is intentionally small:

| ID | Agent | Function | Default mode |
|----|-------|----------|--------------|
| A-00 | MERIDIAN-ORCHESTRATOR | Orchestrator | `heartbeat + event` |
| A-01 | ATLAS-RESEARCH | Market Research | `event` |
| A-03 | FORGE-ENGINEERING | Engineering | `event` |
| A-05 | CURRENT-SALES | Sales | `event` |
| A-06 | LEDGER-FINANCE | Finance & Fundraising | `event` |
| A-10 | HERALD-COMMS | Investor Relations & PR | `event` |

Second-wave agents are enabled in the schedule, but they remain phase-gated and should stay mostly inactive until triggered by handoffs, dependencies, or manual founder work:

- `CANVAS-PRODUCT`
- `MARKETING-BRAND`
- `VECTOR-ANALYTICS`
- `NEXUS-TALENT`
- `COUNSEL-LEGAL`

## Runtime Contract

Every dispatched run uses the same core request shape:

- `agent_id`
- `trigger_type`
- `reason`
- `run_timestamp`
- `changed_context`
- `instance_path`

Specialist agents remain stateless per run. `MERIDIAN-ORCHESTRATOR` is the only component that normalizes shared state into `outputs/state.json`, asks the founder which project they want to work on, reports startup and project status, and routes work to the appropriate specialists.

## File Structure

```text
├── AGENTS.md                         ← Codex entry point for agent runs
├── CLAUDE.md                         ← Legacy compatibility note pointing to AGENTS.md
├── FOUNDERS_OS_AGENT_SYSTEM.md       ← Agent definitions, cadences, responsibilities
├── agents/                           ← Per-agent runtime prompts
├── config/
│   ├── company-brief.md              ← Company context
│   ├── schedule.json                 ← Event + heartbeat dispatch policy
│   ├── communications.json           ← Founder channel settings
│   ├── google-workspace.json         ← Drive / Docs / Gmail integration config
│   ├── token-policy.json             ← Per-agent budget controls
│   ├── models.json                   ← Model profile routing
│   └── agent-skills.json             ← External artifact guidance by agent
├── docs/
│   ├── runtime-contract.md           ← Dispatch, state, artifact, and communication contracts
│   ├── agent-run-sequence.md         ← Founder intake, routing, and execution sequence
│   ├── google-workspace.md           ← Workspace integration model
│   └── publish-checklist.md          ← Validation and publish sequence
├── runner/
│   ├── orchestrate.py                ← Future app/backend orchestration entrypoint
│   ├── communications.py             ← Channel abstraction with Email/Slack stubs
│   └── google_workspace.py           ← Drive / Docs / Gmail adapter scaffolding
├── .github/workflows/
│   ├── dispatch.yml                  ← 15-minute dispatcher heartbeat
│   └── daily-digest.yml              ← Founder digest trigger
├── outputs/
│   ├── state.json                    ← Canonical runtime state
│   ├── handoffs/                     ← Inter-agent work queue
│   ├── escalations/                  ← Pending / resolved escalations
│   └── {AGENT_NAME}/                 ← Agent output history
```

## Core Principles

1. Repo state is canonical. Google Workspace is a collaboration and delivery layer, not the source of truth.
2. 24/7 means responsive dispatch, not constant re-running. No-work cycles should skip cleanly.
3. Founder communication is email-first in v1, but every outbound and inbound flow goes through a pluggable communication interface.
4. Token efficiency is a product requirement. Only changed inputs, pending handoffs, unresolved escalations, and the most recent relevant outputs should be injected into prompts.
5. `MERIDIAN-ORCHESTRATOR` owns founder intake, project selection, system normalization, triage, and founder digests. Specialist agents should stay narrow, project-scoped, and cheap.
6. The repo should model backend domain concepts cleanly enough that a future standalone web app can sit on top of the same project, task, run, handoff, escalation, and communication contracts.

## Validation Before Publish

Before publishing to GitHub:

1. Search for stale operational dependencies on legacy runtime terms and workflows.
2. Verify `schedule.json`, `state.json`, and `docs/runtime-contract.md` describe the same dispatch and metadata rules.
3. Verify email-first communication and Google Workspace mirroring do not conflict on source-of-truth rules.
4. Verify the dispatcher skips unchanged context and respects cooldowns and daily run caps.

*Founders OS v2.1 · Codex Runtime · April 2026*
