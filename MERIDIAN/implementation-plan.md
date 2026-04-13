# Founders OS — Standalone Docker Product

## Context
The user has a document-only repo (`startup-ai-team-standalone`) containing an 11-agent AI system definition (Founders OS). The prior session designed an automation architecture but never built it. The goal now is to turn this into a fully autonomous, Dockerized product that runs on a schedule with zero manual intervention and minimal cost (~$2/month in API fees).

---

## What gets built

### 1. Repo cleanup
- Remove `SIGNAL_PROJECT_SUMMARY.md` (SIGNAL-specific, not generic)
- Rename agent `A-04 SIGNAL` → `MARKETING` throughout (name collision with the product company)
- Move core docs into `system/` folder (baked into Docker image, read-only at runtime)
- Rewrite `CLAUDE.md` as a generic Founders OS entry point (strip SIGNAL content)
- Create `config/company-brief.md` — the only file a new founder edits at setup

### 2. File/folder structure
```
startup-ai-team-standalone/
├── Dockerfile                          ← orchestrator container
├── Dockerfile.dashboard               ← dashboard container
├── docker-compose.yml                 ← two services: orchestrator + dashboard
├── .env.example
├── requirements.txt                    ← openai, apscheduler, python-dotenv, smtplib (stdlib)
├── requirements.dashboard.txt         ← fastapi, uvicorn, jinja2, python-multipart
├── orchestrate.py                      ← core runtime entry point
├── agents/
│   ├── loader.py                       ← extracts agent section from FOUNDERS_OS_AGENT_SYSTEM.md by ID
│   ├── runner.py                       ← builds prompt, calls API, writes output
│   ├── escalation.py                   ← detects [ESCALATE TO FOUNDER], writes escalation file, sends email
│   └── scheduler.py                    ← maps schedule.json → APScheduler CronTrigger jobs
├── dashboard/
│   ├── app.py                          ← FastAPI app (read-only views + response submission form)
│   ├── templates/
│   │   ├── index.html                  ← agent status overview
│   │   ├── agent.html                  ← per-agent output history
│   │   ├── escalations.html           ← open + resolved escalations + response form
│   │   └── metrics.html               ← token usage, run history, cost tracker
│   └── static/
│       └── style.css
├── config/
│   ├── schedule.json                   ← per-agent cadence, context files, dependencies
│   ├── models.json                     ← model profile per task type
│   ├── email.json                      ← SMTP config, notification settings, reminder delay
│   └── company-brief.md               ← founder fills this in once at setup
├── system/
│   ├── FOUNDERS_OS_AGENT_SYSTEM.md    ← agent definitions (baked into image)
│   └── CLAUDE.md                      ← generic entry point
└── outputs/                            ← DOCKER VOLUME — shared between both containers
    ├── state.json
    ├── handoffs/
    ├── escalations/
    │   ├── pending/
    │   └── resolved/
    ├── MERIDIAN/
    ├── ATLAS/ … HERALD/
    └── FOUNDER_RESPONSES/             ← founder drops .md files here OR submits via dashboard
```

### 3. Docker setup

**Orchestrator container (`Dockerfile`):** `python:3.12-slim`, copies `orchestrate.py`, `agents/`, `config/`, `system/`. Pre-creates all `outputs/` subdirs. Entrypoint: `python orchestrate.py --daemon`. No exposed ports.

**Dashboard container (`Dockerfile.dashboard`):** `python:3.12-slim`, copies `dashboard/`. Exposes port 8080. Mounts the same `outputs/` volume as read + the `FOUNDER_RESPONSES/` dir as read-write (for response submission). Entrypoint: `uvicorn dashboard.app:app --host 0.0.0.0 --port 8080`.

**docker-compose.yml — two services:**
```yaml
services:
  orchestrator:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - founders-os-data:/app/outputs

  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    restart: unless-stopped
    ports:
      - "8080:8080"
    env_file: .env
    volumes:
      - founders-os-data:/app/outputs   # shared read-write
    depends_on:
      - orchestrator

volumes:
  founders-os-data:
```

