# Founders OS — Codex Runtime Implementation Plan

## Goal

Turn this repo into a Codex-native autonomous operating layer for Founders OS with:

- event-driven 24/7 dispatch
- lean token controls
- Google Workspace mirroring
- email-first founder communication
- GitHub Actions as unattended scheduler

## What is implemented in this repo now

### Runtime contracts and configs
- Codex-first entrypoint docs
- event + heartbeat scheduling schema
- expanded canonical state schema
- communication and Google Workspace config stubs
- token-policy and model-profile config stubs

### Runtime scaffolding
- `runner/orchestrate.py` for dispatch planning and run request assembly
- `runner/communications.py` for email-first communication contracts
- `runner/google_workspace.py` for Drive / Docs / Gmail adapter scaffolding

### Operations scaffolding
- workflow scaffolds for heartbeat dispatch and daily digest checks
- publish checklist and runtime contract docs

## Remaining implementation work

### 1. Real Codex execution
- connect the dispatcher output to the production Codex invocation path
- persist real run results back into `outputs/state.json`
- write output, handoff, and escalation artifacts from live runs

### 2. Founder email ingestion
- connect Gmail inbox reads to `ingest_responses`
- map replies to escalation IDs and digest threads
- normalize inbound founder responses into repo state

### 3. Google artifact mirroring
- authenticate Drive / Docs / Gmail adapters
- create or update mirrored documents for founder-facing outputs
- persist returned Google IDs into output metadata and state

### 4. Budget accounting
- record actual token usage and cost from model responses
- enforce per-agent caps and throttle behavior
- add summarization cache for long-lived context

## Delivery order

1. Wire live Codex execution
2. Wire founder email ingestion
3. Wire Google artifact mirroring
4. Add real token accounting
5. Validate publish checklist

## Definition of done

- heartbeat dispatcher identifies due work every 15 minutes
- unchanged context produces a skip, not a rerun
- founder escalations send through email and can be resolved from replies
- founder-facing outputs can be mirrored to Drive / Docs
- schedule, state, and runtime contract remain schema-consistent
