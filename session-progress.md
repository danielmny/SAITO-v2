# MERIDIAN — Session Progress
*Founders OS v1.0 · April 2026*

> Historical architecture note from an earlier phase of the project.
> It is retained for context, but the current canonical runtime lives under `runner/`, `config/`, `README.md`, and `docs/`.

---

## Session summary

This session established the strategic and technical foundation that later evolved into the current repo-native runtime.

### What was clarified

- **Founders OS and SIGNAL are separate concerns.** Founders OS is a reusable agent system. SIGNAL (danielmny/signal-mvp) is one company running on top of it. The two repos must not be conflated or cross-linked.
- **At that point the system was doc-only.** CLAUDE.md + FOUNDERS_OS_AGENT_SYSTEM.md were prompt/context files, not a runtime. The repo has since moved to a repo-native planner/queue harness.
- **The goal is real automation:** agents running tasks independently, handing off structured outputs to each other, with MERIDIAN orchestrating, scheduling, tracking progress, flagging issues, and escalating to the founder only when a human decision is genuinely required.

### What was designed this session

A complete automation architecture:

- **Runtime:** Python orchestration script (`orchestrate.py`) with repo-native planning and serial queue execution
- **Scheduler:** GitHub Actions as scheduler only
- **Message bus:** The Git repo itself — agents write structured handoff files, MERIDIAN reads them on next run
- **State persistence:** `MERIDIAN/state.json` — MERIDIAN's working memory across runs
- **Escalation handler:** Scans outputs for `[ESCALATE TO FOUNDER]` and routes through the configured communication backend
- **Static dashboard (optional):** HTML on iFastNet reading `state.json` from the public repo

### Deployment decisions made

| Layer | Tool | Cost |
|-------|------|------|
| Orchestration script | Python (local or GitHub Actions) | Free |
| Scheduler | GitHub Actions cron | Free |
| Message bus | Git repo file system | Free |
| State | `state.json` in repo | Free |
| Escalations | Repo files + founder comms backend | Free |
| Dashboard | Static HTML on iFastNet | Free |
| Claude API | Anthropic (existing plan) | Existing |

### Pending founder decision

> **Repo structure:** Should agent outputs be committed to the same repo as the Founders OS system files, or a separate outputs repo? Separating keeps the system clean and allows the outputs repo to be public (for the dashboard) without exposing system prompts.

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
├── SIGNAL_PROJECT_SUMMARY.md     ← SIGNAL-specific
├── founders_peer_group_agreement.md
└── README.md
```
