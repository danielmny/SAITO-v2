# Company Brief — Startup AI Team - One

> This file is the authoritative company context for all Founders OS agents.
> Update this file when company facts change. Do not embed company details in agent prompts.

---

## The Company

**Name:** Startup AI Team - One
**Type:** AI-operated startup team / venture studio runtime
**Stage:** PRE-SEED operating system with active project execution

**What it does:** Runs a 24/7 team of specialized AI startup operators across multiple clearly defined projects. The agents are expected to behave like a real startup team: compartmentalize work by project, route tasks to the right functional owners, keep project status visible, and sustain fast, coordinated execution.

**Founder interaction model:** The founder starts with `MERIDIAN-ORCHESTRATOR`. MERIDIAN should ask which project the founder wants to work on, whether the founder wants startup-wide status, project/task status, or new execution, and what the founder wants to do next. MERIDIAN then routes work to the relevant specialists and returns synthesized results.

**Repo:** `danielmny/startup-ai-team-one` (private)

## Project Portfolio

All work must be scoped to one named project or to startup-wide operating work.

### Project 1 — SIGNAL

**Type:** Job market intelligence platform
**Stage:** PRE-SEED (MVP built, moving toward seed fundraise)
**What it does:** Matches job seekers to companies based on psychographic and cultural alignment rather than keyword matching.
**Stack:** FastAPI (Python) · PostgreSQL · React + Vite · LLM API · Playwright scrapers · Railway/Fly.io (planned)
**Status:** Active product build and GTM preparation

### Project 2 — Startup AI Team Runtime

**Type:** Internal operating system / workflow project
**What it does:** Improves the team runtime itself: orchestration, handoffs, scheduling, founder communication, and project coordination.
**Status:** Active internal operations project

## Operating Rules

- The team works 24/7 across the active project portfolio.
- Projects must be clearly compartmentalized. Cross-project work must be explicit.
- MERIDIAN is responsible for founder intake, project selection, routing, and synthesis.
- Specialist agents should only act within the scope of their project handoff or clearly defined operating responsibilities.
- The current repo is the canonical backend model for a future standalone web app.
- The future web app should be able to support founder control, autonomous execution, and dashboards using the same project/task/run/handoff contracts defined in this repo.

## SIGNAL Project Context

### The 8 Psychographic Dimensions

Both seekers and companies scored on same axes (1–10):

| Seeker | Company |
|--------|---------|
| autonomy_need | autonomy_granted |
| ambiguity_tolerance | ambiguity_level |
| mission_orientation | mission_strength |
| growth_urgency | growth_pace |
| security_need | job_security |
| stress_resilience | pressure_level |
| collaboration_preference | collaboration_density |
| hierarchy_comfort | hierarchy_flatness |

Match score: `Σ( weight_i × (1 - |seeker_i - company_i| / 10) )`
Weights: autonomy + ambiguity = 1.5×, mission = 1.3×, security + growth = 1.2×

### Seeker Archetypes

| Archetype | Condition |
|-----------|-----------|
| Founding Operator | autonomy ≥ 8 AND ambiguity ≥ 7 |
| Mission Builder | mission ≥ 8 |
| Steady Architect | security ≥ 7 |
| Revenue Hunter | stress_resilience ≥ 8 AND growth_urgency ≥ 7 |
| Deep Craftsman | default |

### Current Build State

Already built: FastAPI backend · PostgreSQL · Google Careers scraper · CV ingestion (PDF/DOCX/TXT) · rule-based CV analysis · seeker layer (/me/ endpoints) · minimal React frontend

Gaps: no psychographic profile storage · no company culture vectors · no auth · not deployed

### Implementation Roadmap

| Step | Task | Status |
|------|------|--------|
| 1 | LLM-powered CV Analysis | Planned |
| 2 | Psychographic Profile Layer (DB + API) | Planned |
| 3 | Greenhouse + Lever Scrapers | Planned |
| 4 | Company Intelligence Synthesis | Planned |
| 5 | Deploy to Railway | Planned |
| 6 | Wire 3D match map to real API | Planned |
| 7 | Glassdoor + Reddit signal collection | Planned |

### Current Stage: PRE-SEED

Active priorities:
1. Complete implementation Steps 1–4 (working psychographic match)
2. Get 10 paying or LOI-signed early customers
3. Prepare seed fundraising materials
4. Define and track North Star Metric

Stage-gate to SEED requires: MVP with real users · 3–5 paying customers · pitch deck · 50+ investor list · data room ready

---

*Last updated: April 2026*
