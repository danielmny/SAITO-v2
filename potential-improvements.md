# Potential Improvements For SAITO-v2

This file captures improvements identified from the `CreditBank` workflow that happened on April 17-18, 2026.

## Summary

The `CreditBank` run proved that the multi-project model works, but it also exposed friction in the founder experience, runtime orchestration, and downstream execution. SAITO-v2 can already:

- scaffold a project
- run manual Meridian intake
- populate project files from founder replies
- queue specialist work

But the actual workflow was still more manual and fragmented than it should be.

## 1. Make Manual Meridian Fully Conversational End-To-End

### Problem

Meridian can ask intake questions conversationally in chat, but the runtime still fundamentally expects file-based replies under `inputs/founder-replies/`. In the `CreditBank` workflow, the founder answered in conversation, and that context then had to be translated back into a markdown reply artifact so the runtime could actually populate the files.

### Improvement

Add a first-class conversational intake mode for manual launches where:

- Meridian asks one question at a time in chat
- each answer is persisted automatically
- Meridian tracks progress across the intake sequence
- completion automatically triggers project-file population without requiring a separate reply file

### Why It Matters

This removes the current split between "chat interaction" and "runtime ingestion." Right now the system can do both, but they are not the same flow.

## 2. Add Intake Session State And Resume Logic

### Problem

The conversational intake that happened for `CreditBank` was not backed by durable structured session state. If interrupted, Meridian would not naturally know which question was already answered and which one comes next.

### Improvement

Add an intake-session object to state, for example:

- current project being defined
- current question index
- answers collected so far
- completion status
- source conversation or thread key

### Why It Matters

This would let Meridian resume a partially completed founder intake instead of restarting or relying on manual reconstruction.

## 3. Auto-Trigger Project Population After Conversational Intake

### Problem

After the founder answered the questions conversationally, project-file population still required a separate runtime ingestion step.

### Improvement

When Meridian reaches the last intake question, it should:

- synthesize the collected answers into canonical structured fields
- write the project files immediately
- produce the setup artifact
- update `outputs/state.json`

### Why It Matters

The system should not require a second internal translation step after the founder already finished the intake.

## 4. Unify Manual Launch UX

### Problem

There are currently several manual launch behaviors mixed together:

- `make run-meridian`
- `make drain`
- manual conversational questioning in chat
- file-based founder intake artifacts

This creates ambiguity about what "run Meridian" actually means.

### Improvement

Define one clear manual-launch contract:

1. launch Meridian
2. Meridian asks questions conversationally
3. Meridian persists answers automatically
4. Meridian writes project files
5. Meridian proposes and optionally queues next specialist work

### Why It Matters

Founder-facing behavior should feel like a single product, not a combination of runtime internals.

## 5. Make Planner/Drain Execution Atomic

### Problem

During the `CreditBank` workflow, `ingest-replies` and `drain-queue` raced each other, and `drain-queue` initially processed zero items even though a request had just been queued. The same thing happened again after planning specialist handoffs.

### Improvement

Introduce either:

- a single command that performs `plan + drain` atomically, or
- queue locking / deterministic sequencing so a newly queued request is always visible to the following drain operation

### Why It Matters

The current behavior is subtle and easy to misread as failure, especially during manual founder interaction.

## 6. Add Founder-Priority Override To Quiet Hours

### Problem

After Meridian queued specialist work for `CreditBank`, only `FORGE-ENGINEERING` ran. `ATLAS-RESEARCH`, `CANVAS-PRODUCT`, and `LEDGER-FINANCE` were blocked by quiet-hours suppression even though the founder had just completed intake and expected momentum.

### Improvement

Add scheduling logic such that founder-triggered project work can bypass quiet hours for an initial execution burst, for example:

- allow one immediate founder-priority run per queued specialist
- or let Meridian mark certain handoffs as `critical_founder_flow`

### Why It Matters

A manual founder session should not stall just because it happens during suppressed hours.

## 7. Let Meridian Fan Out The First Specialist Pass Automatically

### Problem

After project setup, the next obvious work items had to be inferred and then queued manually. SAITO-v2 did not automatically turn the newly populated project into a coordinated first-pass execution plan.

### Improvement

After project setup, Meridian should automatically decide whether to create an initial set of handoffs such as:

- research
- product framing
- engineering architecture
- economics / financial model

This should be driven by project stage and missing fields in the project files.

### Why It Matters

A fresh idea-stage project should immediately move from "defined" to "actively investigated."

## 8. Add Missing-Field And Confidence Tracking

### Problem

The `CreditBank` files now contain many intentional unknowns such as:

