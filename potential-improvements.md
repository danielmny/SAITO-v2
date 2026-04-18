# Potential Improvements For SAITO-v2

This file started as a backlog created from the `CreditBank` workflow on April 17-18, 2026.
It now serves as a live status memo:

- what the `CreditBank` workflow exposed
- what has already been implemented
- what is still incomplete
- what should likely be improved next

## Current Summary

The `CreditBank` workflow forced SAITO-v2 to behave more like a real multi-project founder operating system instead of a static agent harness. That led to substantial runtime improvements:

- manual MERIDIAN is now conversational and stateful
- project files can be populated directly from founder intake
- project kickoff work can fan out across multiple specialists
- founder-priority work can bypass some background throttling
- the runtime now supports a hybrid execution model:
  - event-loop behavior for hot-path founder and handoff work
  - cooldown-governed behavior for background heartbeat and overdue maintenance

The remaining gaps are now less about basic workflow plumbing and more about polish, deeper automation, and clearer founder ergonomics.

## Implemented

### 1. Manual Meridian Is Stateful And Conversational

Implemented:

- intake sessions are persisted in `outputs/state.json`
- MERIDIAN can ask one question at a time
- session progress is resumable
- manual launch now starts with a founder standup plus project-choice flow
- MERIDIAN can continue the last open project or start a new one

Impact:

- the founder flow is no longer a stateless prompt chain
- interrupted intake can resume instead of restarting from scratch

### 2. Project Files Populate Directly From Intake

Implemented:

- completed intake writes:
  - `project.md`
  - `problem.md`
  - `icp.md`
  - `solution.md`
  - `validation.md`
  - `strategy.md`
  - `financials.md`
  - `roadmap.md`
  - `decisions.md`
- project setup artifacts are generated automatically
- `outputs/state.json` is updated during the same flow

Impact:

- there is no longer a separate manual “translate founder answers into project files” step

### 3. Manual Launch UX Is Much More Unified

Implemented:

- `manual-meridian`
- `run-cycle`
- `ingest-and-drain-replies`

Manual founder behavior is now much clearer:

1. launch MERIDIAN
2. see current project standup
3. continue or start new
4. answer questions if needed
5. populate project state
6. accept recommended next actions

Impact:

- the founder experience is much closer to one coherent product

### 4. Planner/Drain Atomicity Exists

Implemented:

- atomic `run-cycle`
- atomic `manual-meridian`
- atomic `ingest-and-drain-replies`

Impact:

- the original planner/drain race from the `CreditBank` workflow is largely removed

### 5. Founder-Priority Execution Exists

Implemented:

- founder-priority handoffs can bypass normal quiet-hours suppression
- founder-priority work can bypass normal cooldown behavior
- kickoff and checkpoint work are treated as hot-path event traffic

Impact:

- a founder session no longer stalls just because it happens during suppressed hours or inside a cooldown window

### 6. Project Kickoff Fan-Out Exists

Implemented:

- automatic first-wave kickoff handoffs after project setup
- research, engineering, product, and finance kickoff work are created automatically
- second-wave work now exists for:
  - sales motion
  - positioning brief
  - MERIDIAN project checkpoint synthesis

Impact:

- a newly defined startup can move from intake into coordinated execution without manual orchestration

### 7. Structured Uncertainty Tracking Exists

Implemented:

- project fields now store structured metadata in state:
  - `status`
  - `confidence`
  - `owner_agent`
  - `next_validation_action`
- stage-aware templates now frame early projects as hypothesis-driven rather than incomplete

Impact:

- uncertainty is now explicit and routable instead of hidden in free text

### 8. Project Identity Handling Improved

Implemented:

- canonical project `name`, `key`, and `slug` separation
- duplicate normalization logic during project upsert

Impact:

- accidental project duplication is less likely

### 9. Recommended Founder Actions Can Be Accepted Inline

Implemented:

- MERIDIAN now proposes action phrases such as:
  - `run kickoff bundle`
  - `run research pass`
  - `run architecture pass`
  - `run product framing pass`
  - `run economics pass`
  - `run project checkpoint`
- founder acceptance creates deterministic handoffs

Impact:

- MERIDIAN now behaves more like an operator and less like a document generator

### 10. Parallel Kickoff Bundles And Threshold Dependencies Exist

Implemented:

- kickoff bundle metadata
- parallel group metadata
- first-wave / second-wave / synthesis-wave structure
- dependency modes:
  - `soft`
  - `any`
  - `all`
- `minimum_dependencies_satisfied`

Impact:

- downstream work no longer has to wait for every upstream agent when partial information is enough

### 11. Founder-Facing Parallel Status Exists

Implemented:

- standup and briefing outputs can now show:
  - queued
  - queued for next window
  - blocked by dependency
  - skipped as unnecessary
  - completed

Impact:

- the founder can see the team fan out instead of inferring run state indirectly

### 12. Hybrid Event-Loop Runtime Exists

Implemented:

