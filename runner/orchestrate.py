from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass
class DispatchRequest:
    agent_id: str
    trigger_type: str
    reason: str
    run_timestamp: str
    changed_context: list[str]
    instance_path: str
    project: str = "startup_ops"
    task_type: str = "status_review"
    origin: str = "scheduler"


@dataclass
class PlannedRun:
    agent_id: str
    project: str
    task_type: str
    origin: str
    reason: str


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_state(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "outputs/state.json")


def load_schedule(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "config/schedule.json")


def plan_runs(instance_path: Path) -> list[PlannedRun]:
    state = load_state(instance_path)
    _schedule = load_schedule(instance_path)
    planned: list[PlannedRun] = []

    for event in state.get("pending_events", []):
        planned.append(
            PlannedRun(
                agent_id=event.get("to", "MERIDIAN-ORCHESTRATOR"),
                project=event.get("project", "startup_ops"),
                task_type=event.get("task_type", "status_review"),
                origin=event.get("type", "event"),
                reason=event.get("handoff_id", "pending_event"),
            )
        )

    return planned


def run_once(request: DispatchRequest) -> dict[str, Any]:
    return {
        "status": "not_implemented",
        "message": "Runtime execution scaffold exists, but agent execution is still document-driven.",
        "request": request.__dict__,
    }


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[1]
    print(
        json.dumps(
            {
                "status": "scaffolded",
                "planned_runs": [run.__dict__ for run in plan_runs(repo)],
                "note": "This file is the future standalone app/backend orchestration entrypoint.",
            },
            indent=2,
        )
    )