- undetermined ICP traits
- undetermined wedge
- unknown GTM
- unknown economics
- no locked decisions

Those are valid at idea stage, but SAITO-v2 currently stores them as plain text rather than as structured uncertainty.

### Improvement

Track field quality explicitly, for example:

- `status: known | hypothesis | unknown`
- `confidence: low | medium | high`
- `owner_agent`
- `next_validation_action`

### Why It Matters

This would let Meridian route specialist work based on actual uncertainty, not just free-text interpretation.

## 9. Improve Project Key And Naming Normalization

### Problem

During intake, the founder answered `CrediBank` once and `CreditBank` elsewhere. The runtime eventually updated the existing `CreditBank` project, but the system currently relies on loose normalization and human judgment rather than a clear duplicate-resolution flow.

### Improvement

Add explicit project identity handling:

- detect probable duplicate keys or names
- ask Meridian to confirm merge vs new project
- maintain canonical display name, key, and slug separately

### Why It Matters

This avoids accidental project duplication as the startup portfolio grows.

## 10. Distinguish Runtime Artifacts From Product Artifacts More Cleanly

### Problem

The `CreditBank` workflow created many runtime files:

- queue manifests
- result manifests
- intake artifacts
- project setup artifacts
- handoffs

These are useful, but they can obscure the actual founder-facing project state.

### Improvement

Separate the layers more clearly:

- project knowledge files
- founder-facing summaries
- runtime logs
- scheduling/queue manifests

Potentially move runtime-heavy files further under `runtime/` and keep project folders cleaner.

### Why It Matters

The project folder should read like the startup's operating memory, not a mixed debug surface.

## 11. Fix Output Naming Consistency

### Problem

The generated FORGE output filename for `CreditBank` includes a clipped suffix: `estrator-002`. This works technically, but it is low-quality output naming and reduces trust in the system.

### Improvement

Tighten slug generation and filename construction so:

- agent/task identifiers are stable
- truncation is deliberate
- filenames remain readable

### Why It Matters

Artifact names are part of the product surface. They should look intentional.

## 12. Add Meridian "Recommended Next Actions" That Can Be Accepted Inline

### Problem

Meridian can state recommended next moves, but there is no clear action layer where the founder can simply say "yes, do that" and have the recommended handoffs executed deterministically.

### Improvement

When Meridian finishes setup, it should present actions like:

- run research pass
- run architecture pass
- run product framing pass
- run economics pass

And the founder should be able to approve them inline.

### Why It Matters

This makes Meridian feel like an actual operator rather than just a document generator.

## 13. Add Better Stage-Aware Templates

### Problem

The current project files are generic and work, but they do not adapt much to the fact that `CreditBank` is still at `IDEA` stage. Many sections would benefit from an idea-stage framing rather than looking like incomplete seed-stage planning docs.

### Improvement

Render project files differently by stage:

- IDEA: hypotheses, unknowns, validation questions, early architecture options
- PRE-SEED: chosen wedge, MVP scope, first GTM motion
- SEED: execution metrics, team, financial plan, investor narrative

### Why It Matters

This reduces the feeling that early projects are "missing content" when they are actually "appropriately uncertain."

## 14. Add A Cross-Agent "Project Kickoff" Workflow

### Problem

The first post-intake coordination had to be improvised. There is no explicit kickoff mode that says: "new project created, now establish the first work package across key agents."

### Improvement

Create a `project_kickoff` workflow where Meridian:

- reads all newly populated project files
- identifies the top unknowns
- generates the first coordinated handoffs
- synthesizes returned outputs into a first founder briefing

### Why It Matters

This would make startup creation feel complete, not partial.

## 15. Improve State Reconciliation For Founder Sessions

### Problem

The founder session updated project files and created new outputs, but there is still a lot of implicit state spread across:

- `outputs/state.json`
- project files
- handoffs
- runtime result manifests
- chat context

### Improvement

Add a founder-session summary record that captures:

- what changed
- what project was updated
- what handoffs were created
- which runs completed
- what remains blocked

### Why It Matters

This would make each manual founder session auditable and easy to continue later.

## 16. Parallelize Independent Specialist Work By Default

### Problem

The `CreditBank` workflow showed that SAITO-v2 still behaves too serially in situations where several agents could work at the same time. After project setup, research, product framing, engineering architecture, and economics assessment were all independently useful, but the system only moved one of them forward immediately.

### Improvement

Add a parallel execution model for handoffs that are independent enough to proceed together, especially during early project kickoff. Meridian should explicitly classify downstream work as:

- parallel-safe
- blocked on another agent
- optional follow-on work

Then the planner should enqueue all parallel-safe handoffs in the same cycle.

