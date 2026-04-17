# Agent Run Sequence

This document explains how Startup AI Team - One operates today and how the same workflow maps cleanly into a future standalone web app.

## 1. Scheduler entry point

- GitHub Actions is the current scheduler of record.
- `.github/workflows/dispatch.yml` runs every 15 minutes and invokes the dispatcher planner.
- A future web app may replace this entrypoint, but it must preserve the same project/task/run model.

## 2. Planner inputs

Before any run is planned, the runtime reads:

- `config/schedule.json`
- `outputs/state.json`
- recent outputs and handoffs relevant to the active project or startup-wide lane
- the selected startup folder under `projects/{startup-slug}/` when a project is in scope

## 3. Founder-first routing

The founder starts with `MERIDIAN-ORCHESTRATOR`.

MERIDIAN should determine:

1. which project is in scope, or whether the request is `startup_ops`
2. whether the founder wants:
   - startup-wide status
   - project status
   - project/task status
   - new execution
3. what work should be delegated next

If the founder manually launches MERIDIAN without naming a project and the request is not obviously startup-wide, MERIDIAN asks the full startup-intake questionnaire before routing work.
The founder reply can then be ingested to populate the project files under `projects/{startup-slug}/`.
Scheduled MERIDIAN runs should continue on the last non-portfolio project recorded in shared state.

## 4. How the planner decides run order

The planner evaluates agents using:

1. `enabled`
2. `trigger_mode`
3. `run_if_changed`
4. `cooldown_minutes`
5. `max_runs_per_day`
6. `depends_on`
7. `phase`
8. `priority`

This means sequencing is dependency-first, then phase-aware, then priority-driven.

## 5. Practical runtime order

- `MERIDIAN-ORCHESTRATOR` runs first for founder intake, project routing, and status synthesis.
- Launch-core specialists execute the highest-priority project work:
  - `CURRENT-SALES`
  - `FORGE-ENGINEERING`
  - `HERALD-COMMS`
  - `ATLAS-RESEARCH`
- Disabled second-wave specialists deepen planning and instrumentation when later enabled:
  - `CANVAS-PRODUCT`
  - `LEDGER-FINANCE`
  - `VECTOR-ANALYTICS`
  - `MARKETING-BRAND`
- On-demand specialists activate later as needed:
  - `NEXUS-TALENT`
  - `COUNSEL-LEGAL`

## 6. What each run must produce

Every run should generate:

- one project-scoped or startup-wide output
- zero or more project-scoped handoffs
- project-scoped artifacts inside the selected startup folder when a single startup is in scope
- enough metadata for a future dashboard to show:
  - project
  - task type
  - owner agent
  - status
  - blockers
  - latest result

## 7. Shared-state rule

- Specialist agents are stateless per run.
- `MERIDIAN-ORCHESTRATOR` normalizes shared state in `outputs/state.json`.
- Task and handoff statuses should use app-ready statuses such as `queued`, `in_progress`, `waiting_on_founder`, `blocked`, `completed`, and `stale`.

## 8. App boundary

The future web app should be able to render and control:

- founder control center
- project portfolio
- task board
- agent run history
- handoff queue
- escalations
- recent outputs

without redesigning the underlying repo contracts.
