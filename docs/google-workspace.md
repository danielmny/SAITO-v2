# Google Workspace Integration

## Scope

Google Workspace v1 includes:

- Google Drive for artifact storage
- Google Docs for editable founder-facing documents
- Gmail for founder communications and reply ingestion

Google Sheets, Calendar, and Slides are intentionally out of scope for this pass.

## Source-of-truth policy

- repo markdown and JSON remain canonical
- Google artifacts are mirrors with external IDs written back into repo metadata
- no workflow should require Google Workspace to reconstruct core state
- a future standalone web app may replace or augment these adapters without changing canonical repo contracts

## Initial artifact mapping

| Artifact | Canonical form | Google mirror |
|----------|----------------|---------------|
| MERIDIAN-ORCHESTRATOR founder briefing | Markdown in `outputs/MERIDIAN-ORCHESTRATOR/` | Google Doc |
| HERALD-COMMS investor update | Markdown in `outputs/HERALD-COMMS/` | Google Doc |
| LEDGER finance packet | Markdown / exported file | Google Drive file |
| Escalation packet | Markdown in `outputs/escalations/` | Google Doc + Gmail thread |

## Adapter responsibilities

- `DriveAdapter`: create folders, upload files, return Drive IDs
- `DocsAdapter`: create or update editable documents, return Doc IDs
- `GmailAdapter`: send digests and escalations, ingest replies, return thread IDs

These adapters should remain thin delivery layers over the same project/task/run/communication model used by the core runtime.

## Failure handling

- a failed Google sync must not corrupt canonical repo state
- sync failures should be logged in state and retried later
- agent outputs should still exist locally even if all Google calls fail
