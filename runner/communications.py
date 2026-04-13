from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    message_type: str
    subject: str
    body_markdown: str
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


class EmailChannel(CommunicationChannel):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def _payload(self, message: Message) -> dict[str, Any]:
        return {
            "channel": "email",
            "provider": self.config.get("provider", "gmail"),
            "subject": message.subject,
            "thread_key": message.thread_key,
            "requires_reply": message.requires_reply,
            "reply_deadline": message.reply_deadline,
            "delivery_status": "stubbed",
        }

    def send_digest(self, message: Message) -> dict[str, Any]:
        return self._payload(message)

    def send_escalation(self, message: Message) -> dict[str, Any]:
        return self._payload(message)

    def send_reply_needed(self, message: Message) -> dict[str, Any]:
        return self._payload(message)

    def ingest_responses(self) -> list[dict[str, Any]]:
        return []


class SlackChannel(CommunicationChannel):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def send_digest(self, message: Message) -> dict[str, Any]:
        return {"channel": "slack", "delivery_status": "not_implemented", "thread_key": message.thread_key}

    def send_escalation(self, message: Message) -> dict[str, Any]:
        return {"channel": "slack", "delivery_status": "not_implemented", "thread_key": message.thread_key}

    def send_reply_needed(self, message: Message) -> dict[str, Any]:
        return {"channel": "slack", "delivery_status": "not_implemented", "thread_key": message.thread_key}

    def ingest_responses(self) -> list[dict[str, Any]]:
        return []
