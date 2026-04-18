# Security Audit
*SAITO-v2 · April 18, 2026*

## Scope

This audit covered the repo-native runtime and its core security surfaces:

- `runner/orchestrate.py`
- `runner/communications.py`
- `runner/specialists.py`
- `runner/projects.py`
- `runner/google_workspace.py`
- runtime state, handoff, and founder-reply flows

This was a code-review audit, not a penetration test. It focused on trust boundaries, file integrity, command execution surfaces, and data handling inside the current repo-native runtime.

## Overall Assessment

Current posture: **moderate risk for a local/file-native prototype, not yet hardened for multi-user or externally writable environments.**

Good news:

- no direct remote-code-execution path was found
- no use of `eval`, `exec`, unsafe deserialization, or shell command interpolation was found in the runtime
- project slug generation strips path separators and reduces path-traversal risk during project creation
- Google Workspace adapters fail closed when disabled or unconfigured

Main remaining concern:

- canonical state and runtime artifacts still live as plain repo files, which is acceptable for a local prototype but still not ideal for broader operational environments

## Remediated In This Pass

### Front Matter Injection Hardening

Implemented:

- front-matter values are now sanitized before being written in:
  - `runner/communications.py`
  - `runner/orchestrate.py`
  - `runner/specialists.py`

Why it mattered:

- before this change, newline-bearing values could corrupt or spoof markdown front matter fields

### Reply Archive Path Validation

Implemented:

- `archive_reply_file()` now verifies the resolved source path stays inside `inputs/founder-replies/` before moving it

Why it mattered:

- this closes a weak path-trust assumption in the founder-reply archive path

### Founder Reply Authentication And Session Binding

Implemented:

- founder replies now require:
  - `thread_key`
  - `session_id`
  - `reply_token`
  - `reply_signature`
- reply signatures are validated against `SAITO_FOUNDER_REPLY_SECRET`
- replies must match an active thread challenge stored in state
- stale, unsigned, replayed, expired, or mismatched replies are rejected
- a signing helper now exists:
  - `python3 runner/orchestrate.py sign-founder-reply --instance-path . --reply-file inputs/founder-replies/<file>.md`

Why it mattered:

- this moves founder authority from “whoever can drop a file into the inbox” toward a signed, session-bound trust model

## Open Findings

### Medium — Founder Trust Still Depends On Local Secret And Filesystem Control

Affected areas:

- `runner/communications.py`
- `runner/orchestrate.py`

What happens:

- the runtime now verifies signed replies and session-bound tokens
- however, the trust model still depends on:
  - a local environment secret
  - local filesystem control
  - local process integrity

Why this matters:

- this is significantly safer than the original inbox-only design
- it is still not equivalent to a fully authenticated remote identity provider or managed access control layer

Recommended fix:

- eventually replace or wrap the file-native founder channel with a real authenticated transport
- keep using signed reply envelopes even after transport changes

### Medium — Sensitive Operating State Is Stored In Plain Repo Files

Affected areas:

- `outputs/state.json`
- `runtime/results/`
- `runtime/requests/`
- project output artifacts under `projects/{slug}/outputs/`

What happens:

- founder interactions, project summaries, routing history, and runtime metadata are stored as plain text / JSON in the repo workspace

Why this matters:

- this is correct for auditability, but it also means project-sensitive operational data is easy to exfiltrate if the workspace is exposed
- the risk increases if these files are ever pushed accidentally, mirrored broadly, or used in a multi-user environment

Recommended fix:

- formalize retention and cleanup policy for runtime manifests
- classify which artifacts are canonical and which are ephemeral
- consider redaction or segregation for founder-sensitive artifacts if the runtime expands beyond local single-user use

### Low — Front Matter Parsing Is Still Lightweight

Affected areas:

- `runner/communications.py`
- `runner/orchestrate.py`
- `runner/specialists.py`

What happens:

- front matter is now sanitized on write and critical founder replies are validated more strictly
- but parsing is still based on simple line splitting rather than a schema-aware document parser

Why this matters:

- this is now mainly a data-integrity and maintenance concern rather than an immediate security gap

Recommended fix:

- introduce a stricter schema validator for canonical artifacts
- reject malformed front matter instead of silently accepting partial parses

## Lower-Risk Observations

- The runtime depends heavily on local filesystem trust. That is safer now that replies are signed and session-bound, but it is still a design constraint rather than a production-grade security model.
- `run-cycle` hybrid propagation improves responsiveness, but it also increases the importance of strong event provenance and replay protection.
- Legacy artifacts remain in the repo. They are mostly operational clutter, but clutter increases the chance of operator confusion and accidental routing mistakes.

## Recommended Security Roadmap

1. Add stricter schema validation for canonical handoff and communication artifacts.
2. Separate durable project memory from ephemeral runtime execution debris.
3. Add retention / pruning policy for `runtime/results/` and `runtime/requests/`.
4. Re-audit once the founder channel is no longer purely file-native.
5. Revisit whether a small local database should replace some ephemeral manifest storage.

## Bottom Line

For a local repo-native prototype, SAITO-v2 is in reasonable shape and does not show obvious code-execution flaws.

The most important remaining weakness is architectural:

- **the system is still a repo-native local runtime, not a fully authenticated multi-user control plane**

That is a manageable posture for the current prototype, but it remains the main constraint before treating SAITO-v2 as a remotely accessible system.
