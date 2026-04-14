from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner.communications import Message, get_default_channel


ROOT_DIRS = (
    "runtime/requests",
    "runtime/queue",
    "runtime/results",
    "runtime/logs",
    "outputs/communications/outbox",
    "inputs/founder-replies",
)
REQUEST_FIELDS = (
    "agent_id",
    "trigger_type",
    "reason",
    "run_timestamp",
    "changed_context",
    "instance_path",
)
CRITICAL_TASK_TYPES = {"escalation", "founder_reply", "reply_needed", "founder_digest"}
DEFAULT_DAILY_TOKEN_BUDGET = 10000


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
    request_id: str = ""
    request_hash: str = ""


@dataclass
class ResultRecord:
    run_id: str
    request_id: str
    agent_id: str
    status: str
    started_at: str
    finished_at: str
    trigger_type: str
    project: str
    task_type: str
    origin: str
    reason: str
    changed_context: list[str]
    request_path: str
    queue_path: str
    context_hash: str
    model_profile: dict[str, Any]
    token_policy: dict[str, Any]
    output_path: str = ""
    error: str = ""
    notes: list[str] | None = None


def ensure_runtime_dirs(instance_path: Path) -> None:
    for relative_dir in ROOT_DIRS:
        (instance_path / relative_dir).mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_state(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "outputs/state.json")


def load_schedule(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "config/schedule.json")


def load_models(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "config/models.json")


def load_token_policy(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "config/token-policy.json")


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


def slugify(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value.upper()).strip("-")


def parse_iso8601(timestamp: str) -> datetime | None:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        return None


def current_time(schedule: dict[str, Any]) -> datetime:
    timezone_name = schedule.get("timezone", "UTC")
    return datetime.now(ZoneInfo(timezone_name))


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


def write_front_matter(path: Path, front_matter: dict[str, str], body: str) -> None:
    lines = ["---"]
    for key, value in front_matter.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    path.write_text("\n".join(lines) + "\n" + body.lstrip("\n"), encoding="utf-8")


def list_existing_hashes(directory: Path) -> set[str]:
    hashes: set[str] = set()
    if not directory.exists():
        return hashes
    for path in sorted(directory.glob("*.json")):
        try:
            payload = load_json(path)
        except json.JSONDecodeError:
            continue
        request_hash = payload.get("request_hash")
        if request_hash:
            hashes.add(request_hash)
    return hashes


def dependency_satisfied(agent_state: dict[str, Any]) -> bool:
    return bool(agent_state.get("last_success")) or agent_state.get("status") in {"success", "completed"}


def quiet_hours_block_reason(request: DispatchRequest, schedule_entry: dict[str, Any], now: datetime) -> str | None:
    policy = schedule_entry.get("quiet_hours_policy", {})
    start_hour = policy.get("start_hour_local")
    end_hour = policy.get("end_hour_local")
    if start_hour is None or end_hour is None:
        return None

    hour = now.hour
    in_quiet_hours = False
    if start_hour == end_hour:
        in_quiet_hours = False
    elif start_hour < end_hour:
        in_quiet_hours = start_hour <= hour < end_hour
    else:
        in_quiet_hours = hour >= start_hour or hour < end_hour

    if not in_quiet_hours:
        return None

    mode = policy.get("mode", "allow")
    if mode == "manual_only" and request.trigger_type != "manual":
        return "quiet_hours_manual_only"
    if mode == "digest_only" and request.task_type != "founder_digest" and request.reason != "daily_digest":
        return "quiet_hours_digest_only"
    if mode == "suppress_noncritical" and request.trigger_type != "manual" and request.task_type not in CRITICAL_TASK_TYPES:
        return "quiet_hours_suppressed"
    if mode == "allow_critical_only" and request.trigger_type != "manual" and request.task_type not in CRITICAL_TASK_TYPES:
        return "quiet_hours_critical_only"
    return None


