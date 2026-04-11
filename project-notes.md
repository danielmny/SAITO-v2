# MERIDIAN — Project Notes
*Founders OS v1.0 · April 2026*

---

## Core architectural decisions

### 1. No orchestration framework
CrewAI, LangChain, and similar frameworks were evaluated and rejected. Reasons:
- The agent system in `FOUNDERS_OS_AGENT_SYSTEM.md` is already better-structured than what those frameworks generate
- They add dependency weight, abstraction overhead, and cost without meaningful benefit for this use case
- A thin Python script calling the Claude API directly gives full control over context injection, output routing, and state management

### 2. Git as message bus
Agent handoffs use the repo file system. Each agent writes a structured markdown file in its folder following the `FROM / TO / RE / CONTEXT / OUTPUT / ACTION REQUIRED` format defined in `FOUNDERS_OS_AGENT_SYSTEM.md`. MERIDIAN reads pending handoff files at the start of each orchestration run and dispatches tasks accordingly.

This means:
- Every handoff is version-controlled and auditable
- No queue infrastructure required
- Human can inspect and intervene at any point by editing files directly

### 3. MERIDIAN as the only stateful component
All other agents are stateless — they receive a task + context, produce an output, done. MERIDIAN alone maintains `state.json` across runs. This keeps the system simple and debuggable.

### 4. Escalation as a hard gate
`[ESCALATE TO FOUNDER]` is not advisory — it halts the relevant task thread until the founder responds. The escalation handler opens a GitHub Issue with full context. The founder's response (a comment or a new file pushed) unblocks the next run.

### 5. Founders OS ≠ SIGNAL
These are separate repos with separate concerns. SIGNAL is one company running on Founders OS. The standalone Founders OS repo should contain no SIGNAL-specific content.

---

## Key design principles (carry forward into build)

- **Agents are prompt + context, not code.** Each agent's "intelligence" lives in `FOUNDERS_OS_AGENT_SYSTEM.md`. The orchestration layer is plumbing, not logic.
- **Outputs are always markdown.** No JSON agent outputs (except `state.json`). Everything human-readable, everything committable.
- **Cadence is configuration.** Agent run frequencies (daily / weekly / monthly) are defined in a schedule config, not hardcoded in workflows. MERIDIAN reads the config and dispatches accordingly.
- **Never invent data.** Agents must flag assumptions and propose validation steps rather than fabricating metrics, competitive intelligence, or financial figures.

---

## Open questions (not yet resolved)

| Question | Who decides | Status |
|----------|------------|--------|
| Same repo or separate outputs repo? | Founder | Open |
| Which email/notification channel for escalations? | Founder | Open |
| Should the static dashboard be built now or post-MVP? | Founder | Deferred |
| GitHub account to create standalone repo under? | Founder | Open |
| Should `FOUNDERS_OS_AGENT_SYSTEM.md` be versioned (v1.1, v2.0) as agents are refined? | MERIDIAN | Recommended yes |
