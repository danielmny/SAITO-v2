# Runtime Contract

## Dispatch request

Every runtime invocation should be reducible to this request object:

```json
{
  "agent_id": "MERIDIAN",
  "trigger_type": "heartbeat",
  "reason": "pending escalation review",
  "run_timestamp": "2026-04-13T17:00:00+02:00",
  "changed_context": ["outputs/escalations/pending/ESC-001.md"],
  "instance_path": "/workspace/founders-os"
}
```

## State ownership

- Repo state is canonical.
- `MERIDIAN` is the only shared-state normalizer.
- Specialist agents can propose local metadata updates, but normalized agent status, communications, and external artifact records must flow through canonical state rules.

## Output metadata

Founder-facing outputs may include this optional front matter:

```yaml
artifact_type: founder_briefing
audience: founder
source_run_id: run-2026-04-13-meridian-001
google_drive_id: ""
google_doc_id: ""
communication_thread_id: ""
```

## Communication contract

Outbound communication is channel-agnostic:

- `message_type`
- `subject`
- `body_markdown`
- `attachments`
- `thread_key`
- `requires_reply`
- `reply_deadline`

Inbound communication must be normalized into:

- linked escalation or digest thread
- founder response timestamp
- delivery and ingestion status
- optional unblock action

## Lean-token rules

- unchanged effective context should yield a skip
- only changed inputs and recent relevant outputs may be injected
- long-running history should be summarized into rolling notes
- budgets should be enforced per agent and per day