def resolve_model_profile(instance_path: Path, agent_id: str) -> dict[str, Any]:
    config = load_models(instance_path)
    default_profile_name = config.get("default_profile", "standard")
    default_profile = config.get("profiles", {}).get(default_profile_name, {})
    profile_name = config.get("agent_profiles", {}).get(agent_id, default_profile_name)
    profile = config.get("profiles", {}).get(profile_name, default_profile)
    return {
        "profile_name": profile_name if profile else default_profile_name,
        "provider": profile.get("provider", default_profile.get("provider", "codex")),
        "model": profile.get("model", default_profile.get("model", "gpt-5.4-mini")),
        "reasoning_effort": profile.get("reasoning_effort", default_profile.get("reasoning_effort", "medium")),
        "fallback_used": agent_id not in config.get("agent_profiles", {}),
    }


def resolve_token_policy(instance_path: Path, state: dict[str, Any], agent_id: str) -> dict[str, Any]:
    config = load_token_policy(instance_path)
    agent_policy = config.get("agents", {}).get(agent_id, {})
    state_budget = state.get("agents", {}).get(agent_id, {}).get("run_budget", {})
    daily_token_budget = (
        agent_policy.get("daily_token_budget")
        or state_budget.get("daily_token_budget")
        or DEFAULT_DAILY_TOKEN_BUDGET
    )
    return {
        "daily_token_budget": daily_token_budget,
        "max_input_tokens": agent_policy.get("max_input_tokens", config.get("default_max_input_tokens", 4000)),
        "max_output_tokens": agent_policy.get("max_output_tokens", config.get("default_max_output_tokens", 900)),
        "reasoning_tier": agent_policy.get("reasoning_tier", "standard"),
        "skip_if_context_unchanged": config.get("skip_if_context_unchanged", True),
        "fallback_used": agent_id not in config.get("agents", {}),
    }


def iter_relevant_context_files(instance_path: Path, relative_path: str, agent_id: str) -> list[Path]:
    target = instance_path / relative_path
    if not target.exists():
        return []
    if target.is_file():
        return [target]

    files: list[Path] = []
    if relative_path.rstrip("/") == "outputs/handoffs":
        for handoff_path in sorted(target.glob("*.md")):
            front_matter, _body = read_front_matter(handoff_path)
            to_agent = normalize_agent_id(front_matter.get("to", ""))
            from_agent = normalize_agent_id(front_matter.get("from", ""))
            compatibility = front_matter.get("compatibility", "")
            if compatibility == "legacy":
                continue
            if agent_id == "MERIDIAN-ORCHESTRATOR":
                if from_agent == agent_id or to_agent == agent_id or compatibility == "canonical":
                    files.append(handoff_path)
            elif to_agent == agent_id:
                files.append(handoff_path)
        return files

    if relative_path.rstrip("/") == "outputs/escalations":
        pending_dir = target / "pending"
        if pending_dir.exists():
            return sorted(path for path in pending_dir.iterdir() if path.is_file() and path.name != ".gitkeep")
        return []

    for root, _dirs, filenames in os.walk(target):
        for filename in sorted(filenames):
            if filename == ".gitkeep":
                continue
            files.append(Path(root) / filename)
    return files


def compute_context_hash(
    instance_path: Path,
    schedule_entry: dict[str, Any],
    request: DispatchRequest,
) -> str:
    hasher = hashlib.sha256()
    seen: set[str] = set()
    context_paths = list(schedule_entry.get("context_inputs", [])) + list(request.changed_context)
    for relative_path in sorted(context_paths):
        if relative_path in seen:
            continue
        seen.add(relative_path)
        files = iter_relevant_context_files(instance_path, relative_path, request.agent_id)
        if not files:
            hasher.update(relative_path.encode("utf-8"))
            hasher.update(b":missing")
            continue
        for file_path in sorted(files):
            relative_file = file_path.relative_to(instance_path).as_posix()
            hasher.update(relative_file.encode("utf-8"))
            hasher.update(file_path.read_bytes())
    return hasher.hexdigest()


