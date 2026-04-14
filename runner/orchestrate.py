from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    trigger_type: str = "event"
    changed_context: list[str] | None = None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_state(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "outputs/state.json")


def load_schedule(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "config/schedule.json")


def normalize_agent_id(agent_id: str) -> str:
    legacy_aliases = {
        "MERIDIAN": "MERIDIAN-ORCHESTRATOR",
        "ATLAS": "ATLAS-RESEARCH",
        "FORGE": "FORGE-ENGINEERING",
        "CURRENT": "CURRENT-SALES",
        "LEDGER": "LEDGER-FINANCE",
        "NEXUS": "NEXUS-TALENT",
        "COUNSEL": "COUNSEL-LEGAL",
        "VECTOR": "VECTOR-ANALYTICS",
        "HERALD": "HERALD-COMMS",
        "CANVAS": "CANVAS-PRODUCT",
        "MARKETING": "MARKETING-BRAND",
    }
    return legacy_aliases.get(agent_id, agent_id)


def parse_iso8601(timestamp: str) -> datetime | None:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        return None


def dependency_satisfied(agent_state: dict[str, Any]) -> bool:
    return bool(agent_state.get("last_success")) or agent_state.get("status") in {"success", "completed"}


def can_plan_agent(
    agent_id: str,
    event: dict[str, Any],
    state: dict[str, Any],
    schedule: dict[str, Any],
    now: datetime,
) -> tuple[bool, str]:
    schedule_entry = schedule.get("agents", {}).get(agent_id)
    if not schedule_entry:
        return False, "agent_not_in_schedule"
    if not schedule_entry.get("enabled", False):
        return False, "agent_disabled"
    if event.get("type") and "event" not in schedule_entry.get("trigger_mode", []):
        return False, "event_trigger_not_enabled"

    agent_state = state.get("agents", {}).get(agent_id, {})
    runs_today = agent_state.get("run_budget", {}).get("runs_today", 0)
    max_runs = schedule_entry.get("max_runs_per_day")
    if max_runs is not None and runs_today >= max_runs:
        return False, "max_runs_reached"

    cooldown_minutes = schedule_entry.get("cooldown_minutes", 0)
    last_run = parse_iso8601(agent_state.get("last_run", ""))
    if last_run is not None and cooldown_minutes:
        if now < last_run + timedelta(minutes=cooldown_minutes):
            return False, "cooldown_active"

    for dependency in schedule_entry.get("depends_on", []):
        dependency_state = state.get("agents", {}).get(dependency, {})
        if not dependency_satisfied(dependency_state):
            return False, f"blocked_on_{dependency}"

    return True, "eligible"


def plan_runs(instance_path: Path) -> list[PlannedRun]:
    state = load_state(instance_path)
    schedule = load_schedule(instance_path)
    planned: list[PlannedRun] = []
    now = datetime.now(timezone.utc)

    for event in state.get("pending_events", []):
        agent_id = normalize_agent_id(event.get("to", "MERIDIAN-ORCHESTRATOR"))
        should_plan, _reason = can_plan_agent(agent_id, event, state, schedule, now)
        if not should_plan:
            continue

        planned.append(
            PlannedRun(
                agent_id=agent_id,
                project=event.get("project", "startup_ops"),
                task_type=event.get("task_type", "status_review"),
                origin=event.get("type", "event"),
                reason=event.get("handoff_id", "pending_event"),
                trigger_type="event",
                changed_context=[
                    f"outputs/handoffs/{event.get('handoff_id')}.md",
                ]
                if event.get("handoff_id")
                else [],
            )
        )

    return planned


def run_once(request: DispatchRequest) -> dict[str, Any]:
    return {
        "status": "not_implemented",
        "message": "Runtime execution scaffold exists, but agent execution is still document-driven.",
        "request": request.__dict__,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Founders OS runtime scaffold")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Plan eligible runs from state and schedule")
    plan_parser.add_argument("--instance-path", default=".")
    plan_parser.add_argument("--schedule", default="config/schedule.json")
    plan_parser.add_argument("--state", default="outputs/state.json")

    run_once_parser = subparsers.add_parser("run-once", help="Build a one-off dispatch request")
    run_once_parser.add_argument("--agent", required=True)
    run_once_parser.add_argument("--trigger-type", required=True)
    run_once_parser.add_argument("--reason", required=True)
    run_once_parser.add_argument("--instance-path", default=".")
    run_once_parser.add_argument("--project", default="startup_ops")
    run_once_parser.add_argument("--task-type", default="status_review")
    run_once_parser.add_argument("--origin", default="scheduler")
    run_once_parser.add_argument("--changed-context", action="append", default=[])

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "plan":
        repo = Path(args.instance_path).resolve()
        print(
            json.dumps(
                {
                    "status": "scaffolded",
                    "planned_runs": [run.__dict__ for run in plan_runs(repo)],
                    "note": "Planner enforces enabled flags, trigger modes, cooldowns, daily caps, and dependency readiness.",
                },
                indent=2,
            )
        )
    elif args.command == "run-once":
        repo = Path(args.instance_path).resolve()
        request = DispatchRequest(
            agent_id=normalize_agent_id(args.agent),
            trigger_type=args.trigger_type,
            reason=args.reason,
            run_timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
            changed_context=args.changed_context,
            instance_path=str(repo),
            project=args.project,
            task_type=args.task_type,
            origin=args.origin,
        )
        print(json.dumps(run_once(request), indent=2))