Access dashboard at `http://localhost:8080` (or Fly.io/Railway URL).

**Env vars (`.env.example`):**
```
OPENROUTER_API_KEY=
FOUNDERS_OS_TIMEZONE=Europe/London
FOUNDERS_OS_STAGE=PRE-SEED
FOUNDERS_OS_COMPANY_NAME=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=                    # Gmail App Password
NOTIFY_EMAIL=                     # founder's email to receive escalation alerts
ESCALATION_REMINDER_HOURS=24      # resend email if no response after N hours
DASHBOARD_SECRET=                  # optional: simple password to protect dashboard
```

### 4. orchestrate.py — core runtime

**Modes:**
- `--daemon` — starts APScheduler, runs forever, fires agents on schedule
- `--agent ATLAS --cadence weekly` — one-shot for testing/manual runs
- `--run-all-due` — check what's due now and run it
- `--setup` — first-time initialization

**Per-agent execution flow:**
1. `loader.py`: Extract agent section from `FOUNDERS_OS_AGENT_SYSTEM.md` by heading pattern `# A-XX · AGENTNAME`
2. `runner.py`: Build context from `schedule.json`'s `context_files` list (directories → 3 most recent `.md` files; files over 2K tokens → truncate to 1.5K with note)
3. Assemble messages array with agent definition + context + task description + date/stage
4. Call **OpenRouter API** (OpenAI-compatible) with model from `models.json` profile; 3-retry exponential backoff on rate limit
5. `escalation.py`: Scan output for `[ESCALATE TO FOUNDER]` → write escalation file, update state.json, return early (no handoff)
6. `runner.py`: Write output to `outputs/AGENTNAME/YYYY-MM-DD-cadence.md` (timestamped, never overwrite)
7. Write handoff files if `produces_handoff_to` is set in schedule.json
8. `update_state()`: Atomic write to `state.json` (temp file + `os.replace`)

**On every MERIDIAN run:** call `check_founder_responses()` first — scan `FOUNDER_RESPONSES/` for files newer than last MERIDIAN run, match against open escalations by ID, resolve them, reset blocked agents to `pending`.

### 5. config/schedule.json — key design
- Per-agent: `enabled`, `model_profile`, cadences (`daily`/`weekly`/`monthly`), `run_at` (human-readable: `"08:00"`, `"Monday 07:00"`, `"1st 09:00"`), `context_files`, `output_dir`, `max_tokens`, optional `produces_handoff_to`
- `NEXUS` and `COUNSEL` default `enabled: false` (low value at pre-seed; founder flips to `true` in config)

### 6. API backend — OpenRouter + free model options

**Primary: OpenRouter** (`https://openrouter.ai/api/v1`)
- Uses OpenAI-compatible API — `openai` Python package with `base_url` override
- Single env var: `OPENROUTER_API_KEY`
- Free models (`:free` suffix) have rate limits but cost $0

**config/models.json — free-first model profiles:**
| Profile | Model (OpenRouter ID) | Cost | Used by |
|---------|----------------------|------|---------|
| `orchestrator` | `deepseek/deepseek-r1:free` | $0 | MERIDIAN — reasoning model, best free option for orchestration |
| `standard` | `meta-llama/llama-3.3-70b-instruct:free` | $0 | All other agents by default |
| `analytical` | `deepseek/deepseek-chat:free` | $0 | VECTOR |
| `standard_paid` | `mistralai/mistral-small-3.1` | ~$0.10/M | Fallback if free tier rate-limited |

**Estimated cost with free models: $0/month** (only rate limiting applies).
**Fallback cost with paid models: ~$0.50–1/month** (Mistral Small or similar).

**Free model rate limits to be aware of:**
- OpenRouter free models: typically 20 req/min, 200 req/day per model
- With 9 agents running weekly, peak demand is ~9 calls on Sunday night — well within limits
- MERIDIAN daily = 1 call/day — no issue

**Alternative free API backends (configurable via `config/models.json`):**