def request_signature(request: DispatchRequest) -> str:
    payload = {field: getattr(request, field) for field in REQUEST_FIELDS}
    payload.update(
        {
            "project": request.project,
            "task_type": request.task_type,
            "origin": request.origin,
        }
    )
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_request(
    *,
    agent_id: str,
    trigger_type: str,
    reason: str,
    run_timestamp: str,
    changed_context: list[str],
    instance_path: Path,
    project: str,
    task_type: str,
    origin: str,
) -> DispatchRequest:
    normalized_changed_context = sorted({path for path in changed_context if path})
    request = DispatchRequest(
        agent_id=normalize_agent_id(agent_id),
        trigger_type=trigger_type,
        reason=reason,
        run_timestamp=run_timestamp,
        changed_context=normalized_changed_context,
        instance_path=str(instance_path),
        project=project,
        task_type=task_type,
        origin=origin,
    )
    request.request_hash = request_signature(request)
    timestamp_key = run_timestamp.replace("-", "").replace(":", "").replace("+", "").replace(".", "")
    request.request_id = f"REQ-{timestamp_key}-{slugify(request.agent_id)}-{request.request_hash[:8]}"
    return request


def discover_pending_handoffs(instance_path: Path) -> list[dict[str, Any]]:
    handoffs: list[dict[str, Any]] = []
    handoff_dir = instance_path / "outputs/handoffs"
    if not handoff_dir.exists():
        return handoffs
    for handoff_path in sorted(handoff_dir.glob("*.md")):
        front_matter, _body = read_front_matter(handoff_path)
        if front_matter.get("status") != "queued":
            continue
        to_agent = normalize_agent_id(front_matter.get("to", ""))
        from_agent = normalize_agent_id(front_matter.get("from", ""))
        if not to_agent:
            continue
        if front_matter.get("compatibility") == "legacy":
            continue
        if to_agent != front_matter.get("to", "") or from_agent != front_matter.get("from", ""):
            continue
        handoffs.append(
            {
                "agent_id": to_agent,
                "project": front_matter.get("project", "startup_ops"),
                "task_type": front_matter.get("task_type", "handoff"),
                "reason": front_matter.get("reason", front_matter.get("handoff_id", handoff_path.stem)),
                "origin": front_matter.get("origin", "handoff"),
                "handoff_id": front_matter.get("handoff_id", handoff_path.stem),
                "path": handoff_path.relative_to(instance_path).as_posix(),
                "created_at": front_matter.get("created_at", ""),
            }
        )
    return handoffs


