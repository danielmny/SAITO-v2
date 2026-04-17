from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner.communications import Message, get_default_channel
from runner.specialists import ENABLED_SPECIALISTS, execute_specialist


ROOT_DIRS = (
    "runtime/requests",
    "runtime/queue",
    "runtime/results",
    "runtime/logs",
    "outputs/communications/outbox",
    "inputs/founder-replies",
    "projects",
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
RESULT_RETENTION_LIMIT = 200
REQUEST_RETENTION_LIMIT = 200
PORTFOLIO_PROJECT = "portfolio"
STARTUP_WIDE_PROJECT = "startup_ops"


@dataclass
class DispatchRequest:
    agent_id: str
    trigger_type: str
    reason: str
    run_timestamp: str
    changed_context: list[str]
    instance_path: str
    project: str = PORTFOLIO_PROJECT
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
    output_paths: list[str] = field(default_factory=list)
    state_updated: bool = False
    processed_handoffs_count: int = 0
    processed_escalations_count: int = 0
    created_escalations_count: int = 0
    created_handoffs_count: int = 0
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


def project_slug(project: str, state: dict[str, Any] | None = None) -> str:
    if not project:
        return ""
    if state and project in state.get("projects", {}):
        slug = state["projects"][project].get("slug", "")
        if slug:
            return str(slug)
    return "".join(character.lower() if character.isalnum() else "-" for character in project).strip("-")


def project_root(instance_path: Path, project: str, state: dict[str, Any] | None = None) -> Path | None:
    slug = project_slug(project, state)
    if not slug:
        return None
    path = instance_path / "projects" / slug
    return path if path.exists() else None


def project_context_files(instance_path: Path, project: str, state: dict[str, Any] | None = None) -> list[Path]:
    root = project_root(instance_path, project, state)
    if root is None:
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        if "outputs" in path.parts:
            continue
        files.append(path)
    return files


def project_output_files(instance_path: Path, project: str, state: dict[str, Any] | None = None) -> list[Path]:
    root = project_root(instance_path, project, state)
    if root is None:
        return []
    output_root = root / "outputs"
    if not output_root.exists():
        return []
    return sorted(path for path in output_root.rglob("*.md"))


def project_output_dir(instance_path: Path, project: str, agent_id: str, state: dict[str, Any] | None = None) -> Path:
    root = project_root(instance_path, project, state)
    if root is None:
        return instance_path / "outputs" / agent_id
    return root / "outputs" / agent_id


def list_agent_output_files(instance_path: Path, agent_id: str) -> list[Path]:
    files: list[Path] = []
    legacy_dir = instance_path / "outputs" / agent_id
    if legacy_dir.exists():
        files.extend(sorted(legacy_dir.glob("*.md")))
    projects_root = instance_path / "projects"
    if projects_root.exists():
        for project_dir in sorted(path for path in projects_root.iterdir() if path.is_dir()):
            project_dir_outputs = project_dir / "outputs" / agent_id
            if project_dir_outputs.exists():
                files.extend(sorted(project_dir_outputs.glob("*.md")))
    return sorted(files)


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


def isoformat_or_empty(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value is not None else ""


def sanitize_state_for_hash(state: dict[str, Any]) -> dict[str, Any]:
    sanitized = json.loads(json.dumps(state))
    sanitized.get("company", {}).pop("last_updated", None)
    sanitized.pop("last_runs", None)
    sanitized.pop("run_queue", None)
    sanitized.pop("metrics", None)
    for agent_state in sanitized.get("agents", {}).values():
        for key in (
            "last_run",
            "last_success",
            "status",
            "dashboard_status",
            "last_output",
            "last_trigger",
            "context_hash",
            "cooldown_until",
            "skip_reason",
            "communications",
            "external_artifacts",
            "last_google_sync",
        ):
            agent_state.pop(key, None)
        if "run_budget" in agent_state:
            agent_state["run_budget"].pop("tokens_used_today", None)
            agent_state["run_budget"].pop("runs_today", None)
    return sanitized


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


def latest_runtime_result_status(instance_path: Path, agent_id: str, required_status: str | None = None) -> str:
    latest_payload: dict[str, Any] | None = None
    for path in sorted((instance_path / "runtime/results").glob("*.json")):
        try:
            payload = load_json(path)
        except json.JSONDecodeError:
            continue
        if payload.get("agent_id") != agent_id:
            continue
        if required_status is not None and payload.get("status") != required_status:
            continue
        latest_payload = payload
    if latest_payload is None:
        return ""
    return str(latest_payload.get("status", ""))


def dependency_satisfied(instance_path: Path, agent_state: dict[str, Any], dependency: str) -> bool:
    if bool(agent_state.get("last_success")) or agent_state.get("status") in {"success", "completed"}:
        return True
    return latest_runtime_result_status(instance_path, dependency, required_status="success") == "success"


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
            if relative_file == "outputs/state.json":
                sanitized_state = sanitize_state_for_hash(load_json(file_path))
                hasher.update(json.dumps(sanitized_state, sort_keys=True).encode("utf-8"))
            else:
                hasher.update(file_path.read_bytes())
    state = load_state(instance_path)
    for file_path in project_context_files(instance_path, request.project, state):
        relative_file = file_path.relative_to(instance_path).as_posix()
        hasher.update(relative_file.encode("utf-8"))
        hasher.update(file_path.read_bytes())
    for file_path in project_output_files(instance_path, request.project, state):
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


def planner_request_key(request: DispatchRequest) -> tuple[str, str]:
    return (request.agent_id, request.project)


def known_startup_projects(instance_path: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    projects: list[dict[str, str]] = []
    for key, value in sorted(state.get("projects", {}).items()):
        if key == STARTUP_WIDE_PROJECT:
            continue
        projects.append(
            {
                "key": key,
                "name": value.get("name", key),
                "slug": value.get("slug", project_slug(key, state)),
                "summary": value.get("summary", ""),
            }
        )
    known_slugs = {item["slug"] for item in projects}
    projects_root = instance_path / "projects"
    if projects_root.exists():
        for path in sorted(projects_root.iterdir()):
            if not path.is_dir() or path.name == project_slug(STARTUP_WIDE_PROJECT) or path.name in known_slugs:
                continue
            projects.append(
                {
                    "key": path.name,
                    "name": path.name.replace("-", " ").title(),
                    "slug": path.name,
                    "summary": "Project folder exists but is not yet registered in outputs/state.json.",
                }
            )
    return projects


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
                "to": to_agent,
                "from": from_agent,
                "project": front_matter.get("project", STARTUP_WIDE_PROJECT),
                "task_type": front_matter.get("task_type", "handoff"),
                "reason": front_matter.get("reason", front_matter.get("handoff_id", handoff_path.stem)),
                "origin": front_matter.get("origin", "handoff"),
                "handoff_id": front_matter.get("handoff_id", handoff_path.stem),
                "path": handoff_path.relative_to(instance_path).as_posix(),
                "created_at": front_matter.get("created_at", ""),
                "front_matter": front_matter,
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
                "project": escalation.get("project", STARTUP_WIDE_PROJECT),
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
                    "project": front_matter.get("project", STARTUP_WIDE_PROJECT),
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
        if not dependency_satisfied(instance_path, state.get("agents", {}).get(dependency, {}), dependency):
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
    trim_runtime_manifests(instance_path)
    state = load_state(instance_path)
    schedule = load_schedule(instance_path)
    pending_handoffs = discover_pending_handoffs(instance_path)
    open_escalations = discover_open_escalations(instance_path, state)
    queue_hashes = list_existing_hashes(instance_path / "runtime/queue")
    result_hashes = list_existing_hashes(instance_path / "runtime/results")
    now = current_time(schedule)
    requests: list[DispatchRequest] = []
    planning_notes: list[str] = []
    planned_keys: set[tuple[str, str, str]] = set()

    handoffs_by_agent: dict[str, list[dict[str, Any]]] = {}
    for handoff in pending_handoffs:
        handoffs_by_agent.setdefault(handoff["agent_id"], []).append(handoff)

    for agent_id, agent_handoffs in sorted(handoffs_by_agent.items()):
        changed_context = [item["path"] for item in agent_handoffs]
        projects = {item["project"] for item in agent_handoffs}
        task_types = {item["task_type"] for item in agent_handoffs}
        reasons = [item["reason"] for item in agent_handoffs]
        request = build_request(
            agent_id=agent_id,
            trigger_type="event",
            reason=reasons[0] if len(reasons) == 1 else f"{len(agent_handoffs)} pending handoffs",
            run_timestamp=now.isoformat(timespec="seconds"),
            changed_context=changed_context,
            instance_path=instance_path,
            project=sorted(projects)[0] if len(projects) == 1 else PORTFOLIO_PROJECT,
            task_type=sorted(task_types)[0] if len(task_types) == 1 else "handoff_batch",
            origin="handoff" if all(item["origin"] == "handoff" for item in agent_handoffs) else "integration",
        )
        if request.request_hash in queue_hashes or request.request_hash in result_hashes:
            continue
        token_policy = resolve_token_policy(instance_path, state, request.agent_id)
        eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
        if eligible:
            requests.append(request)
            planned_keys.add(planner_request_key(request))
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
            project=STARTUP_WIDE_PROJECT,
            task_type="escalation",
            origin="integration",
        )
        if (
            planner_request_key(request) not in planned_keys
            and request.request_hash not in queue_hashes
            and request.request_hash not in result_hashes
        ):
            token_policy = resolve_token_policy(instance_path, state, request.agent_id)
            eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
            if eligible:
                requests.append(request)
                planned_keys.add(planner_request_key(request))
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
                    project=agent_state.get("active_project", STARTUP_WIDE_PROJECT),
                    task_type="status_review" if agent_id != "MERIDIAN-ORCHESTRATOR" else "operating_review",
                    origin="scheduler",
                )
                if (
                    planner_request_key(request) not in planned_keys
                    and request.request_hash not in queue_hashes
                    and request.request_hash not in result_hashes
                ):
                    token_policy = resolve_token_policy(instance_path, state, request.agent_id)
                    eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
                    if eligible:
                        requests.append(request)
                        planned_keys.add(planner_request_key(request))
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
                    project=state.get("agents", {}).get(agent_id, {}).get("active_project", STARTUP_WIDE_PROJECT),
                    task_type="overdue_sweep",
                    origin="scheduler",
                )
                if (
                    planner_request_key(request) not in planned_keys
                    and request.request_hash not in queue_hashes
                    and request.request_hash not in result_hashes
                ):
                    token_policy = resolve_token_policy(instance_path, state, request.agent_id)
                    eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
                    if eligible:
                        requests.append(request)
                        planned_keys.add(planner_request_key(request))
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


