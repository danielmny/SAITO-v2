# Company Brief — SIGNAL

> This file is the authoritative company context for all Founders OS agents.
> Update this file when company facts change. Do not embed company details in agent prompts.

---

## The Company

**Name:** SIGNAL
**Type:** Job market intelligence platform
**Stage:** PRE-SEED (MVP built, moving toward seed fundraise)

**What it does:** Matches job seekers to companies based on psychographic and cultural alignment — not keyword matching. Both sides are profiled on 8 psychological dimensions and matched via a weighted vector similarity score.

**Two sides of the match:**
- Job seekers — CV analysis + 6-question psychographic interview → 8-dimensional vector
- Companies — multi-source public intelligence (Glassdoor, Reddit, job postings) → 8-dimensional culture vector

**Repo:** `danielmny/signal-mvp` (private, created March 31 2026)

**Stack:** FastAPI (Python) · PostgreSQL · React + Vite · LLM API · Playwright scrapers · Railway/Fly.io (planned)

---

## The 8 Psychographic Dimensions

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

---

## Seeker Archetypes

| Archetype | Condition |
|-----------|-----------|
| Founding Operator | autonomy ≥ 8 AND ambiguity ≥ 7 |
| Mission Builder | mission ≥ 8 |
| Steady Architect | security ≥ 7 |
| Revenue Hunter | stress_resilience ≥ 8 AND growth_urgency ≥ 7 |
| Deep Craftsman | default |

---

## Current Build State

Already built: FastAPI backend · PostgreSQL · Google Careers scraper · CV ingestion (PDF/DOCX/TXT) · rule-based CV analysis · seeker layer (/me/ endpoints) · minimal React frontend

Gaps: no psychographic profile storage · no company culture vectors · no auth · not deployed

---

## Implementation Roadmap

| Step | Task | Status |
|------|------|--------|
| 1 | LLM-powered CV Analysis | Planned |
| 2 | Psychographic Profile Layer (DB + API) | Planned |
| 3 | Greenhouse + Lever Scrapers | Planned |
| 4 | Company Intelligence Synthesis | Planned |
| 5 | Deploy to Railway | Planned |
| 6 | Wire 3D match map to real API | Planned |
| 7 | Glassdoor + Reddit signal collection | Planned |

---

## Current Stage: PRE-SEED

Active priorities:
1. Complete implementation Steps 1–4 (working psychographic match)
2. Get 10 paying or LOI-signed early customers
3. Prepare seed fundraising materials
4. Define and track North Star Metric

Stage-gate to SEED requires: MVP with real users · 3–5 paying customers · pitch deck · 50+ investor list · data room ready

---

*Last updated: April 2026*