def discover_open_escalations(instance_path: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    escalations: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for escalation in state.get("open_escalations", []):
        relative_path = escalation.get("path", "")
        if relative_path:
            seen_paths.add(relative_path)
        escalations.append(
            {
                "escalation_id": escalation.get("escalation_id", Path(relative_path).stem if relative_path else "state-escalation"),
                "path": relative_path,
                "project": escalation.get("project", "startup_ops"),
                "reason": escalation.get("reason", "open_escalation"),
            }
        )

    pending_dir = instance_path / "outputs/escalations/pending"
    if pending_dir.exists():
        for escalation_path in sorted(path for path in pending_dir.iterdir() if path.is_file() and path.name != ".gitkeep"):
            relative_path = escalation_path.relative_to(instance_path).as_posix()
            if relative_path in seen_paths:
                continue
            front_matter, _body = read_front_matter(escalation_path)
            escalations.append(
                {
                    "escalation_id": front_matter.get("escalation_id", escalation_path.stem),
                    "path": relative_path,
                    "project": front_matter.get("project", "startup_ops"),
                    "reason": front_matter.get("reason", "open_escalation"),
                }
            )
    return escalations


def can_enqueue_request(
    request: DispatchRequest,
    state: dict[str, Any],
    schedule: dict[str, Any],
    token_policy: dict[str, Any],
    instance_path: Path,
) -> tuple[bool, str]:
    schedule_entry = schedule.get("agents", {}).get(request.agent_id)
    if not schedule_entry:
        return False, "agent_not_in_schedule"
    if not schedule_entry.get("enabled", False):
        return False, "agent_disabled"
    if request.trigger_type not in schedule_entry.get("trigger_mode", []):
        return False, "trigger_not_enabled"

    agent_state = state.get("agents", {}).get(request.agent_id, {})
    max_runs = schedule_entry.get("max_runs_per_day")
    runs_today = agent_state.get("run_budget", {}).get("runs_today", 0)
    if max_runs is not None and runs_today >= max_runs:
        return False, "max_runs_reached"

    last_run = parse_iso8601(agent_state.get("last_run", ""))
    cooldown_minutes = schedule_entry.get("cooldown_minutes", 0)
    now = current_time(schedule)
    if last_run is not None and cooldown_minutes and now < last_run + timedelta(minutes=cooldown_minutes):
        return False, "cooldown_active"

    for dependency in schedule_entry.get("depends_on", []):
        if not dependency_satisfied(state.get("agents", {}).get(dependency, {})):
            return False, f"blocked_on_{dependency}"

    quiet_reason = quiet_hours_block_reason(request, schedule_entry, now)
    if quiet_reason:
        return False, quiet_reason

    used_tokens = agent_state.get("run_budget", {}).get("tokens_used_today", 0)
    if used_tokens >= token_policy["daily_token_budget"]:
        return False, "daily_token_budget_exhausted"

    context_hash = compute_context_hash(instance_path, schedule_entry, request)
    last_context_hash = agent_state.get("context_hash", "")
    if schedule_entry.get("run_if_changed") and token_policy.get("skip_if_context_unchanged", True):
        if context_hash == last_context_hash and request.trigger_type != "manual":
            return False, "context_unchanged"

    return True, "eligible"


def plan_requests(instance_path: Path) -> dict[str, Any]:
    ensure_runtime_dirs(instance_path)
    state = load_state(instance_path)
    schedule = load_schedule(instance_path)
    pending_handoffs = discover_pending_handoffs(instance_path)
    open_escalations = discover_open_escalations(instance_path, state)
    queue_hashes = list_existing_hashes(instance_path / "runtime/queue")
    result_hashes = list_existing_hashes(instance_path / "runtime/results")
    now = current_time(schedule)
    requests: list[DispatchRequest] = []
    planning_notes: list[str] = []

    for handoff in pending_handoffs:
        request = build_request(
            agent_id=handoff["agent_id"],
            trigger_type="event",
            reason=handoff["reason"],
            run_timestamp=now.isoformat(timespec="seconds"),
            changed_context=[handoff["path"]],
            instance_path=instance_path,
            project=handoff["project"],
            task_type=handoff["task_type"],
            origin=handoff["origin"],
        )
        if request.request_hash in queue_hashes or request.request_hash in result_hashes:
            continue
        token_policy = resolve_token_policy(instance_path, state, request.agent_id)
        eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
        if eligible:
            requests.append(request)
        else:
            planning_notes.append(f"{request.agent_id}:{reason}")

    if open_escalations:
        escalation_paths = [item["path"] for item in open_escalations if item["path"]]
        request = build_request(
            agent_id="MERIDIAN-ORCHESTRATOR",
            trigger_type="event",
            reason="open_escalations",
            run_timestamp=now.isoformat(timespec="seconds"),
            changed_context=escalation_paths,
            instance_path=instance_path,
            project="startup_ops",
            task_type="escalation",
            origin="integration",
        )
        if request.request_hash not in queue_hashes and request.request_hash not in result_hashes:
            token_policy = resolve_token_policy(instance_path, state, request.agent_id)
            eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
            if eligible:
                requests.append(request)
            else:
                planning_notes.append(f"{request.agent_id}:{reason}")

    heartbeat_minutes = schedule.get("dispatcher", {}).get("heartbeat_minutes", 15)
    overdue_sweep_hours = schedule.get("dispatcher", {}).get("overdue_sweep_hours", 6)
    for agent_id, schedule_entry in sorted(schedule.get("agents", {}).items()):
        if not schedule_entry.get("enabled", False):
            continue
        if "heartbeat" in schedule_entry.get("trigger_mode", []):
            agent_state = state.get("agents", {}).get(agent_id, {})
            last_run = parse_iso8601(agent_state.get("last_run", ""))
            heartbeat_interval = schedule_entry.get("heartbeat_minutes", heartbeat_minutes)
            heartbeat_due = last_run is None or now >= last_run + timedelta(minutes=heartbeat_interval)
            if heartbeat_due:
                request = build_request(
                    agent_id=agent_id,
                    trigger_type="heartbeat",
                    reason="heartbeat_due",
                    run_timestamp=now.isoformat(timespec="seconds"),
                    changed_context=[],
                    instance_path=instance_path,
                    project=agent_state.get("active_project", "startup_ops"),
                    task_type="status_review" if agent_id != "MERIDIAN-ORCHESTRATOR" else "operating_review",
                    origin="scheduler",
                )
                if request.request_hash not in queue_hashes and request.request_hash not in result_hashes:
                    token_policy = resolve_token_policy(instance_path, state, request.agent_id)
                    eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
                    if eligible:
                        requests.append(request)
                    else:
                        planning_notes.append(f"{request.agent_id}:{reason}")

        if schedule_entry.get("trigger_mode") and overdue_sweep_hours:
            agent_state = state.get("agents", {}).get(agent_id, {})
            last_success = parse_iso8601(agent_state.get("last_success", ""))
            overdue = last_success is None or now >= last_success + timedelta(hours=overdue_sweep_hours)
            if overdue and any(item["agent_id"] == agent_id for item in pending_handoffs):
                agent_handoff_paths = [item["path"] for item in pending_handoffs if item["agent_id"] == agent_id]
                request = build_request(
                    agent_id=agent_id,
                    trigger_type="event" if "event" in schedule_entry.get("trigger_mode", []) else schedule_entry["trigger_mode"][0],
                    reason="overdue_sweep",
                    run_timestamp=now.isoformat(timespec="seconds"),
                    changed_context=agent_handoff_paths,
                    instance_path=instance_path,
                    project=state.get("agents", {}).get(agent_id, {}).get("active_project", "startup_ops"),
                    task_type="overdue_sweep",
                    origin="scheduler",
                )
                if request.request_hash not in queue_hashes and request.request_hash not in result_hashes:
                    token_policy = resolve_token_policy(instance_path, state, request.agent_id)
                    eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
                    if eligible:
                        requests.append(request)
                    else:
                        planning_notes.append(f"{request.agent_id}:{reason}")

    queued_files: list[str] = []
    requests_dir = instance_path / "runtime/requests"
    queue_dir = instance_path / "runtime/queue"
    for request in requests:
        payload = asdict(request)
        request_path = requests_dir / f"{request.request_id}.json"
        queue_path = queue_dir / f"{request.request_id}.json"
        write_json(request_path, payload)
        write_json(queue_path, payload)
        queued_files.append(queue_path.relative_to(instance_path).as_posix())

    return {
        "status": "planned",
        "queued_count": len(queued_files),
        "queued_requests": queued_files,
        "notes": planning_notes,
        "pending_handoffs": len(pending_handoffs),
        "open_escalations": len(open_escalations),
    }


def queue_request(instance_path: Path, request: DispatchRequest) -> dict[str, Any]:
    ensure_runtime_dirs(instance_path)
    payload = asdict(request)
    request_path = instance_path / "runtime/requests" / f"{request.request_id}.json"
    queue_path = instance_path / "runtime/queue" / f"{request.request_id}.json"
    write_json(request_path, payload)
    write_json(queue_path, payload)
    return {
        "status": "queued",
        "request_id": request.request_id,
        "request_path": request_path.relative_to(instance_path).as_posix(),
        "queue_path": queue_path.relative_to(instance_path).as_posix(),
        "request_hash": request.request_hash,
    }


def mark_consumed_handoffs(instance_path: Path, request: DispatchRequest, result: ResultRecord) -> None:
    for relative_path in request.changed_context:
        if not relative_path.startswith("outputs/handoffs/"):
            continue
        handoff_path = instance_path / relative_path
        if not handoff_path.exists():
            continue
        front_matter, body = read_front_matter(handoff_path)
        if front_matter.get("status") != "queued":
            continue
        front_matter["status"] = "completed"
        front_matter["processed_at"] = result.finished_at
        front_matter["runtime_result"] = f"runtime/results/{result.run_id}.json"
        write_front_matter(handoff_path, front_matter, body)


def execute_request(instance_path: Path, request_path: Path) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    request = DispatchRequest(**load_json(request_path))
    state = load_state(instance_path)
    schedule = load_schedule(instance_path)
    schedule_entry = schedule.get("agents", {}).get(request.agent_id, {})
    token_policy = resolve_token_policy(instance_path, state, request.agent_id)
    model_profile = resolve_model_profile(instance_path, request.agent_id)
    context_hash = compute_context_hash(instance_path, schedule_entry, request) if schedule_entry else ""
    run_id = request.request_id.replace("REQ-", "RUN-", 1)
    notes: list[str] = []
    status = "completed"
    error = ""

    if not schedule_entry:
        status = "failed"
        error = "agent_not_in_schedule"
    else:
        eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
        if not eligible:
            status = "skipped" if reason == "context_unchanged" else "blocked"
            notes.append(reason)
        else:
            notes.append("serial_queue_execution")
            if model_profile.get("fallback_used"):
                notes.append("model_profile_fallback_used")
            if token_policy.get("fallback_used"):
                notes.append("token_policy_fallback_used")

    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = ResultRecord(
        run_id=run_id,
        request_id=request.request_id,
        agent_id=request.agent_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        trigger_type=request.trigger_type,
        project=request.project,
        task_type=request.task_type,
        origin=request.origin,
        reason=request.reason,
        changed_context=request.changed_context,
        request_path=(instance_path / "runtime/requests" / f"{request.request_id}.json").relative_to(instance_path).as_posix(),
        queue_path=request_path.relative_to(instance_path).as_posix(),
        context_hash=context_hash,
        model_profile=model_profile,
        token_policy=token_policy,
        error=error,
        notes=notes,
    )
    result_path = instance_path / "runtime/results" / f"{run_id}.json"
    write_json(result_path, asdict(result))

    if status == "completed":
        mark_consumed_handoffs(instance_path, request, result)

    request_path.unlink(missing_ok=True)
    return {
        "run_id": run_id,
        "status": status,
        "result_path": result_path.relative_to(instance_path).as_posix(),
        "notes": notes,
        "error": error,
    }


def drain_queue(instance_path: Path, limit: int | None = None) -> dict[str, Any]:
    ensure_runtime_dirs(instance_path)
    queue_dir = instance_path / "runtime/queue"
    processed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    queue_files = sorted(queue_dir.glob("*.json"))
    if limit is not None:
        queue_files = queue_files[:limit]

    for queue_path in queue_files:
        try:
            outcome = execute_request(instance_path, queue_path)
            processed.append(outcome)
            if outcome["status"] in {"failed", "blocked"}:
                failures.append(outcome)
        except Exception as exc:  # pragma: no cover - failure path should still persist.
            request_id = queue_path.stem
            run_id = request_id.replace("REQ-", "RUN-", 1)
            result_path = instance_path / "runtime/results" / f"{run_id}.json"
            failure_payload = {
                "run_id": run_id,
                "request_id": request_id,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "request_path": queue_path.relative_to(instance_path).as_posix(),
            }
            write_json(result_path, failure_payload)
            failures.append(failure_payload)
            processed.append(failure_payload)

    return {
        "status": "drained" if not failures else "drained_with_failures",
        "processed_count": len(processed),
        "failure_count": len(failures),
        "results": processed,
    }


def ingest_replies(instance_path: Path) -> dict[str, Any]:
    ensure_runtime_dirs(instance_path)
    channel = get_default_channel(instance_path)
    replies = channel.ingest_responses()
    queued: list[dict[str, Any]] = []
    now = current_time(load_schedule(instance_path)).isoformat(timespec="seconds")
    for reply in replies:
        request = build_request(
            agent_id="MERIDIAN-ORCHESTRATOR",
            trigger_type="event",
            reason=f"founder_reply:{reply['reply_id']}",
            run_timestamp=now,
            changed_context=[reply["source_path"]],
            instance_path=instance_path,
            project=reply.get("project", "startup_ops"),
            task_type="founder_reply",
            origin="founder_reply",
        )
        queued.append(queue_request(instance_path, request))
    return {
        "status": "ingested",
        "reply_count": len(replies),
        "queued_requests": queued,
    }


def reconcile_state(instance_path: Path) -> dict[str, Any]:
    ensure_runtime_dirs(instance_path)
    state = load_state(instance_path)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "state_valid_json": True,
        "state_path": "outputs/state.json",
        "queue_depth": len(list((instance_path / "runtime/queue").glob("*.json"))),
        "result_count": len(list((instance_path / "runtime/results").glob("*.json"))),
        "open_handoffs": len(discover_pending_handoffs(instance_path)),
        "open_escalations": len(discover_open_escalations(instance_path, state)),
        "note": "Shared-state normalization remains MERIDIAN-ORCHESTRATOR-owned; reconcile-state audits repo-native runtime health only.",
    }
    report_path = instance_path / "runtime/logs" / "reconcile-state.json"
    write_json(report_path, report)
    return report