def write_markdown_with_front_matter(path: Path, front_matter: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_front_matter(path, front_matter, body)


def list_recent_agent_outputs(
    instance_path: Path,
    schedule: dict[str, Any],
    since: datetime | None,
    exclude_agent: str = "MERIDIAN-ORCHESTRATOR",
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for agent_id, schedule_entry in sorted(schedule.get("agents", {}).items()):
        if agent_id == exclude_agent or not schedule_entry.get("enabled", False):
            continue
        candidate_files = sorted(list_agent_output_files(instance_path, agent_id), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidate_files:
            continue
        latest_path = candidate_files[0]
        modified_at = datetime.fromtimestamp(latest_path.stat().st_mtime, tz=timezone.utc)
        front_matter, body = read_front_matter(latest_path)
        outputs.append(
            {
                "agent_id": agent_id,
                "path": latest_path.relative_to(instance_path).as_posix(),
                "modified_at": modified_at,
                "is_new": since is None or modified_at > since.astimezone(timezone.utc),
                "front_matter": front_matter,
                "body": body.strip(),
                "summary": next(
                    (line.strip("- ").strip() for line in body.splitlines() if line.startswith("- ")),
                    body.splitlines()[0].strip() if body.splitlines() else "",
                ),
            }
        )
    return outputs


def recent_output_priority(output: dict[str, Any], pending_handoffs: list[dict[str, Any]]) -> tuple[int, str]:
    score = 0
    front_matter = output.get("front_matter", {})
    artifact_type = front_matter.get("artifact_type", "")
    task_type = front_matter.get("task_type", "")
    audience = front_matter.get("audience", "internal")
    score += sum(3 for item in pending_handoffs if item["from"] == output["agent_id"])
    if audience == "founder":
        score += 4
    if artifact_type in {"finance_memo", "legal_brief", "founder_briefing"}:
        score += 3
    if artifact_type in {"product_memo", "analytics_brief"}:
        score += 2
    if task_type in {"metric_alignment_review", "fundraise_preparation", "diligence_readiness"}:
        score += 2
    if "[ESCALATE TO FOUNDER]" in output.get("body", ""):
        score += 5
    return score, output["path"]


def trim_runtime_manifests(instance_path: Path) -> None:
    queue_ids = {path.stem for path in (instance_path / "runtime/queue").glob("*.json")}

    request_paths: list[Path] = []
    for path in (instance_path / "runtime/requests").glob("*.json"):
        if path.exists():
            request_paths.append(path)
    request_paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    kept_requests = 0
    for path in request_paths:
        if path.stem in queue_ids:
            kept_requests += 1
            continue
        result_path = instance_path / "runtime/results" / path.name.replace("REQ-", "RUN-", 1)
        if result_path.exists() or kept_requests >= REQUEST_RETENTION_LIMIT:
            path.unlink(missing_ok=True)
            continue
        kept_requests += 1

    result_paths: list[Path] = []
    for path in (instance_path / "runtime/results").glob("*.json"):
        if path.exists():
            result_paths.append(path)
    result_paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for stale_path in result_paths[RESULT_RETENTION_LIMIT:]:
        stale_path.unlink(missing_ok=True)


def mark_handoffs_processed(instance_path: Path, handoff_paths: list[str], run_id: str, processed_at: str) -> int:
    processed = 0
    for relative_path in sorted(set(handoff_paths)):
        handoff_path = instance_path / relative_path
        if not handoff_path.exists():
            continue
        front_matter, body = read_front_matter(handoff_path)
        if front_matter.get("status") != "queued":
            continue
        front_matter["status"] = "processed"
        front_matter["processed_at"] = processed_at
        front_matter["runtime_result"] = f"runtime/results/{run_id}.json"
        write_front_matter(handoff_path, front_matter, body)
        processed += 1
    return processed


def detect_founder_decision_outputs(
    instance_path: Path,
    recent_outputs: list[dict[str, Any]],
    existing_escalations: list[dict[str, Any]],
    now: datetime,
) -> tuple[list[dict[str, Any]], int]:
    pending_dir = instance_path / "outputs/escalations/pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    existing_paths = {item.get("path", "") for item in existing_escalations}
    existing_source_paths = {item.get("source_output", "") for item in existing_escalations}
    created = 0

    for output in recent_outputs:
        if "[ESCALATE TO FOUNDER]" not in output["body"]:
            continue
        if output["path"] in existing_source_paths:
            continue
        escalation_id = f"ESCALATION-{now.strftime('%Y-%m-%d')}-{slugify(output['agent_id'])}-{created + 1:03d}"
        escalation_path = pending_dir / f"{escalation_id}.md"
        relative_path = escalation_path.relative_to(instance_path).as_posix()
        if relative_path in existing_paths:
            continue
        front_matter = {
            "escalation_id": escalation_id,
            "from": output["agent_id"],
            "project": output["front_matter"].get("project", STARTUP_WIDE_PROJECT),
            "status": "pending",
            "created_at": now.isoformat(timespec="seconds"),
            "reason": "founder_decision_required",
            "source_output": output["path"],
        }
        body = "\n".join(
            [
                f"# {escalation_id}",
                "",
                "## Source",
                output["path"],
                "",
                "## Decision Needed",
                "A recent agent output explicitly requested founder input.",
            ]
        )
        write_markdown_with_front_matter(escalation_path, front_matter, body)
        existing_escalations.append(
            {
                "escalation_id": escalation_id,
                "path": relative_path,
                "project": front_matter["project"],
                "reason": front_matter["reason"],
                "source_output": output["path"],
            }
        )
        created += 1
    return existing_escalations, created


def build_meridian_briefing(
    *,
    state: dict[str, Any],
    pending_handoffs: list[dict[str, Any]],
    open_escalations: list[dict[str, Any]],
    recent_outputs: list[dict[str, Any]],
    processed_handoff_paths: list[str],
) -> str:
    new_outputs = [item for item in recent_outputs if item["is_new"]]
    prioritized_outputs = sorted(
        new_outputs,
        key=lambda item: recent_output_priority(item, pending_handoffs),
        reverse=True,
    )
    wins: list[str] = []
    risks: list[str] = []
    decisions_needed: list[str] = []
    next_actions: list[str] = []

    if prioritized_outputs:
        for output in prioritized_outputs[:4]:
            handoff_count = sum(1 for item in pending_handoffs if item["from"] == output["agent_id"])
            summary = output.get("summary", "").strip()
            detail = f" Summary: {summary}" if summary else ""
            if handoff_count:
                wins.append(
                    f"`{output['agent_id']}` advanced `{output['path']}` and generated {handoff_count} downstream follow-on(s).{detail}"
                )
            else:
                wins.append(f"`{output['agent_id']}` advanced `{output['path']}`.{detail}")
    else:
        wins.append("No new specialist outputs landed since the last MERIDIAN success.")

    downstream_handoffs = [item for item in pending_handoffs if item["to"] != "MERIDIAN-ORCHESTRATOR"]
    if downstream_handoffs:
        risks.append(f"{len(downstream_handoffs)} downstream handoffs remain queued across active agents.")
    if open_escalations:
        risks.append(f"{len(open_escalations)} open escalations require founder attention or explicit routing.")
        decisions_needed.extend(
            f"`{item['escalation_id']}` for `{item['project']}`: {item['reason']}." for item in open_escalations[:3]
        )
    if processed_handoff_paths:
        wins.append(f"MERIDIAN processed {len(processed_handoff_paths)} handoff(s) addressed directly to the orchestrator.")

    if not decisions_needed:
        decisions_needed.append("No new founder decision is required in this pass.")

    ranked_handoffs = sorted(
        downstream_handoffs,
        key=lambda item: (
            0 if item["to"] in {"COUNSEL-LEGAL", "LEDGER-FINANCE"} else 1,
            item["handoff_id"],
        ),
    )
    for handoff in ranked_handoffs[:4]:
        next_actions.append(
            f"Keep `{handoff['handoff_id']}` queued for `{handoff['to']}` on `{handoff['project']}`."
        )
    if not next_actions:
        next_actions.append("No immediate downstream routing changes are required.")

    handoff_summary_lines = [
        f"- `{item['handoff_id']}` -> `{item['to']}` on `{item['project']}` ({item['task_type']})"
        for item in pending_handoffs[:6]
    ] or ["- No queued handoffs."]
    escalation_summary_lines = [
        f"- `{item['escalation_id']}` on `{item['project']}`: {item['reason']}"
        for item in open_escalations[:6]
    ] or ["- No open escalations."]
    risk_lines = [f"- {item}" for item in risks] if risks else ["- No new operating risks surfaced in this pass."]

    return "\n".join(
        [
            "[Acting as: MERIDIAN-ORCHESTRATOR]",
            "",
            f"# Founder Briefing — {datetime.now().date().isoformat()}",
            "",
            "## Wins",
            *[f"- {item}" for item in wins],
            "",
            "## Risks",
            *risk_lines,
            "",
            "## Decisions Needed",
            *[f"- {item}" for item in decisions_needed],
            "",
            "## Next Actions",
            *[f"- {item}" for item in next_actions],
            "",
            "## Open Handoffs Summary",
            *handoff_summary_lines,
            "",
            "## Escalation Summary",
            *escalation_summary_lines,
        ]
    )


def build_meridian_project_intake(state: dict[str, Any], instance_path: Path) -> str:
    projects = known_startup_projects(instance_path, state)
    project_lines = [f"- `{item['name']}` (`{item['slug']}`): {item['summary']}" for item in projects] or [
        "- No startup projects are registered yet. Add a startup under `projects/{startup-slug}/` and try again."
    ]
    next_step_lines: list[str] = []
    for item in projects:
        open_tasks = [
            task for task in state.get("task_board", [])
            if task.get("project") == item["key"] and task.get("status") not in {"completed", "stale"}
        ]
        if open_tasks:
            top_task = open_tasks[0]
            next_step_lines.append(
                f"- `{item['name']}`: continue `{top_task.get('title', top_task.get('task_type', 'next task'))}` with `{top_task.get('owner_agent', 'assigned agent')}`."
            )
        else:
            next_step_lines.append(
                f"- `{item['name']}`: review current status and choose the next proof, GTM, or product task."
            )
    return "\n".join(
        [
            "[Acting as: MERIDIAN-ORCHESTRATOR]",
            "",
            "# Project Selection Required",
            "",
            "Manual MERIDIAN runs now begin with project selection so the team stays scoped to one startup at a time.",
            "",
            "## Active Startup Projects",
            *project_lines,
            "",
            "## Reply With",
            "- Which startup/project to work on.",
            "- Whether you want startup-wide status, project status, task status, or new execution.",
            "- What you want the team to do next.",
            "",
            "## Suggested Next Steps",
            *next_step_lines,
            "",
            "## New Startup Setup",
            "- Create `projects/{startup-slug}/` from the template hierarchy.",
            "- Fill in `project.md`, `problem.md`, `icp.md`, `solution.md`, `validation.md`, `strategy.md`, and `financials.md`.",
            "- MERIDIAN can then route that startup as a first-class project.",
        ]
    )


def update_meridian_state(
    *,
    instance_path: Path,
    state: dict[str, Any],
    schedule: dict[str, Any],
    request: DispatchRequest,
    run_id: str,
    started_at: str,
    finished_at: str,
    status: str,
    post_context_hash: str,
    output_paths: list[str],
    processed_handoff_paths: list[str],
    open_escalations: list[dict[str, Any]],
    recent_outputs: list[dict[str, Any]],
) -> None:
    meridian_state = state.setdefault("agents", {}).setdefault("MERIDIAN-ORCHESTRATOR", {})
    run_budget = meridian_state.setdefault("run_budget", {})
    run_budget["daily_token_budget"] = run_budget.get("daily_token_budget", DEFAULT_DAILY_TOKEN_BUDGET)
    run_budget["tokens_used_today"] = run_budget.get("tokens_used_today", 0)
    run_budget["runs_today"] = run_budget.get("runs_today", 0) + 1
    meridian_state["last_run"] = finished_at
    meridian_state["status"] = status
    meridian_state["dashboard_status"] = "completed" if status in {"success", "skipped"} else status
    meridian_state["last_trigger"] = request.trigger_type
    meridian_state["context_hash"] = post_context_hash
    meridian_state["skip_reason"] = "no_meaningful_changed_context" if status == "skipped" else ""
    if request.project != PORTFOLIO_PROJECT:
        meridian_state["active_project"] = request.project
    if status in {"success", "skipped"}:
        meridian_state["last_success"] = finished_at
    if output_paths:
        meridian_state["last_output"] = output_paths[0]
    communications = meridian_state.setdefault("communications", [])
    external_artifacts = meridian_state.setdefault("external_artifacts", [])

    state["open_escalations"] = open_escalations
    state["run_queue"] = sorted(path.relative_to(instance_path).as_posix() for path in (instance_path / "runtime/queue").glob("*.json"))

    if output_paths:
        for output_path in output_paths:
            communications.append(
                {
                    "type": "founder_briefing",
                    "project": request.project,
                    "task_type": request.task_type,
                    "origin": request.origin,
                    "path": output_path,
                    "created_at": finished_at,
                }
            )
            if output_path not in external_artifacts:
                external_artifacts.append(output_path)
            if output_path not in state.setdefault("external_artifacts", []):
                state["external_artifacts"].append(output_path)
            state.setdefault("communications", []).append(
                {
                    "type": "founder_briefing",
                    "project": request.project,
                    "task_type": request.task_type,
                    "origin": request.origin,
                    "from": "MERIDIAN-ORCHESTRATOR",
                    "path": output_path,
                    "created_at": finished_at,
                }
            )

    remaining_pending_handoff_ids = {item["handoff_id"] for item in discover_pending_handoffs(instance_path)}
    state["pending_events"] = [
        item for item in state.get("pending_events", []) if item.get("handoff_id") in remaining_pending_handoff_ids
    ]

    state.setdefault("metrics", {})
    if status == "skipped":
        state["metrics"]["skipped_runs_today"] = state["metrics"].get("skipped_runs_today", 0) + 1
        if request.trigger_type == "heartbeat":
            state["metrics"]["no_op_heartbeats_today"] = state["metrics"].get("no_op_heartbeats_today", 0) + 1
    state["company"]["last_updated"] = finished_at
    if output_paths:
        active_project = state.get("projects", {}).get(request.project)
        if active_project is not None:
            active_project["last_activity_at"] = finished_at
        latest_output_by_agent_project = {
            (item["agent_id"], item["front_matter"].get("project", request.project)): item["path"] for item in recent_outputs
        }
        for task in state.get("task_board", []):
            if task.get("owner_agent") == "MERIDIAN-ORCHESTRATOR" and task.get("project") == request.project:
                task["updated_at"] = finished_at
                task["result_output"] = output_paths[0]
            source_handoff_id = task.get("source_handoff_id", "")
            if source_handoff_id and source_handoff_id not in remaining_pending_handoff_ids:
                task["status"] = "completed"
                task["updated_at"] = finished_at
                if not task.get("result_output"):
                    task["result_output"] = latest_output_by_agent_project.get(
                        (task.get("owner_agent", ""), task.get("project", "")), ""
                    )

    last_runs = state.setdefault("last_runs", [])
    last_runs.append(
        {
            "run_id": run_id,
            "agent": "MERIDIAN-ORCHESTRATOR",
            "project": request.project,
            "task_type": request.task_type,
            "origin": request.origin,
            "trigger_type": request.trigger_type,
            "status": "completed" if status == "success" else status,
            "started_at": started_at,
            "finished_at": finished_at,
            "output": output_paths[0] if output_paths else "",
        }
    )
    state["last_runs"] = last_runs[-50:]
    write_json(instance_path / "outputs/state.json", state)


def execute_meridian_request(
    instance_path: Path,
    request: DispatchRequest,
    state: dict[str, Any],
    schedule: dict[str, Any],
    result: ResultRecord,
) -> ResultRecord:
    meridian_state = state.get("agents", {}).get("MERIDIAN-ORCHESTRATOR", {})
    last_success = parse_iso8601(meridian_state.get("last_success", ""))
    pending_handoffs = discover_pending_handoffs(instance_path)
    open_escalations = discover_open_escalations(instance_path, state)
    recent_outputs = list_recent_agent_outputs(instance_path, schedule, last_success)
    now = current_time(schedule)

    consumed_handoffs = [
        item for item in pending_handoffs if item["to"] == "MERIDIAN-ORCHESTRATOR"
    ]
    new_downstream_handoffs = [
        item
        for item in pending_handoffs
        if item["to"] != "MERIDIAN-ORCHESTRATOR"
        and (last_success is None or parse_iso8601(item.get("created_at", "")) is None or parse_iso8601(item.get("created_at", "")) > last_success)
    ]
    new_recent_outputs = [item for item in recent_outputs if item["is_new"]]
    meaningful_misc_context = any(
        (instance_path / relative_path).exists() for relative_path in request.changed_context if relative_path
    )

    open_escalations, created_escalations = detect_founder_decision_outputs(
        instance_path, new_recent_outputs, open_escalations, now
    )

    meaningful_context = bool(
        consumed_handoffs or open_escalations or new_recent_outputs or new_downstream_handoffs or meaningful_misc_context
    )
    processed_handoff_paths: list[str] = []
    output_paths: list[str] = []
    notes = list(result.notes or [])
    notes.append("meridian_orchestration_pass")
    needs_project_selection = request.origin == "manual" and request.project == PORTFOLIO_PROJECT

    if needs_project_selection:
        filename = f"{now.date().isoformat()}-project-intake.md"
        output_path = instance_path / "outputs" / "MERIDIAN-ORCHESTRATOR" / filename
        front_matter = {
            "artifact_type": "founder_intake",
            "audience": "founder",
            "project": PORTFOLIO_PROJECT,
            "task_type": "project_selection",
            "origin": request.origin,
            "source_run_id": result.run_id,
            "status": "waiting_on_founder",
            "google_drive_id": "",
            "google_doc_id": "",
            "communication_thread_id": f"meridian-intake-{now.strftime('%Y%m%d')}",
        }
        body = build_meridian_project_intake(state, instance_path)
        write_markdown_with_front_matter(output_path, front_matter, body)
        output_paths.append(output_path.relative_to(instance_path).as_posix())
        result.status = "waiting_on_founder"
        notes.append("project_selection_requested")
    elif not meaningful_context:
        result.status = "skipped"
        notes.append("no_meaningful_changed_context")
    else:
        processed_handoff_paths = [item["path"] for item in consumed_handoffs]
        if processed_handoff_paths:
            mark_handoffs_processed(instance_path, processed_handoff_paths, result.run_id, result.finished_at)
            notes.append(f"processed_{len(processed_handoff_paths)}_handoff(s)")

        remaining_pending_handoffs = [
            item for item in pending_handoffs if item["path"] not in set(processed_handoff_paths)
        ]
        filename = f"{now.date().isoformat()}-founder-briefing.md"
        output_path = project_output_dir(instance_path, request.project, "MERIDIAN-ORCHESTRATOR", state) / filename
        front_matter = {
            "artifact_type": "founder_briefing",
            "audience": "founder",
            "project": request.project,
            "task_type": request.task_type,
            "origin": request.origin,
            "source_run_id": result.run_id,
            "status": "completed",
            "google_drive_id": "",
            "google_doc_id": "",
            "communication_thread_id": f"meridian-{now.strftime('%Y%m%d')}",
        }
        body = build_meridian_briefing(
            state=state,
            pending_handoffs=remaining_pending_handoffs,
            open_escalations=open_escalations,
            recent_outputs=recent_outputs,
            processed_handoff_paths=processed_handoff_paths,
        )
        write_markdown_with_front_matter(output_path, front_matter, body)
        output_paths.append(output_path.relative_to(instance_path).as_posix())
        result.status = "success"
        notes.append("founder_output_created")

    post_state = load_state(instance_path)
    update_meridian_state(
        instance_path=instance_path,
        state=post_state,
        schedule=schedule,
        request=request,
        run_id=result.run_id,
        started_at=result.started_at,
        finished_at=result.finished_at,
        status=result.status,
        post_context_hash="",
        output_paths=output_paths,
        processed_handoff_paths=processed_handoff_paths,
        open_escalations=open_escalations,
        recent_outputs=recent_outputs,
    )
    temp_request = DispatchRequest(**asdict(request))
    post_context_hash = compute_context_hash(
        instance_path,
        schedule.get("agents", {}).get("MERIDIAN-ORCHESTRATOR", {}),
        temp_request,
    )
    updated_state = load_state(instance_path)
    updated_state["agents"]["MERIDIAN-ORCHESTRATOR"]["context_hash"] = post_context_hash
    write_json(instance_path / "outputs/state.json", updated_state)

    result.output_path = output_paths[0] if output_paths else ""
    result.output_paths = output_paths
    result.state_updated = True
    result.processed_handoffs_count = len(processed_handoff_paths)
    result.processed_escalations_count = 0
    result.created_escalations_count = created_escalations
    result.context_hash = post_context_hash
    result.notes = notes
    return result


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
    if status == "completed":
        if request.agent_id == "MERIDIAN-ORCHESTRATOR":
            result = execute_meridian_request(instance_path, request, state, schedule, result)
        else:
            schedule_entry = schedule.get("agents", {}).get(request.agent_id, {})
            specialist_result = execute_specialist(
                instance_path=instance_path,
                agent_id=request.agent_id,
                schedule_entry=schedule_entry,
                request=request,
                run_id=result.run_id,
            )
            result.status = specialist_result.status
            result.output_path = specialist_result.output_paths[0] if specialist_result.output_paths else ""
            result.output_paths = specialist_result.output_paths
            result.processed_handoffs_count = len(specialist_result.processed_handoff_paths)
            result.created_handoffs_count = len(specialist_result.created_handoff_paths)
            specialist_notes = ["real_specialist_execution"] if request.agent_id in ENABLED_SPECIALISTS else []
            result.notes = list(result.notes or []) + specialist_notes + specialist_result.notes

    result_path = instance_path / "runtime/results" / f"{run_id}.json"
    write_json(result_path, asdict(result))

    request_path.unlink(missing_ok=True)
    (instance_path / "runtime/queue" / f"{request.request_id}.json").unlink(missing_ok=True)
    return {
        "run_id": run_id,
        "status": result.status,
        "result_path": result_path.relative_to(instance_path).as_posix(),
        "notes": result.notes or [],
        "error": error,
    }


def drain_queue(instance_path: Path, limit: int | None = None) -> dict[str, Any]:
    ensure_runtime_dirs(instance_path)
    trim_runtime_manifests(instance_path)
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
            queue_path.unlink(missing_ok=True)
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
                    project=reply.get("project", STARTUP_WIDE_PROJECT),
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
    trim_runtime_manifests(instance_path)
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
    run_once_parser.add_argument("--project", default=PORTFOLIO_PROJECT)
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