| Provider | Free tier | Best model | Notes |
|----------|-----------|-----------|-------|
| **Google Gemini** | 1,500 req/day, 1M TPM | `gemini-2.0-flash` | Best free throughput; REST API or `google-generativeai` package |
| **Groq** | 6,000 tokens/min, ~500 req/day | `llama-3.3-70b-versatile` | Extremely fast inference; ideal if agents need quick turnaround |
| **Ollama (local)** | Unlimited | `llama3.3`, `mistral`, `deepseek-r1` | 100% free + private; requires capable GPU/Mac (M-series works well) |

**Recommendation:** Start with OpenRouter free models. If rate limits become an issue on the weekly sweep, rotate between OpenRouter + Groq (both free). Gemini Flash is a strong backup for high-volume runs.

**`requirements.txt` change:** `openai` replaces `anthropic`. The `openai` package works with any OpenAI-compatible endpoint.

### 7. Escalation system + email notifications

**Detection and file creation** (same as before):
- `[ESCALATE TO FOUNDER]` in output → write `outputs/escalations/pending/YYYY-MM-DD-AGENTID-slug.md`
- State.json updated: escalation to `open`, blocking agents listed, agent status `escalated`

**Email notification (in `agents/escalation.py`):**
- On escalation creation: send email to `NOTIFY_EMAIL` via SMTP
- Email contains: agent name, what decision is needed, full escalation context, two response options:
  1. **Dashboard:** click link → fill in response form → submits to `FOUNDER_RESPONSES/`
  2. **File drop:** create `FOUNDER_RESPONSES/YYYY-MM-DD-response.md` starting with `RE: ESC-ID`
- Email is sent via Python `smtplib` (stdlib, no extra package) — works with Gmail App Password or any SMTP

**Reminder emails:**
- MERIDIAN daily run checks `escalations.open` in state.json
- For each open escalation older than `ESCALATION_REMINDER_HOURS` (default 24h) with no response: resend email with "REMINDER" subject prefix
- Max 1 reminder per 24h per escalation to avoid spam
- Reminder count tracked in state.json per escalation

**Response channels (both work):**
1. **Dashboard form** (recommended): `/escalations` page shows pending escalations, each with a text area + submit button. POST saves response as `FOUNDER_RESPONSES/YYYY-MM-DD-ESC-ID-response.md`.
2. **File drop**: founder creates file manually in `FOUNDER_RESPONSES/`

**Resolution:** Same as before — MERIDIAN daily run calls `check_founder_responses()`, matches by `RE: ESC-ID` line, resolves in state.json, resets blocked agents.

### 8. Dashboard (`dashboard/app.py`)

Lightweight FastAPI app. Mounts the shared `outputs/` volume read-only (except `FOUNDER_RESPONSES/`). No database — reads directly from `state.json` and agent output files.

**Routes:**
| Route | What it shows |
|-------|--------------|
| `GET /` | Overview: all agent statuses, last run times, open escalation count, week token usage |
| `GET /agent/{agent_id}` | Agent detail: last 10 outputs listed with timestamps, most recent output rendered as markdown |
| `GET /escalations` | All open escalations with full content + response form; resolved escalations below |
| `POST /escalations/{esc_id}/respond` | Saves response to `FOUNDER_RESPONSES/`; redirects back to escalations page |
| `GET /metrics` | Token usage per agent, estimated cost, run count, weekly/monthly trends |
| `GET /state` | Raw `state.json` as JSON (for debugging) |