### Why It Matters

Idea-stage projects move faster when the first investigation wave runs concurrently instead of waiting for one agent at a time unless there is a true dependency.

## 17. Add Dependency-Aware Handoff Grouping

### Problem

Right now the runtime has dependencies in `config/schedule.json`, but it does not appear to reason deeply about which specific handoffs are actually dependent versus merely associated with the same project.

### Improvement

Model handoffs as dependency groups. For example:

- `ATLAS-RESEARCH`, `FORGE-ENGINEERING`, and `LEDGER-FINANCE` can often run in parallel immediately after founder intake
- `CANVAS-PRODUCT` can start in parallel too, but may optionally consume the first research and engineering outputs for a refinement pass
- `MARKETING-BRAND` and `CURRENT-SALES` may wait until ICP and wedge are clearer

The planner should support a first-wave / second-wave structure instead of one undifferentiated queue.

### Why It Matters

This would preserve rigor without forcing unnecessary serialization.

## 18. Add Parallel "Project Kickoff Bundles"

### Problem

After a new project is defined, Meridian currently has to infer and queue handoffs manually. Even when it does so, they are not treated as one coordinated multi-agent bundle.

### Improvement

Create a kickoff bundle concept where Meridian can say:

- kickoff bundle: validation
- kickoff bundle: product-definition
- kickoff bundle: architecture-and-economics

Each bundle would expand into a set of agent runs designed to execute together.

For an idea-stage startup like `CreditBank`, a sensible default kickoff bundle would be:

- `ATLAS-RESEARCH`: market, alternatives, ICP, urgency
- `FORGE-ENGINEERING`: architecture options and trust model
- `LEDGER-FINANCE`: revenue mechanics and unit-economics risks
- `CANVAS-PRODUCT`: wedge, first proof loop, and validation roadmap

### Why It Matters

This would make new-project startup work feel like a coordinated team effort instead of a sequence of isolated dispatches.

## 19. Add Multi-Agent Synthesis After Parallel Runs

### Problem

If more agents run in parallel, Meridian also needs a structured way to merge those outputs back into one founder-facing answer. Otherwise faster execution just creates more fragmented artifacts.

### Improvement

After a parallel run group completes, Meridian should automatically synthesize:

- what each agent found
- where findings agree or conflict
- what changed in the project files
- what the top next decisions are

This should be emitted as a single founder briefing or project checkpoint.

### Why It Matters

Parallelism only improves founder experience if the outputs converge cleanly.

## 20. Add "Wait For Enough Inputs" Thresholds Instead Of Hard Sequential Dependencies

### Problem

Some work should not wait for every upstream agent. For example, product framing might improve with research, but it does not always need to be completely blocked on research before starting.

### Improvement

Introduce softer gating rules such as:

- run immediately
- run after any one of these upstream outputs exists
- run after all of these upstream outputs exist
- run twice: initial draft now, refinement after inputs land

This is especially useful for `CANVAS-PRODUCT`, `CURRENT-SALES`, and `MARKETING-BRAND`.

### Why It Matters

This allows SAITO-v2 to use partial information productively instead of waiting too long for perfect sequencing.

## 21. Add Parallelism-Aware Quiet-Hours Handling

### Problem

Quiet-hours policy currently prevented most of the `CreditBank` follow-on work from running, which effectively collapsed a multi-agent kickoff into a single-agent pass.

### Improvement

If founder-triggered work opens a parallel-safe kickoff bundle, the scheduler should either:

- run the whole bundle immediately once, or
- defer the whole bundle consistently until the next eligible window

It should avoid the current middle state where one agent runs and the rest are silently delayed.

### Why It Matters

Partial execution creates uneven momentum and makes the system feel unreliable.

## 22. Make Parallel Work Visible In Founder-Facing Status

### Problem

The founder currently has to infer which agents ran, which were queued, and which were blocked.

### Improvement

Whenever Meridian launches parallel work, it should present a compact status such as:

- running now
- queued for next eligible window
- blocked by dependency
- skipped as unnecessary

### Why It Matters

If SAITO is going to behave like a startup team, the founder should be able to see the team fan out and understand the state of that work.

## Highest-Value Next Improvements

If SAITO-v2 is improved incrementally, the highest-value next changes are:

1. Make manual Meridian intake fully conversational and stateful.
2. Auto-populate project files directly from that conversation.
3. Auto-fan-out the first specialist pass after project setup, with parallel-safe kickoff bundles.
4. Allow founder-triggered runs to bypass quiet-hour suppression in a coordinated way.
5. Make planner/drain execution atomic.

These five changes would remove most of the friction exposed by the `CreditBank` workflow.
