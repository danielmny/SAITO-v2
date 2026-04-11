# Founders OS

A multi-agent AI system that simulates a complete startup team — from idea stage through seed close.

## What It Is

Founders OS gives you an 11-agent AI team, each owning a defined domain, deliverable set, and operating cadence. Feed the system reference documents to Claude Code (or any LLM orchestration layer) and operate as if you have a full founding team on hand.

## The Agent Team

| ID | Agent | Domain |
|----|-------|--------|
| A-00 | MERIDIAN | Orchestration, strategy, OKRs, founder interface |
| A-01 | ATLAS | Market research, competitive intelligence, customer discovery |
| A-02 | CANVAS | Product strategy, roadmap, backlog, user stories |
| A-03 | FORGE | Engineering, architecture, sprint planning, technical debt |
| A-04 | SIGNAL | Marketing, brand, messaging, content, demand generation |
| A-05 | CURRENT | Sales, pipeline, revenue, CRM, playbook |
| A-06 | LEDGER | Finance, fundraising, runway, investor pipeline |
| A-07 | NEXUS | Talent, hiring, HR, culture, onboarding |
| A-08 | COUNSEL | Legal, contracts, IP, compliance, risk |
| A-09 | VECTOR | Data, analytics, growth experiments, KPI dashboard |
| A-10 | HERALD | Comms, investor relations, pitch deck, PR |

## Stage Coverage

- **IDEA** — Problem validation, concept shaping, initial team structure
- **PRE-SEED** — MVP scoping, early customers, pitch narrative
- **SEED** — Fundraising execution, team build, GTM, financial controls

## Active Company: SIGNAL

The current instance of Founders OS is operating for **SIGNAL** — a job market intelligence platform that matches job seekers to companies based on psychographic and cultural alignment, not keyword matching.

- **Stage:** PRE-SEED (MVP built, moving toward seed)
- **Stack:** FastAPI · PostgreSQL · React + Vite · Claude API · Playwright
- **Repo:** `danielmny/signal-mvp`

See [`SIGNAL_PROJECT_SUMMARY.md`](./SIGNAL_PROJECT_SUMMARY.md) for the full product and technical reference.

## Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Claude Code entry point — read this first |
| `FOUNDERS_OS_AGENT_SYSTEM.md` | Full agent definitions, task inventories, stage gates |
| `SIGNAL_PROJECT_SUMMARY.md` | SIGNAL product and technical reference |
| `founders_peer_group_agreement.md` | Founders peer group membership agreement |

## How to Use

1. Open this repo in Claude Code
2. Give a task — Claude will identify the owning agent and operate from that perspective
3. Outputs are declared with `[Acting as: AGENT_NAME]`
4. Cross-agent handoffs use a structured `FROM / TO / RE / CONTEXT / OUTPUT / ACTION REQUIRED` format
5. Human decisions are flagged with `[ESCALATE TO FOUNDER]`

---

*Founders OS v1.0 · April 2026*
