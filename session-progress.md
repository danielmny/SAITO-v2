# MERIDIAN — Session Progress
*Founders OS v1.0 · April 2026*

---

## Session summary

This session established the strategic and technical foundation for turning Founders OS from a document system into a live, automated multi-agent runtime.

### What was clarified

- **Founders OS and SIGNAL are separate concerns.** Founders OS is a standalone, reusable agent system. SIGNAL (danielmny/signal-mvp) is one company running on top of it. The two repos must not be conflated or cross-linked.
- **The current system is doc-only.** CLAUDE.md + FOUNDERS_OS_AGENT_SYSTEM.md are prompt/context files, not a runtime. Agents do not currently run autonomously.
- **The goal is real automation:** agents running tasks independently, handing off structured outputs to each other, with MERIDIAN orchestrating, scheduling, tracking progress, flagging issues, and escalating to the founder only when a human decision is genuinely required.

### What was designed this session

A complete automation architecture:

- **Runtime:** Python orchestration script (`orchestrate.py`) calling the Claude API directly — no CrewAI, no LangChain
- **Scheduler:** GitHub Actions (free tier, 2,000 min/month) with two workflows: daily MERIDIAN run, weekly full-agent sweep
- **Message bus:** The Git repo itself — agents write structured handoff files, MERIDIAN reads them on next run
- **State persistence:** `MERIDIAN/state.json` — MERIDIAN's working memory across runs
- **Escalation handler:** Scans all outputs for `[ESCALATE TO FOUNDER]`, opens a GitHub Issue or sends email
- **Static dashboard (optional):** HTML on iFastNet reading `state.json` from the public repo

### Deployment decisions made

| Layer | Tool | Cost |
|-------|------|------|
| Orchestration script | Python (local or GitHub Actions) | Free |
| Scheduler | GitHub Actions cron | Free |
| Message bus | Git repo file system | Free |
| State | `state.json` in repo | Free |
| Escalations | GitHub Issues | Free |
| Dashboard | Static HTML on iFastNet | Free |
| Claude API | Anthropic (existing plan) | Existing |

### Pending founder decision

> **Repo structure:** Should agent outputs be committed to the same repo as the Founders OS system files, or a separate outputs repo? Separating keeps the system clean and allows the outputs repo to be public (for the dashboard) without exposing system prompts.

### Next action agreed (not yet executed)

Create a standalone clone of this repo called **"Startup AI Team - standalone"** — a clean, SIGNAL-agnostic version of Founders OS ready to be the base for the automation build. *(Paused pending founder instruction on GitHub vs. local creation.)*

---

## Repo structure (as received)

```
/
├── .claude/
│   ├── hooks/session-start.sh
│   └── settings.json
├── MERIDIAN/             ← agent output folder (empty, needs creation)
├── .gitignore
├── .markdownlint.json
├── CLAUDE.md             ← Claude Code entry point
├── FOUNDERS_OS_AGENT_SYSTEM.md   ← full agent definitions
├── SIGNAL_PROJECT_SUMMARY.md     ← SIGNAL-specific (to be removed in standalone)
├── founders_peer_group_agreement.md
└── README.md
```
