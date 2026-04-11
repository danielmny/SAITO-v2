# MERIDIAN — Next Steps & Build Roadmap
*Founders OS v1.0 · April 2026*

---

## Immediate next steps

### Step 0 — Repo setup (blocked on founder decision)
- [ ] Decide: same repo or separate outputs repo for agent outputs
- [ ] Create **"Startup AI Team - standalone"** repo (clean Founders OS, no SIGNAL content)
- [ ] Remove `SIGNAL_PROJECT_SUMMARY.md` and SIGNAL references from `CLAUDE.md` and `README.md`
- [ ] Create the full agent folder structure (`/ATLAS`, `/CANVAS`, `/FORGE`, etc.)
- [ ] Add `MERIDIAN/state.json` with initial empty state schema

### Step 1 — Orchestration script (`orchestrate.py`)
- [ ] Load agent system prompt from `FOUNDERS_OS_AGENT_SYSTEM.md` by agent ID
- [ ] Load relevant context files (state, recent outputs, handoff queue)
- [ ] Call Claude API (`claude-sonnet-4-6`) with assembled prompt
- [ ] Write output to correct agent folder with timestamp
- [ ] Update `MERIDIAN/state.json` with run result
- [ ] Scan output for `[ESCALATE TO FOUNDER]` and trigger escalation handler

### Step 2 — MERIDIAN scheduling config (`MERIDIAN/schedule.json`)
- [ ] Define per-agent cadence (daily / weekly / monthly / on-handoff)
- [ ] Define dependency order (ATLAS → CANVAS → FORGE chain, etc.)
- [ ] Define which context files each agent receives as input

### Step 3 — GitHub Actions workflows
- [ ] `meridian-daily.yml` — runs MERIDIAN at 08:00 CET, reads state, dispatches due tasks
- [ ] `agents-weekly.yml` — full agent sweep every Sunday night
- [ ] `escalation-handler.yml` — monitors for `[ESCALATE TO FOUNDER]` in any committed output

### Step 4 — Escalation handler
- [ ] Parse agent outputs for escalation flag
- [ ] Open GitHub Issue with: agent name, task, full context, output, action required
- [ ] Mark task as `BLOCKED` in `state.json` until issue is closed

### Step 5 — Static dashboard (optional, iFastNet)
- [ ] Single HTML file fetching `MERIDIAN/state.json` from public repo
- [ ] Renders: agent statuses, last run timestamps, open escalations, recent outputs
- [ ] No backend — pure client-side fetch + render

---

## Suggestions (MERIDIAN perspective)

### Make MERIDIAN's weekly briefing the north star output
The single most valuable automated output is MERIDIAN's weekly founder briefing — one page covering wins, risks, decisions needed, and next week's priorities. Everything else (individual agent tasks) feeds into this. Design the system around producing this briefing reliably, and the rest follows.

### Start with two agents before wiring all eleven
ATLAS (research, competitive intel) and HERALD (investor update draft) are the two agents with the clearest, most self-contained weekly tasks and the highest value-to-effort ratio. Wire those first, prove the pipeline, then extend to the others.

### Use Claude's extended thinking for MERIDIAN only
MERIDIAN's orchestration decisions (priority setting, conflict resolution, stage-gate assessment) benefit from deeper reasoning. All other agents can use standard mode. This keeps API costs low while giving the orchestrator the quality it needs.

### Version the agent system file
As agents are refined through actual runs, `FOUNDERS_OS_AGENT_SYSTEM.md` will need updates. Introduce versioning (`v1.0`, `v1.1`) and a changelog section at the top so MERIDIAN can reference the version it was trained on and flag when agent definitions have changed.

### Build the escalation handler before the scheduler
An autonomous system that runs tasks without an escalation path is dangerous — it will hit blockers and spin. Build the escalation mechanism first, test it, then activate the scheduler.

### Consider a `FOUNDER_RESPONSES/` folder as the input channel
Rather than monitoring GitHub Issues (which requires API polling), a simpler pattern: the founder drops a markdown file into `FOUNDER_RESPONSES/YYYY-MM-DD-response.md` and the next MERIDIAN run picks it up. Git push = signal to continue. Simpler, more auditable.

---

## Build order summary

```
1. Standalone repo (clean)
2. orchestrate.py (core runtime)
3. MERIDIAN/schedule.json (cadence config)
4. escalation handler (safety first)
5. GitHub Actions workflows (scheduler)
6. Wire ATLAS + HERALD as pilot agents
7. Validate full loop: task → output → handoff → MERIDIAN → escalation
8. Extend to all 11 agents
9. Static dashboard (optional)
```

---

*Updated: April 2026 · Next review: after standalone repo is created*
