# Founders OS — Cowork Edition

A multi-agent AI system that simulates a complete startup team — from idea stage through seed close. Runs natively in **Claude Cowork** with each agent firing on its own schedule as an independent session.

## The Agent Team

| ID | Agent | Function | Schedule |
|----|-------|----------|----------|
| A-00 | MERIDIAN | Orchestrator | Daily 8:00 AM |
| A-01 | ATLAS | Market Research | Monday 7:00 AM |
| A-02 | CANVAS | Product | Tuesday 7:00 AM |
| A-03 | FORGE | Engineering | Daily 9:00 AM + Wednesday 7:00 AM |
| A-04 | MARKETING | Brand & Demand Gen | Tuesday 7:00 AM |
| A-05 | CURRENT | Sales | Daily 8:05 AM (weekdays) |
| A-06 | LEDGER | Finance & Fundraising | Thursday 7:00 AM |
| A-07 | NEXUS | Talent & Hiring | On-demand |
| A-08 | COUNSEL | Legal | On-demand |
| A-09 | VECTOR | Analytics & Growth | Thursday 7:00 AM |
| A-10 | HERALD | Investor Relations & PR | Friday 7:00 AM |

## Stage Coverage

- **IDEA** — Problem validation, concept shaping, initial team structure
- **PRE-SEED** — MVP scoping, early customers, pitch narrative
- **SEED** — Fundraising execution, team build, GTM, financial controls

## Active Company: SIGNAL

The current instance of Founders OS is operating for **SIGNAL** — a job market intelligence platform that matches job seekers to companies based on psychographic and cultural alignment, not keyword matching.

- **Stage:** PRE-SEED (MVP built, moving toward seed)
- **Stack:** FastAPI · PostgreSQL · React + Vite · Claude API · Playwright
- **Repo:** `danielmny/signal-mvp`

See [`config/company-brief.md`](./config/company-brief.md) for the full company context, and [`SIGNAL_PROJECT_SUMMARY.md`](./SIGNAL_PROJECT_SUMMARY.md) for the technical reference.

## File Structure

```
├── CLAUDE.md                        ← Cowork entry point — read this first
├── FOUNDERS_OS_AGENT_SYSTEM.md      ← Full agent definitions, task inventories, stage gates
├── agents/                          ← Per-agent scheduled task prompts
├── config/
│   ├── company-brief.md             ← Company context (single source of truth)
│   ├── agent-skills.json            ← Skill assignments per agent
│   └── schedule.json                ← Cadence reference
├── outputs/
│   ├── state.json                   ← Live system state (MERIDIAN-owned)
│   ├── handoffs/                    ← Inter-agent handoff queue
│   ├── escalations/                 ← Pending and resolved escalations
│   └── {AGENT_NAME}/                ← Agent output files (one folder per agent)
├── FOUNDER_RESPONSES/               ← Drop responses here to unblock escalations
└── SIGNAL_PROJECT_SUMMARY.md        ← SIGNAL technical reference
```

## How It Works

1. Each agent runs as an independent Claude Code session on its own cron schedule
2. MERIDIAN runs daily to read all agent outputs, resolve escalations, and produce the founder briefing
3. Agents communicate via handoff files in `outputs/handoffs/`
4. When an agent needs a human decision, it writes `[ESCALATE TO FOUNDER]` — MERIDIAN detects it and creates a pending escalation
5. Drop your response in `FOUNDER_RESPONSES/RE: ESC-{ID}.md` to unblock the relevant agent

## Managing Agents

All scheduled tasks are visible in the **Scheduled** sidebar in Claude Code. To run any agent manually, click **Run now** on the corresponding task:

- `MERIDIAN (Orchestrator)` — daily briefing
- `ATLAS (Market Research)` — competitive intel
- `CANVAS (Product)` — roadmap + backlog
- `FORGE (Engineering)` — standup or weekly review
- `MARKETING (Brand & Demand Gen)` — content + messaging
- `CURRENT (Sales)` — pipeline update
- `LEDGER (Finance & Fundraising)` — runway + investor pipeline
- `VECTOR (Analytics & Growth)` — KPIs + experiments
- `HERALD (Investor Relations & PR)` — investor update + pitch deck
- `NEXUS (Talent & Hiring)` — on-demand
- `COUNSEL (Legal)` — on-demand

---

*Founders OS v2.0 · Cowork Edition · April 2026*
