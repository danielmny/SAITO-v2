# Publish Checklist

## Validation

1. Search for stale operational references tied to deprecated runtime wording, UI-only workflow assumptions, and legacy founder-response paths.
2. Verify `README.md`, `AGENTS.md`, `config/schedule.json`, and `outputs/state.json` agree on:
   - scheduler of record
   - heartbeat interval
   - core active agents
   - source-of-truth rules
   - founder intake model
   - project/task metadata model
3. Verify email-first communication and Google Workspace mirroring do not conflict.
4. Verify the dispatcher skip logic respects unchanged context, cooldowns, and max-runs-per-day.
5. Verify the runtime contracts are portable into a future standalone web app without redesign.

## Commit groups

1. `docs/runtime`
2. `schemas/config`
3. `integration-design`
4. `ops/publish`

## Push target

- branch: `codex/codex-runtime-refactor` when available, otherwise a non-conflicting Codex-prefixed branch
- repo: `danielmny/startup-ai-team-cowork-GPT`

## Pre-push sanity check

- run dispatcher planner locally
- run Python compilation for `runner/`
- inspect `git diff --stat`
- verify no unrelated local changes are being included
- inspect at least one canonical handoff and one state snapshot for project/task metadata completeness
