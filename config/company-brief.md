# Company Brief — SAITO Framework

> This file is the authoritative portfolio-level context for the SAITO runtime.
> It defines how the harness works. Startup-specific facts belong in `projects/{startup-slug}/`.

---

## The Company

**Name:** SAITO Framework
**Type:** Multi-project AI startup operating system
**Stage:** PRE-SEED runtime with active multi-startup execution

**What it does:** Runs a 24/7 team of specialized AI startup operators across multiple named startups. Each startup is treated as a separate project with its own problem, ICP, solution, validation, strategy, financials, roadmap, and decision history.

**Founder interaction model:** The founder starts with `MERIDIAN-ORCHESTRATOR`. On manual launch, MERIDIAN should begin with a concise founder standup for the last open project, ask whether to continue that project or start a new one, then either resume project work or begin a stateful startup-intake session. Once the project is known, MERIDIAN routes work to the relevant specialists, can offer inline recommended actions, and returns synthesized responses.

**Runtime execution model:** SAITO now runs in a hybrid mode:

- hot-path event execution for founder replies, handoffs, escalations, and founder-priority bundle work
- cooldown-governed background execution for heartbeat reviews and overdue maintenance

## Portfolio Model

All work must be scoped to one of:

- a named startup project under `projects/{startup-slug}/`
- the startup-wide operating lane `startup_ops`

Each startup folder should contain, at minimum:

- `project.md`
- `problem.md`
- `icp.md`
- `solution.md`
- `validation.md`
- `strategy.md`
- `financials.md`
- `roadmap.md`
- `decisions.md`

Project-specific artifacts should be written under:

- `projects/{startup-slug}/outputs/{AGENT_NAME}/`

Shared runtime artifacts remain global:

- `outputs/state.json`
- `outputs/handoffs/`
- `outputs/escalations/`
- `outputs/communications/`
- `runtime/`

## Current Portfolio

### Project 1 — SIGNAL

**Slug:** `signal`
**Type:** Job market intelligence platform
**Stage:** PRE-SEED
**Status:** Active startup project
**Project folder:** `projects/signal/`

### Project 2 — Startup Ops

**Slug:** `startup-ops`
**Type:** Internal operating-system project
**Stage:** Internal build
**Status:** Active operating project
**Project folder:** `projects/startup-ops/`

### Project 3 — CreditBank

**Slug:** `creditbank`
**Type:** Transaction infrastructure / credits platform
**Stage:** IDEA
**Status:** Active startup project
**Project folder:** `projects/creditbank/`

## Operating Rules

- The SAITO harness is reusable across many startup ideas, not tied to a single company thesis.
- Every specialist agent should work from the selected startup folder plus the shared runtime state.
- MERIDIAN is responsible for project selection, routing, synthesis, and shared-state normalization.
- MERIDIAN may create founder-priority kickoff bundles and project checkpoints when the founder accepts recommended actions.
- If a founder asks for work on a new startup, the runtime should create or populate a new folder under `projects/` and keep that startup isolated from existing ones.
- The future app should expose the same portfolio, project, task, run, handoff, and communication model defined in this repo.

---

*Last updated: April 18, 2026*
