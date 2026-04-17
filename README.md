# Founders OS — Codex Runtime

Founders OS is a multi-agent operating system for startup work. In the SAITO harness, it behaves like a 24/7 team of startup operators working across multiple separate startup projects, with `MERIDIAN-ORCHESTRATOR` acting as the founder-facing project intake and coordination layer.

## Operating Model

- Codex-compatible runner executes agents as stateless jobs, with a full MERIDIAN orchestration pass on top of the serial harness
- GitHub Actions remains the scheduler of record
- A 15-minute dispatcher heartbeat scans for new events, changed context, and overdue work
- The planner coalesces pending handoffs into one queued request per agent per cycle to avoid duplicate serial work
- Handoffs and state stay in-repo for auditability
- File-backed runtime manifests are the default execution path
- Founder communication defaults to repo files in `outputs/communications/outbox/` and `inputs/founder-replies/`
- Google Drive, Docs, and Gmail stay disabled until real adapters exist
- Manual founder launches start with project selection unless the request is clearly startup-wide
- Scheduled MERIDIAN runs continue on the last real project in `MERIDIAN-ORCHESTRATOR.active_project`
- Enabled specialist agents receive scoped, project-specific work through handoffs, generate real markdown artifacts, and may create justified downstream handoffs that MERIDIAN later synthesizes back to the founder
- Equivalent downstream handoffs are suppressed so repeated runs do not reopen the same follow-on work without new justification
- The runtime contracts are being prepared so a future standalone web app can become the founder control center, dashboard, and execution surface without redesigning the backend model

## Agent Activation

The initial always-active core is intentionally small:

| ID | Agent | Function | Default mode |
|----|-------|----------|--------------|
| A-00 | MERIDIAN-ORCHESTRATOR | Orchestrator | `heartbeat + event` |
| A-01 | ATLAS-RESEARCH | Market Research | `event` |
| A-02 | CANVAS-PRODUCT | Product | `event` |
| A-03 | FORGE-ENGINEERING | Engineering | `event` |
| A-04 | MARKETING-BRAND | Brand & Demand Gen | `event` |
| A-05 | CURRENT-SALES | Sales | `event` |
| A-06 | LEDGER-FINANCE | Finance & Fundraising | `event` |
| A-07 | NEXUS-TALENT | Talent & Hiring | `event` |
| A-08 | COUNSEL-LEGAL | Legal | `event` |
| A-09 | VECTOR-ANALYTICS | Analytics & Growth | `event` |
| A-10 | HERALD-COMMS | Investor Relations & PR | `event` |

Second-wave agents stay disabled at launch until the core harness is stable and real demand requires them:


## Runtime Contract

Every dispatched run uses the same core request shape:

- `agent_id`
- `trigger_type`
- `reason`
- `run_timestamp`
- `changed_context`
- `instance_path`

Specialist agents remain stateless per run. `MERIDIAN-ORCHESTRATOR` is the only component that normalizes shared state into `outputs/state.json`, asks the founder which project they want to work on, reports startup and project status, and routes work to the appropriate specialists.

`make run-meridian` now queues a manual MERIDIAN intake pass. After `make drain`, MERIDIAN either:

- asks which startup/project to work on, or
- writes a founder-facing briefing and normalizes shared state once project scope is clear

To scaffold a new startup project from the template:

- `make scaffold-project NAME="New Startup" KEY="NEW-STARTUP" TYPE="product" STAGE="IDEA" SUMMARY="One-line summary"`

## File Structure

```text
├── AGENTS.md                         ← Codex entry point for agent runs
├── CLAUDE.md                         ← Legacy compatibility note pointing to AGENTS.md
├── FOUNDERS_OS_AGENT_SYSTEM.md       ← Agent definitions, cadences, responsibilities
├── agents/                           ← Per-agent runtime prompts
├── config/
│   ├── company-brief.md              ← Portfolio context
│   ├── schedule.json                 ← Event + heartbeat dispatch policy
│   ├── communications.json           ← Founder channel settings
│   ├── google-workspace.json         ← Drive / Docs / Gmail integration config
│   ├── token-policy.json             ← Per-agent budget controls
│   ├── models.json                   ← Model profile routing
│   └── agent-skills.json             ← External artifact guidance by agent
├── projects/
│   ├── _template/                    ← Reusable startup template hierarchy
│   ├── signal/                       ← Example startup project
│   └── startup-ops/                  ← Internal operating-system project
├── docs/
│   ├── runtime-contract.md           ← Dispatch, state, artifact, and communication contracts
│   ├── agent-run-sequence.md         ← Founder intake, routing, and execution sequence
│   ├── google-workspace.md           ← Workspace integration model
│   └── publish-checklist.md          ← Validation and publish sequence
├── runner/
│   ├── orchestrate.py                ← Repo-native planner, queue runner, reply ingest, and reconciliation CLI
│   ├── communications.py             ← File-first founder communication backend
│   ├── google_workspace.py           ← Feature-flagged Google adapter boundary
│   ├── specialists.py                ← Deterministic executor layer for enabled specialist agents
│   └── smoke_test.py                 ← Minimal temp-copy runtime validation
├── runtime/
│   ├── requests/                     ← Canonical request manifests
│   ├── queue/                        ← Pending serial execution queue
│   ├── results/                      ← Per-run result manifests
│   └── logs/                         ← Reconciliation and audit logs
├── .github/workflows/
│   ├── dispatch.yml                  ← 15-minute dispatcher heartbeat
│   └── daily-digest.yml              ← Founder digest trigger
├── outputs/
│   ├── state.json                    ← Canonical runtime state
│   ├── handoffs/                     ← Inter-agent work queue
│   ├── escalations/                  ← Pending / resolved escalations
│   ├── communications/outbox/        ← File-backed founder outbox
│   └── {AGENT_NAME}/                 ← Startup-wide or legacy agent output history
├── inputs/
│   └── founder-replies/              ← File-backed founder reply inbox
```

## Core Principles

1. Repo state is canonical. Google Workspace is a collaboration and delivery layer, not the source of truth.
2. 24/7 means responsive dispatch, not constant re-running. No-work cycles should skip cleanly.
3. Founder communication is file-first in v1, but every outbound and inbound flow still goes through a pluggable communication interface.
4. Token efficiency is a product requirement. Only changed inputs, pending handoffs, unresolved escalations, and the most recent relevant outputs should be injected into prompts.
5. `MERIDIAN-ORCHESTRATOR` owns founder intake, project selection, system normalization, triage, and founder digests. Specialist agents should stay narrow, project-scoped, and cheap.
6. The repo should model backend domain concepts cleanly enough that a future standalone web app can sit on top of the same project, task, run, handoff, escalation, and communication contracts.

## Validation Before Publish

Before publishing to GitHub:

1. Search for stale operational dependencies on legacy runtime terms and workflows.
2. Verify `schedule.json`, `state.json`, and `docs/runtime-contract.md` describe the same dispatch and metadata rules.
3. Verify file-first communication and disabled Google Workspace defaults do not conflict with source-of-truth rules.
4. Verify the dispatcher skips unchanged context and respects cooldowns and daily run caps.

*Founders OS v2.1 · Codex Runtime · April 2026*
