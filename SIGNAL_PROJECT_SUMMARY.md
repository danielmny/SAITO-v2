# SIGNAL — Full Project Summary

## 1. What SIGNAL Is
SIGNAL is a job market intelligence platform that matches job seekers to companies based on psychographic and cultural alignment — not keyword matching.

Two sides of the match:
- Job seekers — profiled via CV analysis + 6-question psychographic interview → 8-dimensional vector
- Companies — profiled via multi-source public intelligence (Glassdoor, Reddit, job postings, website) → 8-dimensional culture vector

## 2. Architecture Plan

Stack:
- Frontend: React + D3 / Three.js (3D point cloud)
- Backend API: FastAPI (Python)
- Database: PostgreSQL
- AI: Claude API (claude-sonnet-4-6)
- Scrapers: Playwright + Greenhouse/Lever public APIs
- Auth: JWT (to be added)
- Hosting: Railway or Fly.io

Core modules:
1. CV Analysis Engine — Claude-powered, rule-based fallback
2. Psychographic Interview — 6 questions → 8-dim vector
3. Company Intelligence Engine — multi-source scraping + Claude synthesis
4. Match Map — 3D point cloud visualisation

Database tables: companies, jobs, job_evidence, seeker_profiles, company_culture

## 3. The 8 Psychographic Dimensions

Both seekers and companies scored on same axes (1–10):
- autonomy_need / autonomy_granted
- ambiguity_tolerance / ambiguity_level
- mission_orientation / mission_strength
- growth_urgency / growth_pace
- security_need / job_security
- stress_resilience / pressure_level
- collaboration_preference / collaboration_density
- hierarchy_comfort / hierarchy_flatness

Match score: Σ( weight_i × (1 - |seeker_dim_i - company_dim_i| / 10) )
Autonomy and ambiguity weighted 1.5×; mission 1.3×; security and growth 1.2×.

## 4. Seeker Archetypes
- Founding Operator: autonomy ≥ 8 AND ambiguity ≥ 7
- Mission Builder: mission ≥ 8
- Steady Architect: security ≥ 7
- Revenue Hunter: stress resilience ≥ 8 AND growth urgency ≥ 7
- Deep Craftsman: default

## 5. Existing Repo State
Repo: danielmny/signal-mvp (private) — created March 31, 2026

Already built:
- FastAPI backend: main.py, db.py, db_models.py
- PostgreSQL via Docker Compose
- Google Careers scraper (working)
- CV ingestion: PDF / DOCX / TXT
- Rule-based CV analysis
- Seeker layer: saved/viewed jobs + companies, /me/ endpoints
- Minimal Vite + React frontend

Known gaps:
- No psychographic profile storage
- No company culture vectors
- Limited job sources
- No auth, not deployed

## 6. Implementation — Steps 1–4

Step 1: Claude-powered CV Analysis (backend/app/cv_analysis.py)
- Replaces rule-based parsing with Claude API call
- Returns 15-field JSON schema including psychographic_signals, archetype, green_flags, watch_items, narrative_summary
- Falls back to rule engine if API key absent

Step 2: Psychographic Profile Layer
- New DB tables: seeker_profiles, company_culture
- New API endpoints: GET/POST /me/profile, POST /me/profile/cv, GET /me/match

Step 3: Greenhouse + Lever Scrapers
- Greenhouse: 15 default boards (Stripe, Notion, Linear, Vercel, Figma, etc.)
- Lever: 15 default companies (Netflix, Cloudflare, OpenAI, Anthropic, etc.)
- Both use free unauthenticated public APIs

Step 4: Company Intelligence Synthesis
- Pipeline: collect signals → Claude synthesis → 8-dim culture vector → write to DB
- New endpoints: POST /ingest/greenhouse, /ingest/lever, /ingest/culture/{id}, GET /me/match

## 7. Operational Pipeline
1. POST /ingest/greenhouse + /ingest/lever (no API key needed)
2. POST /ingest/culture/all (needs ANTHROPIC_API_KEY)
3. POST /me/profile/cv + /me/profile/answers
4. GET /me/match

## 8. Next Steps
- Step 5: Deploy to Railway
- Step 6: Wire 3D match map frontend to real API
- Step 7: Real Glassdoor + Reddit signal collection

## 9. What Was Deliberately Skipped
- Oracle Playwright scraping (too much effort)
- Celery / Redis job queues (premature)
- Vector embeddings / pgvector (fix data quality first)
- Auth / multi-user (single-user MVP sufficient)
