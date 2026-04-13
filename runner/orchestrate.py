from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class RunRequest:
    agent_id: str
    trigger_type: str
    reason: str
    run_timestamp: str
    changed_context: list[str]
    instance_path: str


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_timestamp(value: str) -> datetime:
    if not value:
        return datetime.min
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def compute_context_hash(changed_context: list[str]) -> str:
    payload = "\n".join(sorted(changed_context))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def can_run_agent(
    agent_id: str,
    schedule_cfg: dict[str, Any],
    state_cfg: dict[str, Any],
    now: datetime,
    changed_context: list[str],
) -> tuple[bool, str]:
    agent_schedule = schedule_cfg["agents"][agent_id]
    agent_state = state_cfg["agents"][agent_id]

    if not agent_schedule.get("enabled", False):
        return False, "disabled"

    cooldown_until = parse_timestamp(agent_state.get("cooldown_until", ""))
    if cooldown_until != datetime.min and cooldown_until > now:
        return False, "cooldown_active"

    daily_runs = agent_state.get("run_budget", {}).get("runs_today", 0)
    max_runs = agent_schedule.get("max_runs_per_day", 0)
    if max_runs and daily_runs >= max_runs:
        return False, "daily_run_cap_reached"

    trigger_modes = set(agent_schedule.get("trigger_mode", []))
    if changed_context and "event" in trigger_modes:
        next_hash = compute_context_hash(changed_context)
        if agent_schedule.get("run_if_changed", True) and next_hash == agent_state.get("context_hash", ""):
            return False, "context_unchanged"
        return True, "event"

    if "heartbeat" in trigger_modes:
        last_run = parse_timestamp(agent_state.get("last_run", ""))
        heartbeat_minutes = agent_schedule.get("heartbeat_minutes", 0)
        if last_run == datetime.min or now - last_run >= timedelta(minutes=heartbeat_minutes):
            return True, "heartbeat"
        return False, "heartbeat_not_due"

    return False, "no_trigger"


def build_run_request(
    agent_id: str,
    trigger_type: str,
    reason: str,
    changed_context: list[str],
    instance_path: Path,
    now: datetime,
) -> RunRequest:
    return RunRequest(
        agent_id=agent_id,
        trigger_type=trigger_type,
        reason=reason,
        run_timestamp=now.isoformat(),
        changed_context=changed_context,
        instance_path=str(instance_path),
    )


def planner(args: argparse.Namespace) -> int:
    schedule_cfg = load_json(Path(args.schedule))
    state_cfg = load_json(Path(args.state))
    now = datetime.now().astimezone()
    changed_context = args.changed_context or []
    due: list[RunRequest] = []

    for agent_id in schedule_cfg["agents"]:
        should_run, reason = can_run_agent(agent_id, schedule_cfg, state_cfg, now, changed_context)
        if should_run:
            due.append(
                build_run_request(
                    agent_id=agent_id,
                    trigger_type=reason,
                    reason=args.reason or f"{reason}_dispatch",
                    changed_context=changed_context,
                    instance_path=Path(args.instance_path),
                    now=now,
                )
            )

    output = [request.__dict__ for request in due]
    print(json.dumps(output, indent=2))
    return 0


def run_once(args: argparse.Namespace) -> int:
    now = datetime.now().astimezone()
    request = build_run_request(
        agent_id=args.agent,
        trigger_type=args.trigger_type,
        reason=args.reason,
        changed_context=args.changed_context or [],
        instance_path=Path(args.instance_path),
        now=now,
    )
    print(json.dumps(request.__dict__, indent=2))
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Founders OS dispatcher scaffold")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = {
        "instance_path": {
            "default": ".",
            "help": "Path to the Founders OS instance workspace.",
        },
        "changed_context": {
            "nargs": "*",
            "default": [],
            "help": "Changed files or logical context inputs that triggered evaluation.",
        },
        "reason": {
            "default": "",
            "help": "Human-readable trigger reason.",
        },
    }

    plan_parser = subparsers.add_parser("plan", help="Print due run requests.")
    plan_parser.add_argument("--schedule", default="config/schedule.json")
    plan_parser.add_argument("--state", default="outputs/state.json")
    plan_parser.add_argument("--instance-path", **common["instance_path"])
    plan_parser.add_argument("--reason", **common["reason"])
    plan_parser.add_argument("--changed-context", **common["changed_context"])
    plan_parser.set_defaults(func=planner)

    once_parser = subparsers.add_parser("run-once", help="Print a single run request.")
    once_parser.add_argument("--agent", required=True)
    once_parser.add_argument("--trigger-type", default="manual")
    once_parser.add_argument("--reason", default="manual_run")
    once_parser.add_argument("--instance-path", **common["instance_path"])
    once_parser.add_argument("--changed-context", **common["changed_context"])
    once_parser.set_defaults(func=run_once)

    return parser


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
