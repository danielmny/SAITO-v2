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

## Initial artifact mapping

| Artifact | Canonical form | Google mirror |
|----------|----------------|---------------|
| MERIDIAN founder briefing | Markdown in `outputs/MERIDIAN/` | Google Doc |
| HERALD investor update | Markdown in `outputs/HERALD/` | Google Doc |
| LEDGER finance packet | Markdown / exported file | Google Drive file |
| Escalation packet | Markdown in `outputs/escalations/` | Google Doc + Gmail thread |

## Adapter responsibilities

- `DriveAdapter`: create folders, upload files, return Drive IDs
- `DocsAdapter`: create or update editable documents, return Doc IDs
- `GmailAdapter`: send digests and escalations, ingest replies, return thread IDs

## Failure handling

- a failed Google sync must not corrupt canonical repo state
- sync failures should be logged in state and retried later
- agent outputs should still exist locally even if all Google calls fail