def send_file_message(instance_path: Path, message_type: str, subject: str, body_markdown: str) -> dict[str, Any]:
    channel = get_default_channel(instance_path)
    message = Message(message_type=message_type, subject=subject, body_markdown=body_markdown)
    if message_type == "digest":
        return channel.send_digest(message)
    if message_type == "escalation":
        return channel.send_escalation(message)
    return channel.send_reply_needed(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Founders OS repo-native orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Plan eligible runs and enqueue request manifests")
    plan_parser.add_argument("--instance-path", default=".")

    run_once_parser = subparsers.add_parser("run-once", help="Queue a one-off dispatch request")
    run_once_parser.add_argument("--agent", required=True)
    run_once_parser.add_argument("--trigger-type", required=True)
    run_once_parser.add_argument("--reason", required=True)
    run_once_parser.add_argument("--instance-path", default=".")
    run_once_parser.add_argument("--project", default="startup_ops")
    run_once_parser.add_argument("--task-type", default="status_review")
    run_once_parser.add_argument("--origin", default="scheduler")
    run_once_parser.add_argument("--changed-context", action="append", default=[])

    drain_parser = subparsers.add_parser("drain-queue", help="Process queued request manifests serially")
    drain_parser.add_argument("--instance-path", default=".")
    drain_parser.add_argument("--limit", type=int, default=None)

    ingest_parser = subparsers.add_parser("ingest-replies", help="Ingest founder replies from the file-backed channel")
    ingest_parser.add_argument("--instance-path", default=".")

    reconcile_parser = subparsers.add_parser("reconcile-state", help="Audit repo-native runtime state and queue health")
    reconcile_parser.add_argument("--instance-path", default=".")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    instance_path = Path(args.instance_path).resolve()
    ensure_runtime_dirs(instance_path)

    if args.command == "plan":
        payload = plan_requests(instance_path)
    elif args.command == "run-once":
        request = build_request(
            agent_id=args.agent,
            trigger_type=args.trigger_type,
            reason=args.reason,
            run_timestamp=current_time(load_schedule(instance_path)).isoformat(timespec="seconds"),
            changed_context=args.changed_context,
            instance_path=instance_path,
            project=args.project,
            task_type=args.task_type,
            origin=args.origin,
        )
        payload = queue_request(instance_path, request)
    elif args.command == "drain-queue":
        payload = drain_queue(instance_path, limit=args.limit)
    elif args.command == "ingest-replies":
        payload = ingest_replies(instance_path)
    elif args.command == "reconcile-state":
        payload = reconcile_state(instance_path)
    else:  # pragma: no cover
        parser.error(f"Unknown command: {args.command}")
        return 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload.get("status") in {"failed", "drained_with_failures"} else 0


if __name__ == "__main__":
    sys.exit(main())