- `config/schedule.json` now declares `execution_mode: "hybrid"`
- hot-path founder and handoff work can propagate through multiple plan/drain rounds in one `run-cycle`
- heartbeat and overdue maintenance remain cooldown-governed
- background work is suppressed when the same agent already has live hot-path work

Impact:

- SAITO is more responsive without becoming a fully unbounded event storm

## Partially Implemented

### 13. Multi-Agent Synthesis Exists, But It Is Still Lightweight

Implemented so far:

- MERIDIAN can create and process a `project_checkpoint`
- checkpoint synthesis can run as part of the kickoff flow

Still weak:

- synthesis is still mostly file-and-handoff summarization
- conflict resolution between agent outputs is not deep enough
- project-file mutation from synthesis is still conservative

### 14. Runtime And Product Artifacts Are Cleaner, But Not Fully Separated

Implemented so far:

- project knowledge files live under `projects/{slug}/`
- project outputs live under `projects/{slug}/outputs/{AGENT}/`

Still weak:

- runtime manifests still accumulate heavily under `runtime/`
- founder-facing repo surfaces still mix operational and debugging artifacts
- cleanup/archival policy is not strong enough

### 15. Output Naming Is Better, But Not Fully Normalized

Implemented so far:

- project/task artifact naming is more stable than before

Still weak:

- some older or edge-case output filenames are still low-quality
- naming consistency across legacy artifacts and new artifacts is not complete

## Still Open

### 16. True Chat-Native Persistence Is Not Complete

Current state:

- the runtime supports conversational flows well
- this Codex conversation can simulate the intended founder experience

Still missing:

- a first-class runtime bridge where this conversation itself is the canonical founder reply transport
- full elimination of file-backed founder reply machinery under the hood

Why it matters:

- this is still the biggest gap between the intended product experience and the repo-native runtime implementation

### 17. Automatic “Skip Already Answered Questions” Is Not Fully Generalized

Current state:

- MERIDIAN can resume stateful intake
- some project-choice and continue flows already avoid restarting the whole intake

Still missing:

- universal field-by-field skip logic derived from existing project files and structured state
- fully reliable resume behavior for partially refined existing projects

Why it matters:

- refining an existing startup should feel like editing live memory, not re-running an intake form

### 18. Bundle-Level Execution Policy Is Still Basic

Current state:

- founder-priority bundle work can propagate quickly
- threshold dependencies exist

Still missing:

- stronger bundle-level policies such as:
  - run the whole bundle now
  - defer the whole bundle together
  - partially run only if the bundle explicitly allows it

Why it matters:

- coordinated startup work should feel intentional, not opportunistic

### 19. State Reconciliation And Session Auditability Can Improve Further

Current state:

- founder session summaries exist
- state tracks more session and project metadata than before

Still missing:

- cleaner audit views for:
  - what changed in project files
  - which runs completed in a founder session
  - which work remains blocked
  - what the net effect of a session was

Why it matters:

- founder sessions should be easy to continue, inspect, and trust later

### 20. Background Scheduling Still Needs Product Tuning

Current state:

- the hybrid model is now in place

Still missing:

- tuning of:
  - heartbeat frequency
  - overdue sweep policy
  - max event-loop iterations
  - when background work should be resumed after hot-path bursts

Why it matters:

- hybrid mode is directionally correct, but its operating parameters still need experience-based tuning

## Suggested Future Improvements

### A. Build A True Chat-Native Founder Adapter

Highest-value product improvement still open.

Goal:

- make the live founder conversation the canonical intake/status/action channel
- remove the conceptual need for reply files during normal founder use

### B. Let MERIDIAN Update Project Files During Synthesis

Goal:

- use project checkpoints not just to summarize outputs
- also propose or apply structured updates back into project knowledge files when confidence is high enough

### C. Add Stronger Bundle Lifecycle Controls

Goal:

- bundle states like:
  - planned
  - launched
  - partially complete
  - waiting for enough inputs
  - synthesized
  - archived

### D. Add Automatic Project Refinement Mode

Goal:

- detect what is already known in a project
- ask only delta questions
- refine the project memory rather than re-running intake logic

### E. Add Runtime Artifact Retention And Cleanup Policy

Goal:

- archive or compact old `runtime/results` and `runtime/requests`
- preserve auditability without drowning the repo in execution debris

### F. Improve Founder-Facing Synthesis Quality

Goal:

- better conflict detection
- clearer “what changed / what still disagrees / what needs decision”
- stronger executive-summary style outputs

### G. Add Real Event Source Integration Later

Goal:

- keep the same repo contracts
- eventually let a web app, Slack adapter, or other realtime surface drive the hybrid runtime directly

## Highest-Value Next Improvements

If SAITO-v2 is improved incrementally from here, the most valuable next steps are:

1. Build a true chat-native founder adapter.
2. Add project refinement mode that skips already answered fields automatically.
3. Strengthen MERIDIAN checkpoint synthesis so it can update project memory more intelligently.
4. Add lifecycle management and retention for runtime artifacts.
5. Tune hybrid runtime thresholds using real usage rather than static defaults.

Those five changes are the most likely to improve founder experience now that the core workflow plumbing is largely in place.
