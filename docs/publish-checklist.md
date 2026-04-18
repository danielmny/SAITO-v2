# Publish Checklist

## Validation

1. Search for stale operational references tied to deprecated runtime wording, UI-only workflow assumptions, and legacy founder-response paths.
2. Verify `README.md`, `AGENTS.md`, `config/schedule.json`, and `outputs/state.json` agree on:
   - scheduler of record
   - execution mode
   - heartbeat interval
   - core active agents
   - source-of-truth rules
   - founder intake model
   - manual-launch standup / continue-or-start-new behavior
   - project/task metadata model
3. Verify file-first communication and disabled-by-default Google Workspace do not conflict.
4. Verify the dispatcher skip logic respects unchanged context, hybrid hot-path behavior, cooldowns, and max-runs-per-day.
5. Verify `runtime/requests/`, `runtime/queue/`, and `runtime/results/` are used consistently by the planner and serial runner.
6. Verify the runtime contracts are portable into a future standalone web app without redesign.

## Commit groups

1. `docs/runtime`
2. `schemas/config`
3. `integration-design`
4. `ops/publish`

## Push target

- branch: `codex/codex-runtime-refactor` when available, otherwise a non-conflicting Codex-prefixed branch
- repo: `danielmny/SAITO-v2`

## Pre-push sanity check

- run `make plan`, `make drain`, or `make validate`
- run `make run-cycle` for a hybrid-runtime sanity check when dispatch logic changed
- run Python compilation for `runner/`
- inspect `git diff --stat`
- verify no unrelated local changes are being included
- inspect at least one canonical handoff and one state snapshot for project/task metadata completeness
