from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


class AdapterUnavailableError(RuntimeError):
    pass


def load_google_workspace_config(instance_path: Path) -> dict[str, Any]:
    return json.loads((instance_path / "config/google-workspace.json").read_text(encoding="utf-8"))


def require_enabled(config: dict[str, Any], feature_name: str) -> None:
    if not config.get("enabled", False):
        raise AdapterUnavailableError(f"{feature_name} is disabled in config/google-workspace.json")


def require_value(value: str, feature_name: str, field_name: str) -> None:
    if not value:
        raise AdapterUnavailableError(f"{feature_name} requires a non-empty `{field_name}` setting")


@dataclass
class ArtifactRecord:
    artifact_type: str
    title: str
    local_path: str
    project: str = "startup_ops"
    task_type: str = "artifact"
    origin: str = "runtime"
    google_drive_id: str = ""
    google_doc_id: str = ""


class DriveAdapter:
    def __init__(self, root_config: dict[str, Any]) -> None:
        require_enabled(root_config, "Google Workspace")
        self.config = root_config.get("google_drive", {})
        require_value(self.config.get("shared_drive_id", ""), "google_drive", "google_drive.shared_drive_id")

    def upload_file(self, record: ArtifactRecord) -> ArtifactRecord:
        if not Path(record.local_path).exists():
            raise AdapterUnavailableError(f"Cannot upload missing file: {record.local_path}")
        raise AdapterUnavailableError("google_drive adapter is not implemented yet; canonical repo state remains unchanged")


class DocsAdapter:
    def __init__(self, root_config: dict[str, Any]) -> None:
        require_enabled(root_config, "Google Workspace")
        self.config = root_config.get("google_docs", {})
        require_enabled(self.config, "google_docs")

    def create_or_update_doc(self, record: ArtifactRecord, markdown_body: str) -> ArtifactRecord:
        if not markdown_body.strip():
            raise AdapterUnavailableError("google_docs requires non-empty markdown content")
        raise AdapterUnavailableError("google_docs adapter is not implemented yet; canonical repo state remains unchanged")


class GmailAdapter:
    def __init__(self, gmail_config: dict[str, Any]) -> None:
        require_enabled(gmail_config, "gmail")
        require_value(gmail_config.get("mailbox", ""), "gmail", "gmail.mailbox")
        self.config = gmail_config

    def send_threaded_message(self, subject: str, body_markdown: str, thread_key: str = "") -> dict[str, str]:
        if not subject.strip():
            raise AdapterUnavailableError("gmail requires a non-empty subject")
        if not body_markdown.strip():
            raise AdapterUnavailableError("gmail requires a non-empty body")
        raise AdapterUnavailableError("gmail adapter is not implemented yet; no external delivery was attempted")

    def ingest_replies(self) -> list[dict[str, str]]:
        raise AdapterUnavailableError("gmail reply ingestion is not implemented yet")
