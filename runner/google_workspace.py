from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ArtifactRecord:
    artifact_type: str
    title: str
    local_path: str
    google_drive_id: str = ""
    google_doc_id: str = ""


class DriveAdapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def upload_file(self, record: ArtifactRecord) -> ArtifactRecord:
        record.google_drive_id = record.google_drive_id or "stub-drive-id"
        return record


class DocsAdapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def create_or_update_doc(self, record: ArtifactRecord, markdown_body: str) -> ArtifactRecord:
        _ = markdown_body
        record.google_doc_id = record.google_doc_id or "stub-doc-id"
        return record


class GmailAdapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def send_threaded_message(self, subject: str, body_markdown: str, thread_key: str = "") -> dict[str, str]:
        _ = body_markdown
        return {
            "subject": subject,
            "thread_key": thread_key or "stub-thread-key",
            "delivery_status": "stubbed",
        }

    def ingest_replies(self) -> list[dict[str, str]]:
        return []
