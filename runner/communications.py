from __future__ import annotations

import hashlib
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner.google_workspace import AdapterUnavailableError, GmailAdapter, load_google_workspace_config


@dataclass
class Message:
    message_type: str
    subject: str
    body_markdown: str
    project: str = "startup_ops"
    task_type: str = "communication"
    origin: str = "runtime"
    attachments: list[str] = field(default_factory=list)
    thread_key: str = ""
    requires_reply: bool = False
    reply_deadline: str = ""


class CommunicationChannel(ABC):
    @abstractmethod
    def send_digest(self, message: Message) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def send_escalation(self, message: Message) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def send_reply_needed(self, message: Message) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def ingest_responses(self) -> list[dict[str, Any]]:
        raise NotImplementedError


def load_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def read_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    _, remainder = text.split("---\n", 1)
    if "\n---\n" not in remainder:
        return {}, text
    front_matter_text, body = remainder.split("\n---\n", 1)
    front_matter: dict[str, str] = {}
    for line in front_matter_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        front_matter[key.strip()] = value.strip()
    return front_matter, body


class FileChannel(CommunicationChannel):
    def __init__(self, instance_path: Path) -> None:
        self.instance_path = instance_path
        self.outbox_dir = instance_path / "outputs/communications/outbox"
        self.replies_dir = instance_path / "inputs/founder-replies"
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self.replies_dir.mkdir(parents=True, exist_ok=True)

    def _write_message(self, message: Message) -> dict[str, Any]:
        sent_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        digest = hashlib.sha256(
            f"{message.message_type}|{message.subject}|{message.thread_key}|{sent_at}".encode("utf-8")
        ).hexdigest()[:8]
        filename = f"{sent_at.replace(':', '').replace('+00:00', 'Z').replace('-', '')}-{message.message_type}-{digest}.md"
        path = self.outbox_dir / filename
        front_matter = [
            "---",
            f"message_type: {message.message_type}",
            f"subject: {message.subject}",
            f"project: {message.project}",
            f"task_type: {message.task_type}",
            f"origin: {message.origin}",
            f"thread_key: {message.thread_key}",
            f"requires_reply: {'true' if message.requires_reply else 'false'}",
            f"reply_deadline: {message.reply_deadline}",
            f"sent_at: {sent_at}",
            "---",
            "",
        ]
        path.write_text("\n".join(front_matter) + message.body_markdown.strip() + "\n", encoding="utf-8")
        return {
            "channel": "file",
            "delivery_status": "written_to_file",
            "path": path.relative_to(self.instance_path).as_posix(),
            "thread_key": message.thread_key,
            "sent_at": sent_at,
        }

    def send_digest(self, message: Message) -> dict[str, Any]:
        return self._write_message(message)

    def send_escalation(self, message: Message) -> dict[str, Any]:
        return self._write_message(message)

    def send_reply_needed(self, message: Message) -> dict[str, Any]:
        return self._write_message(message)

    def ingest_responses(self) -> list[dict[str, Any]]:
        replies: list[dict[str, Any]] = []
        for reply_path in sorted(path for path in self.replies_dir.iterdir() if path.is_file() and path.name != ".gitkeep"):
            front_matter, body = read_front_matter(reply_path)
            reply_id = front_matter.get("reply_id", reply_path.stem)
            replies.append(
                {
                    "reply_id": reply_id,
                    "project": front_matter.get("project", "startup_ops"),
                    "thread_key": front_matter.get("thread_key", ""),
                    "source_path": reply_path.relative_to(self.instance_path).as_posix(),
                    "body_markdown": body.strip(),
                }
            )
        return replies


class EmailChannel(CommunicationChannel):
    def __init__(self, config: dict[str, Any], gmail_config: dict[str, Any]) -> None:
        self.config = config
        self.adapter = GmailAdapter(gmail_config)

    def _deliver(self, message: Message) -> dict[str, Any]:
        return self.adapter.send_threaded_message(
            subject=message.subject,
            body_markdown=message.body_markdown,
            thread_key=message.thread_key,
        )

    def send_digest(self, message: Message) -> dict[str, Any]:
        return self._deliver(message)

    def send_escalation(self, message: Message) -> dict[str, Any]:
        return self._deliver(message)

    def send_reply_needed(self, message: Message) -> dict[str, Any]:
        return self._deliver(message)

    def ingest_responses(self) -> list[dict[str, Any]]:
        return self.adapter.ingest_replies()


class SlackChannel(CommunicationChannel):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def _not_configured(self, message: Message) -> dict[str, Any]:
        return {
            "channel": "slack",
            "delivery_status": "not_configured",
            "subject": message.subject,
            "thread_key": message.thread_key,
        }

    def send_digest(self, message: Message) -> dict[str, Any]:
        return self._not_configured(message)

    def send_escalation(self, message: Message) -> dict[str, Any]:
        return self._not_configured(message)

    def send_reply_needed(self, message: Message) -> dict[str, Any]:
        return self._not_configured(message)

    def ingest_responses(self) -> list[dict[str, Any]]:
        return []


def get_default_channel(instance_path: Path) -> CommunicationChannel:
    communications_config = load_json(instance_path / "config/communications.json")
    google_config = load_google_workspace_config(instance_path)
    default_channel_name = communications_config.get("default_channel", "file")

    email_config = communications_config.get("channels", {}).get("email", {})
    gmail_config = google_config.get("gmail", {})
    email_usable = (
        default_channel_name == "email"
        and email_config.get("enabled", False)
        and gmail_config.get("enabled", False)
        and bool(gmail_config.get("mailbox"))
    )
    if email_usable:
        try:
            return EmailChannel(email_config, gmail_config)
        except AdapterUnavailableError:
            return FileChannel(instance_path)

    slack_config = communications_config.get("channels", {}).get("slack", {})
    if default_channel_name == "slack" and slack_config.get("enabled", False):
        return SlackChannel(slack_config)

    return FileChannel(instance_path)
