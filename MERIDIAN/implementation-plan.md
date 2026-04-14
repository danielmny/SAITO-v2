# Founders OS — Codex Runtime Implementation Plan

## Goal

Turn this repo into a Codex-native autonomous operating layer for Founders OS with:

- event-driven 24/7 dispatch
- lean token controls
- optional Google Workspace mirroring
- file-first founder communication
- GitHub Actions as unattended scheduler

## Remaining implementation work

### 1. Real Codex execution
- connect the dispatcher output to the production Codex invocation path
- persist real run results back into `outputs/state.json`
- write output, handoff, and escalation artifacts from live runs

### 2. Founder reply ingestion
- normalize file-based founder replies from `inputs/founder-replies/`
- map replies to escalation IDs and digest threads
- normalize inbound founder responses into repo state

### 3. Google artifact mirroring
- implement real Drive / Docs / Gmail adapters behind feature flags
- create or update mirrored documents for founder-facing outputs
- persist returned Google IDs into output metadata and state

### 4. Budget accounting
- record actual token usage and cost from model responses
- enforce per-agent caps and throttle behavior
- add summarization cache for long-lived context

## Delivery order

1. Wire live Codex execution
2. Harden founder reply ingestion and escalation resolution
3. Wire Google artifact mirroring
4. Add real token accounting
5. Validate publish checklist

## Definition of done

- heartbeat dispatcher identifies due work every 15 minutes
- unchanged context produces a skip, not a rerun
- founder escalations can be delivered through the file channel and resolved from replies
- founder-facing outputs can optionally be mirrored to Drive / Docs later
- schedule, state, and runtime contract remain schema-consistent