**Optional auth:** If `DASHBOARD_SECRET` is set, all routes require a simple password via HTTP Basic Auth (one line with FastAPI's `HTTPBasic`). Sufficient for a founder-only tool.

**Templates:** Jinja2 with minimal CSS — no framework, no build step. Renders markdown agent outputs via a simple `markdown` filter (Python `markdown` package, one extra dependency). Clean, readable, mobile-friendly.

### 9. state.json schema
Tracks: company info + stage, `last_run`, per-agent `last_daily/weekly/monthly` timestamps + run counts + token totals, open/resolved escalations, handoff queue, cumulative API metrics + estimated cost in USD.
Atomic writes only — never corrupt on concurrent access.

### 9. File retention policy (in `write_output`)
- Daily outputs: keep 30 days
- Weekly: keep 6 months
- Monthly+: keep all

---

## Build order

**Phase 0 — Setup**
0a. Clone `startup-ai-team-standalone` → `startup-ai-team-cowork` (local copy for collaborative/cowork variant)
0b. Copy this plan to `MERIDIAN/implementation-plan.md` in both repos and commit

**Phase 1 — Repo cleanup + structure**
1. Remove `SIGNAL_PROJECT_SUMMARY.md`, rename A-04 agent to MARKETING in system files
2. Create all folders (empty), `requirements.txt`, `requirements.dashboard.txt`, `.env.example`, initial `state.json`
3. Create `config/company-brief.md` template, `config/models.json`, `config/schedule.json`, `config/email.json`

**Phase 2 — Core modules**
4. `agents/loader.py` — test against all 11 agents
5. `agents/runner.py` — context builder + OpenRouter API caller; test with ATLAS weekly one-shot
6. `agents/escalation.py` — escalation file writing + SMTP email send; test by forcing trigger
7. Test SMTP: send a test escalation email to verify Gmail App Password works

**Phase 3 — Orchestrator**
8. `orchestrate.py` one-shot mode (`--agent --cadence`)
9. State.json read/write + handoff writing + `check_founder_responses()`
10. Full single-agent loop test: ATLAS → output → handoff → state update
11. Test escalation + reminder: create open escalation, advance clock 25h, verify reminder fires

**Phase 4 — Dashboard**
12. `dashboard/app.py` — all routes + Jinja2 templates
13. `POST /escalations/{esc_id}/respond` — writes to `FOUNDER_RESPONSES/`, verify orchestrator picks it up
14. Test dashboard auth with `DASHBOARD_SECRET`

**Phase 5 — Scheduler + daemon mode**
15. `agents/scheduler.py` — `parse_schedule_trigger` for all `run_at` formats
16. Daemon mode with APScheduler; test with 2-minute trigger locally

**Phase 6 — Docker**
17. `Dockerfile` + `Dockerfile.dashboard` + `docker-compose.yml` (two services, shared volume)
18. Build both, run `docker compose up`, verify both containers start
19. Kill + restart; verify state.json survived on volume
20. Verify dashboard is accessible at `http://localhost:8080`

**Phase 7 — Pilot agents + validation**
21. Full ATLAS → HERALD → MERIDIAN loop
22. Enable remaining agents one at a time via `--agent X --cadence weekly` one-shot

---

## Hosting recommendation (ranked by cost)

| Option | Cost | Notes |
|--------|------|-------|
| **Local Docker** | $0/month | Best starting point; runs on always-on Mac |
| **Fly.io** | $0–$3/month | Recommended production option; persistent volumes, always-on |
| **Railway** | ~$5/month | Simpler UI than Fly.io; slightly more expensive |
| **GitHub Actions cron** | $0 | Requires committing state.json back to repo after each run — workable but messier |

---

## Critical files
- `/Users/d3/Codex/startup-ai-team-standalone/` — target repo (exists, needs cleanup)
- `FOUNDERS_OS_AGENT_SYSTEM.md` — heading pattern `# A-XX · AGENTNAME` used by loader
- `MERIDIAN/session-progress.md`, `project-notes.md`, `next-steps.md` — prior session decisions (binding architectural constraints)

## Verification
1. `docker compose build` succeeds for both services
2. `python orchestrate.py --agent ATLAS --cadence weekly` runs, writes output, updates state.json
3. Trigger an escalation → verify file in `outputs/escalations/pending/` + email received
4. Wait 24h (or manually advance state timestamp) → verify reminder email fires
5. Submit response via dashboard form → verify `FOUNDER_RESPONSES/` file created → MERIDIAN next run resolves it
6. Dashboard at `localhost:8080` shows correct agent statuses, escalation resolved, metrics updated
7. Kill + restart both containers → state.json survives, dashboard still reads correctly
8. Monitor `state.json` metrics after first real weekly sweep to verify $0 cost on free models
