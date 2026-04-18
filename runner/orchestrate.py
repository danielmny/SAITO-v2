from __future__ import annotations

import argparse
import hmac
import hashlib
import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner.communications import Message, get_default_channel
from runner.projects import upsert_project_from_intake
from runner.specialists import ENABLED_SPECIALISTS, execute_specialist


ROOT_DIRS = (
    "runtime/requests",
    "runtime/queue",
    "runtime/results",
    "runtime/logs",
    "outputs/communications/outbox",
    "inputs/founder-replies",
    "inputs/founder-replies/processed",
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
PROJECT_SETUP_TASK_TYPE = "project_setup"
KICKOFF_TASK_TYPES = {
    "market_validation",
    "architecture_exploration",
    "product_framing",
    "economics_assessment",
}
INTAKE_QUESTION_SPECS = [
    ("What should we call this project?", "project_name"),
    ("What project key should SAITO use for it?", "project_key"),
    ("What kind of project is it?", "project_type"),
    ("What stage is it in right now?", "stage"),
    ("Give me the one-line summary.", "summary"),
    ("What is the main objective right now?", "objective"),
    ("What core problem does it solve?", "core_problem"),
    ("Who feels this problem most directly?", "who_feels_it"),
    ("Why does this matter now?", "why_now"),
    ("Who is the primary ICP?", "primary_icp"),
    ("What observable traits define that ICP?", "observable_traits"),
    ("Who are the likely early adopters?", "early_adopters"),
    ("What is the product wedge?", "product_wedge"),
    ("What is the core workflow?", "core_workflow"),
    ("Why does this win over alternatives?", "why_it_wins"),
    ("What evidence do we already have?", "evidence_collected"),
    ("Which assumptions still need testing?", "assumptions_to_test"),
    ("What are the next proof steps?", "next_proof_steps"),
    ("What is the go-to-market plan?", "go_to_market"),
    ("How should we position it?", "positioning"),
    ("What are the key risks?", "key_risks"),
    ("What is the revenue model?", "revenue_model"),
    ("What do costs and burn look like?", "costs_and_burn"),
    ("Any fundraising notes?", "fundraising_notes"),
    ("What is on the roadmap now?", "roadmap_now"),
    ("What comes next on the roadmap?", "roadmap_next"),
    ("What is later on the roadmap?", "roadmap_later"),
    ("What open decisions are still unresolved?", "open_decisions"),
    ("What decisions are already locked?", "locked_decisions"),
    ("What should we revisit later?", "revisit_later"),
]
INTAKE_FIELD_TO_QUESTION = {field: question for question, field in INTAKE_QUESTION_SPECS}
PROJECT_CHOICE_SPECS = [
    ("Should we continue on the last open project, or should we start a new one?", "project_choice"),
]
INLINE_ACTION_SPECS = {
    "run_kickoff_bundle": {
        "label": "run kickoff bundle",
        "task_types": {
            "market_validation",
            "architecture_exploration",
            "product_framing",
            "economics_assessment",
            "sales_motion",
            "positioning_brief",
            "project_checkpoint",
        },
    },
    "run_research_pass": {
        "label": "run research pass",
        "task_types": {"market_validation"},
    },
    "run_architecture_pass": {
        "label": "run architecture pass",
        "task_types": {"architecture_exploration"},
    },
    "run_product_pass": {
        "label": "run product framing pass",
        "task_types": {"product_framing"},
    },
    "run_economics_pass": {
        "label": "run economics pass",
        "task_types": {"economics_assessment"},
    },
    "run_project_checkpoint": {
        "label": "run project checkpoint",
        "task_types": {"project_checkpoint"},
    },
}


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


def intake_field_aliases() -> dict[str, str]:
    aliases = {
        "project choice": "project_choice",
        "project name": "project_name",
        "project key": "project_key",
        "project type": "project_type",
        "stage": "stage",
        "summary": "summary",
        "objective": "objective",
        "core problem": "core_problem",
        "who feels it": "who_feels_it",
        "why now": "why_now",
        "primary icp": "primary_icp",
        "observable traits": "observable_traits",
        "early adopters": "early_adopters",
        "product wedge": "product_wedge",
        "core workflow": "core_workflow",
        "why it wins": "why_it_wins",
        "evidence collected": "evidence_collected",
        "assumptions to test": "assumptions_to_test",
        "next proof steps": "next_proof_steps",
        "go-to-market": "go_to_market",
        "positioning": "positioning",
        "key risks": "key_risks",
        "revenue model": "revenue_model",
        "costs and burn": "costs_and_burn",
        "fundraising notes": "fundraising_notes",
        "roadmap now": "roadmap_now",
        "roadmap next": "roadmap_next",
        "roadmap later": "roadmap_later",
        "open decisions": "open_decisions",
        "locked decisions": "locked_decisions",
        "revisit later": "revisit_later",
    }
    for question, field in INTAKE_QUESTION_SPECS:
        aliases[question.lower()] = field
    return aliases


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


def load_communications(instance_path: Path) -> dict[str, Any]:
    return load_json(instance_path / "config/communications.json")


def founder_reply_auth_config(instance_path: Path) -> dict[str, Any]:
    communications = load_communications(instance_path)
    config = communications.get("founder_reply_auth", {})
    return {
        "required": config.get("required", True),
        "secret_env_var": config.get("secret_env_var", "SAITO_FOUNDER_REPLY_SECRET"),
        "reply_ttl_hours": int(config.get("reply_ttl_hours", 24) or 24),
    }


def founder_reply_secret(instance_path: Path) -> str:
    config = founder_reply_auth_config(instance_path)
    env_var = str(config.get("secret_env_var", "SAITO_FOUNDER_REPLY_SECRET"))
    return os.environ.get(env_var, "")


def founder_reply_auth_store(state: dict[str, Any]) -> dict[str, Any]:
    return state.setdefault(
        "founder_reply_auth",
        {"active_threads": {}, "used_reply_ids": [], "rejected_replies": []},
    )


def prune_founder_reply_auth(state: dict[str, Any], now: datetime) -> None:
    auth_state = founder_reply_auth_store(state)
    active_threads = auth_state.setdefault("active_threads", {})
    stale_keys: list[str] = []
    for thread_key, item in active_threads.items():
        expires_at = parse_iso8601(str(item.get("expires_at", "")))
        if expires_at is not None and now > expires_at:
            stale_keys.append(thread_key)
    for thread_key in stale_keys:
        active_threads.pop(thread_key, None)
    auth_state["used_reply_ids"] = auth_state.get("used_reply_ids", [])[-200:]
    auth_state["rejected_replies"] = auth_state.get("rejected_replies", [])[-50:]


def compute_reply_signature(*, secret: str, thread_key: str, session_id: str, reply_token: str, body_markdown: str) -> str:
    payload = "\n".join([thread_key.strip(), session_id.strip(), reply_token.strip(), body_markdown.strip()])
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_founder_reply_challenge(
    *,
    instance_path: Path,
    state: dict[str, Any],
    project: str,
    thread_key: str,
    session_id: str,
    now: datetime,
) -> dict[str, str]:
    auth_state = founder_reply_auth_store(state)
    active_threads = auth_state.setdefault("active_threads", {})
    ttl_hours = founder_reply_auth_config(instance_path).get("reply_ttl_hours", 24)
    reply_token = secrets.token_hex(16)
    active_threads[thread_key] = {
        "thread_key": thread_key,
        "session_id": session_id,
        "project": project,
        "reply_token": reply_token,
        "issued_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(timespec="seconds"),
        "status": "open",
    }
    config = founder_reply_auth_config(instance_path)
    return {
        "thread_key": thread_key,
        "session_id": session_id,
        "reply_token": reply_token,
        "reply_signature_required": "true" if config.get("required", True) else "false",
        "reply_secret_env_var": str(config.get("secret_env_var", "SAITO_FOUNDER_REPLY_SECRET")),
    }


def dispatcher_execution_mode(schedule: dict[str, Any]) -> str:
    return str(schedule.get("dispatcher", {}).get("execution_mode", "hybrid")).strip().lower() or "hybrid"


def max_event_loop_iterations(schedule: dict[str, Any]) -> int:
    configured = schedule.get("dispatcher", {}).get("max_event_loop_iterations", 4)
    try:
        return max(1, int(configured))
    except (TypeError, ValueError):
        return 4


def intake_session_store(state: dict[str, Any]) -> dict[str, Any]:
    return state.setdefault("founder_intake", {"active_session_id": "", "sessions": {}})


def active_intake_session(state: dict[str, Any]) -> dict[str, Any] | None:
    intake_state = intake_session_store(state)
    session_id = str(intake_state.get("active_session_id", "")).strip()
    if not session_id:
        return None
    return intake_state.setdefault("sessions", {}).get(session_id)


def session_question_specs(session: dict[str, Any]) -> list[tuple[str, str]]:
    if session.get("mode") == "project_choice":
        return PROJECT_CHOICE_SPECS
    return INTAKE_QUESTION_SPECS


def next_intake_question(session: dict[str, Any]) -> tuple[str, str] | None:
    answers = session.get("answers", {})
    for question, field in session_question_specs(session):
        if str(answers.get(field, "")).strip():
            continue
        return question, field
    return None


def last_open_project(state: dict[str, Any]) -> str:
    candidate = str(state.get("agents", {}).get("MERIDIAN-ORCHESTRATOR", {}).get("active_project", "")).strip()
    if candidate and candidate not in {PORTFOLIO_PROJECT, STARTUP_WIDE_PROJECT}:
        return candidate
    for project in sorted(state.get("projects", {}).keys()):
        if project not in {PORTFOLIO_PROJECT, STARTUP_WIDE_PROJECT}:
            return project
    return ""


def start_intake_session(state: dict[str, Any], now: datetime, *, mode: str = "project_choice") -> dict[str, Any]:
    intake_state = intake_session_store(state)
    session_id = f"intake-{now.strftime('%Y%m%dT%H%M%S')}"
    question_specs = PROJECT_CHOICE_SPECS if mode == "project_choice" else INTAKE_QUESTION_SPECS
    session = {
        "session_id": session_id,
        "status": "in_progress",
        "started_at": now.isoformat(timespec="seconds"),
        "updated_at": now.isoformat(timespec="seconds"),
        "project": last_open_project(state) or PORTFOLIO_PROJECT,
        "mode": mode,
        "answers": {},
        "question_order": [field for _question, field in question_specs],
        "last_question": question_specs[0][1],
        "asked_questions": [question_specs[0][1]],
        "delivery_mode": "conversational",
    }
    intake_state.setdefault("sessions", {})[session_id] = session
    intake_state["active_session_id"] = session_id
    return session


def merge_intake_answers(session: dict[str, Any], answers: dict[str, str], now: datetime) -> dict[str, Any]:
    stored_answers = session.setdefault("answers", {})
    for key, value in answers.items():
        if not value.strip():
            continue
        stored_answers[key] = value.strip()
    next_question = next_intake_question(session)
    session["updated_at"] = now.isoformat(timespec="seconds")
    if next_question is None:
        session["status"] = "completed"
        session["last_question"] = ""
    else:
        _question_text, next_field = next_question
        session["status"] = "in_progress"
        session["last_question"] = next_field
        asked = session.setdefault("asked_questions", [])
        if next_field not in asked:
            asked.append(next_field)
    return session


def latest_project_outputs(instance_path: Path, project: str) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    for agent_id in sorted(load_state(instance_path).get("agents", {}).keys()):
        latest_match: Path | None = None
        for path in reversed(list_agent_output_files(instance_path, agent_id)):
            front_matter, body = read_front_matter(path)
            if front_matter.get("project", "") != project:
                continue
            latest_match = path
            summary = next((line.strip("- ").strip() for line in body.splitlines() if line.startswith("- ")), "")
            outputs.append(
                {
                    "agent_id": agent_id,
                    "path": path.relative_to(instance_path).as_posix(),
                    "summary": summary or (body.splitlines()[0].strip() if body.splitlines() else ""),
                }
            )
            break
        if latest_match is None:
            continue
    return outputs


def build_project_standup(state: dict[str, Any], instance_path: Path, project: str) -> dict[str, list[str]]:
    project_meta = state.get("projects", {}).get(project, {})
    summary = [f"- Project: `{project_meta.get('name', project)}`", f"- Summary: {project_meta.get('summary', 'No summary yet.')}", f"- Stage: `{project_meta.get('stage', 'IDEA') if project_meta.get('stage') else 'IDEA'}`"]
    outputs = latest_project_outputs(instance_path, project)
    wins = [f"- `{item['agent_id']}`: {item['summary'] or 'Completed recent project work.'}" for item in outputs[:4]] or ["- No specialist outputs yet."]
    pending_handoffs = [item for item in discover_pending_handoffs(instance_path) if item["project"] == project]
    blockers = [f"- Waiting on `{item['to']}` for `{item['task_type']}`." for item in pending_handoffs[:4]] or ["- No active blockers recorded."]
    task_board = state.get("task_board", [])
    open_tasks = [task for task in task_board if task.get("project") == project and task.get("status") not in {"completed", "stale"}]
    next_steps = [f"- `{task.get('title', task.get('task_type', 'next task'))}` with `{task.get('owner_agent', 'unassigned')}`." for task in open_tasks[:4]]
    if not next_steps:
        next_steps = [f"- Continue the next highest-value proof, GTM, product, or architecture task for `{project}`."]
    challenges = []
    for path_name in ["validation.md", "strategy.md", "financials.md", "icp.md", "solution.md"]:
        path = project_root(instance_path, project, state)
        if path is None:
            continue
        file_path = path / path_name
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8").lower()
        if "tbd" in content or "undetermined" in content or "needs research" in content:
            challenges.append(f"- `{path_name}` still contains unresolved hypotheses or TBD sections.")
    if not challenges:
        challenges = ["- No explicit project-file blockers surfaced beyond current queued work."]
    return {
        "summary": summary,
        "wins": wins,
        "challenges": challenges[:4],
        "blockers": blockers,
        "next_steps": next_steps,
    }


def project_output_after(instance_path: Path, project: str, agent_id: str, created_at: str) -> bool:
    created = parse_iso8601(created_at)
    for path in reversed(list_agent_output_files(instance_path, agent_id)):
        front_matter, _body = read_front_matter(path)
        if front_matter.get("project", "") != project:
            continue
        if created is None:
            return True
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified >= created.astimezone(timezone.utc):
            return True
    return False


def bundle_status_snapshot(
    *,
    instance_path: Path,
    state: dict[str, Any],
    schedule: dict[str, Any],
    pending_handoffs: list[dict[str, Any]],
    project: str,
) -> list[dict[str, str]]:
    snapshots: list[dict[str, str]] = []
    queue_payloads = []
    for path in sorted((instance_path / "runtime/queue").glob("*.json")):
        try:
            queue_payloads.append(load_json(path))
        except json.JSONDecodeError:
            continue
    for item in pending_handoffs:
        front_matter = item.get("front_matter", {})
        if item["project"] != project or not front_matter.get("parallel_group"):
            continue
        status = "queued_for_next_window"
        if project_output_after(instance_path, project, item["to"], item.get("created_at", "")):
            status = "completed"
        else:
            request = build_request(
                agent_id=item["to"],
                trigger_type="event",
                reason=item["reason"],
                run_timestamp=current_time(schedule).isoformat(timespec="seconds"),
                changed_context=[item["path"]],
                instance_path=instance_path,
                project=item["project"],
                task_type=item["task_type"],
                origin=item["origin"],
            )
            token_policy = resolve_token_policy(instance_path, state, item["to"])
            eligible, reason = can_enqueue_request(request, state, schedule, token_policy, instance_path)
            if any(item["path"] in payload.get("changed_context", []) for payload in queue_payloads):
                status = "running_now" if item["to"] == "MERIDIAN-ORCHESTRATOR" else "queued"
            elif eligible:
                status = "queued"
            elif reason.startswith("waiting_for_") or reason.startswith("blocked_on_"):
                status = "blocked_by_dependency"
            elif reason.startswith("quiet_hours"):
                status = "queued_for_next_window"
            elif reason == "context_unchanged":
                status = "skipped_as_unnecessary"
            else:
                status = reason
        snapshots.append(
            {
                "agent_id": item["to"],
                "task_type": item["task_type"],
                "wave": front_matter.get("wave", "unscoped"),
                "bundle": front_matter.get("kickoff_bundle", ""),
                "status": status,
            }
        )
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for item in snapshots:
        unique[(item["agent_id"], item["task_type"])] = item
    return list(unique.values())


def recommended_action_lines(project: str) -> list[str]:
    return [
        f"- Reply `run kickoff bundle for {project}` to queue the full coordinated first and second wave.",
        f"- Reply `run research pass for {project}` to queue only market validation.",
        f"- Reply `run architecture pass for {project}` to queue only engineering architecture work.",
        f"- Reply `run product framing pass for {project}` to queue only product framing work.",
        f"- Reply `run economics pass for {project}` to queue only finance and unit-economics work.",
        f"- Reply `run project checkpoint for {project}` to force a synthesized founder briefing.",
    ]


def parse_founder_action_request(reply_body: str) -> str:
    normalized = reply_body.strip().lower()
    if "kickoff bundle" in normalized:
        return "run_kickoff_bundle"
    if "research pass" in normalized:
        return "run_research_pass"
    if "architecture pass" in normalized:
        return "run_architecture_pass"
    if "product framing pass" in normalized or "product pass" in normalized:
        return "run_product_pass"
    if "economics pass" in normalized or "finance pass" in normalized:
        return "run_economics_pass"
    if "project checkpoint" in normalized or "synthesi" in normalized:
        return "run_project_checkpoint"
    return ""


def parse_project_choice_reply(reply_body: str, session: dict[str, Any], state: dict[str, Any]) -> str:
    normalized = reply_body.strip().lower()
    project = str(session.get("project", "")).strip() or last_open_project(state)
    if any(token in normalized for token in ["new project", "start a new", "start new", "new one"]):
        return "start_new"
    if project:
        project_meta = state.get("projects", {}).get(project, {})
        project_name = str(project_meta.get("name", project)).lower()
        project_slug_value = str(project_meta.get("slug", project_slug(project, state))).lower()
        if project.lower() in normalized or project_name in normalized or project_slug_value in normalized:
            return "continue_last"
    if any(token in normalized for token in ["continue", "last open", "last project", "current project"]):
        return "continue_last"
    return "continue_last"


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_boolish(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_hot_path_request(request: DispatchRequest, overrides: dict[str, Any] | None = None) -> bool:
    effective_overrides = overrides or {}
    if request.trigger_type == "manual":
        return True
    if request.origin in {"founder_reply", "handoff", "integration", "manual"}:
        return True
    if request.task_type in CRITICAL_TASK_TYPES | KICKOFF_TASK_TYPES | {
        PROJECT_SETUP_TASK_TYPE,
        "project_selection",
        "project_status_report",
        "project_checkpoint",
        "founder_session_summary",
        "founder_action_acceptance",
    }:
        return True
    if effective_overrides.get("founder_priority", False):
        return True
    return False


def question_prompt(question: str) -> str:
    examples = {
        "What is the core workflow?": "Describe the simplest end-to-end transaction flow you want to support first.",
        "What is the product wedge?": "Name the narrowest entry point that can win early adoption before the full platform exists.",
        "What observable traits define that ICP?": "List behaviors or characteristics we can actually look for when deciding who to interview or target.",
    }
    return examples.get(question, "")


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


def sanitize_front_matter_value(value: Any) -> str:
    text = str(value)
    return " ".join(text.replace("\r", "\n").splitlines()).strip()


def write_front_matter(path: Path, front_matter: dict[str, str], body: str) -> None:
    lines = ["---"]
    for key, value in front_matter.items():
        lines.append(f"{key}: {sanitize_front_matter_value(value)}")
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


def dependency_satisfied(
    instance_path: Path,
    agent_state: dict[str, Any],
    dependency: str,
    project: str,
) -> bool:
    for path in reversed(list_agent_output_files(instance_path, dependency)):
        front_matter, _body = read_front_matter(path)
        if front_matter.get("project", "") == project:
            return True
    if bool(agent_state.get("last_success")) or agent_state.get("status") in {"success", "completed"}:
        return True
    return latest_runtime_result_status(instance_path, dependency, required_status="success") == "success"


def dependency_satisfaction_count(
    instance_path: Path,
    state: dict[str, Any],
    dependencies: list[str],
    project: str,
) -> int:
    satisfied = 0
    for dependency in dependencies:
        if dependency_satisfied(instance_path, state.get("agents", {}).get(dependency, {}), dependency, project):
            satisfied += 1
    return satisfied


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
    founder_priority = request.origin in {"founder_reply", "founder_request", "manual"} or request.task_type in KICKOFF_TASK_TYPES
    if founder_priority and request.task_type != "founder_digest":
        return None

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
    required_keys = {"handoff_id", "from", "to", "project", "task_type", "origin", "status", "created_at", "reason", "source_output"}
    for handoff_path in sorted(handoff_dir.glob("*.md")):
        front_matter, _body = read_front_matter(handoff_path)
        if not required_keys.issubset(front_matter.keys()):
            continue
        if front_matter.get("status") != "queued":
            continue
        to_agent = normalize_agent_id(front_matter.get("to", ""))
        from_agent = normalize_agent_id(front_matter.get("from", ""))
        if not to_agent:
            continue
        if parse_iso8601(front_matter.get("created_at", "")) is None:
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


def handoff_runtime_overrides(instance_path: Path, request: DispatchRequest) -> dict[str, Any]:
    overrides = {
        "founder_priority": False,
        "dependency_mode": "strict",
        "depends_on_any": [],
        "depends_on_all": [],
        "minimum_dependencies_satisfied": 1,
        "refinement_run": False,
        "kickoff_bundle": "",
        "parallel_group": "",
        "wave": "",
    }
    for relative_path in request.changed_context:
        path = instance_path / relative_path
        if not path.exists() or path.suffix != ".md":
            continue
        front_matter, _body = read_front_matter(path)
        if front_matter.get("founder_priority", "").lower() == "true":
            overrides["founder_priority"] = True
        dependency_mode = front_matter.get("dependency_mode", "").strip()
        if dependency_mode:
            overrides["dependency_mode"] = dependency_mode
        depends_on_any = parse_csv_list(front_matter.get("depends_on_any", ""))
        if depends_on_any:
            overrides["depends_on_any"] = [normalize_agent_id(item) for item in depends_on_any]
        depends_on_all = parse_csv_list(front_matter.get("depends_on_all", ""))
        if depends_on_all:
            overrides["depends_on_all"] = [normalize_agent_id(item) for item in depends_on_all]
        minimum_dependencies = front_matter.get("minimum_dependencies_satisfied", "").strip()
        if minimum_dependencies.isdigit():
            overrides["minimum_dependencies_satisfied"] = int(minimum_dependencies)
        if parse_boolish(front_matter.get("refinement_run", "")):
            overrides["refinement_run"] = True
        for key in ("kickoff_bundle", "parallel_group", "wave"):
            value = front_matter.get(key, "").strip()
            if value:
                overrides[key] = value
    return overrides


def kickoff_bundle_specs(project: str, stage: str, session_id: str) -> list[dict[str, str]]:
    bundle_name = "idea_validation_bundle" if stage.upper() == "IDEA" else "project_kickoff_bundle"
    parallel_group = f"{project_slug(project)}-{bundle_name}-{session_id[-8:]}"
    first_wave = [
        {
            "to": "ATLAS-RESEARCH",
            "task_type": "market_validation",
            "subject": "Market Validation Kickoff",
            "reason": "Project setup completed with unresolved market, ICP, wedge, and validation questions.",
            "action_required": "Produce a research brief covering competitors, adjacent alternatives, likely ICP segments, urgency, and the first validation interviews or tests.",
            "kickoff_action": "run_research_pass",
            "wave": "first_wave",
            "parallel_group": parallel_group,
            "kickoff_bundle": bundle_name,
        },
        {
            "to": "FORGE-ENGINEERING",
            "task_type": "architecture_exploration",
            "subject": "Architecture Exploration Kickoff",
            "reason": "Project setup completed with open architecture, security, and settlement questions.",
            "action_required": "Outline candidate architectures, core entities and ledgers, trust and security concerns, and the smallest technical proof loop worth building first.",
            "kickoff_action": "run_architecture_pass",
            "wave": "first_wave",
            "parallel_group": parallel_group,
            "kickoff_bundle": bundle_name,
        },
        {
            "to": "CANVAS-PRODUCT",
            "task_type": "product_framing",
            "subject": "Product Wedge Kickoff",
            "reason": "Project setup completed without a locked wedge, proof loop, or validation-first roadmap.",
            "action_required": "Define the narrowest product wedge, the first proof-generating workflow, and a validation-first Now / Next / Later roadmap.",
            "kickoff_action": "run_product_pass",
            "wave": "first_wave",
            "parallel_group": parallel_group,
            "kickoff_bundle": bundle_name,
        },
        {
            "to": "LEDGER-FINANCE",
            "task_type": "economics_assessment",
            "subject": "Economics Assessment Kickoff",
            "reason": "Project setup completed with open monetization, commission, cost, and unit-economics assumptions.",
            "action_required": "Assess plausible monetization mechanics, cost drivers, unit-economics risks, and the financial assumptions that need testing first.",
            "kickoff_action": "run_economics_pass",
            "wave": "first_wave",
            "parallel_group": parallel_group,
            "kickoff_bundle": bundle_name,
        },
    ]
    second_wave = [
        {
            "to": "CURRENT-SALES",
            "task_type": "sales_motion",
            "subject": "Initial Sales Motion",
            "reason": "Research and product framing should inform the earliest outbound and pilot motion.",
            "action_required": "Translate the current ICP, wedge, and urgency assumptions into an initial outreach and pilot motion.",
            "kickoff_action": "run_kickoff_bundle",
            "wave": "second_wave",
            "parallel_group": parallel_group,
            "kickoff_bundle": bundle_name,
            "dependency_mode": "any",
            "depends_on_any": "ATLAS-RESEARCH,CANVAS-PRODUCT",
            "minimum_dependencies_satisfied": "1",
        },
        {
            "to": "MARKETING-BRAND",
            "task_type": "positioning_brief",
            "subject": "Initial Positioning Brief",
            "reason": "Positioning should start once research or product framing clarifies the first wedge and audience.",
            "action_required": "Draft the first positioning and messaging brief using the initial market and product outputs.",
            "kickoff_action": "run_kickoff_bundle",
            "wave": "second_wave",
            "parallel_group": parallel_group,
            "kickoff_bundle": bundle_name,
            "dependency_mode": "any",
            "depends_on_any": "ATLAS-RESEARCH,CANVAS-PRODUCT",
            "minimum_dependencies_satisfied": "1",
        },
        {
            "to": "MERIDIAN-ORCHESTRATOR",
            "task_type": "project_checkpoint",
            "subject": "Kickoff Bundle Synthesis",
            "reason": "The founder should get a synthesized checkpoint once enough first-wave outputs land.",
            "action_required": "Synthesize the parallel kickoff outputs into one founder-facing checkpoint with conflicts, gaps, and next decisions.",
            "kickoff_action": "run_project_checkpoint",
            "wave": "synthesis_wave",
            "parallel_group": parallel_group,
            "kickoff_bundle": bundle_name,
            "dependency_mode": "any",
            "depends_on_any": "ATLAS-RESEARCH,FORGE-ENGINEERING,CANVAS-PRODUCT,LEDGER-FINANCE",
            "minimum_dependencies_satisfied": "2",
        },
    ]
    return first_wave + second_wave


def create_meridian_handoff_from_spec(
    *,
    instance_path: Path,
    project: str,
    source_output: str,
    now: datetime,
    handoff_id: str,
    item: dict[str, str],
) -> str:
    handoff_path = instance_path / "outputs/handoffs" / f"{handoff_id}.md"
    front_matter = {
        "handoff_id": handoff_id,
        "from": "MERIDIAN-ORCHESTRATOR",
        "to": item["to"],
        "project": project,
        "task_type": item["task_type"],
        "origin": "founder_request",
        "status": "queued",
        "created_at": now.isoformat(timespec="seconds"),
        "reason": item["reason"],
        "source_output": source_output,
        "compatibility": "canonical",
        "founder_priority": "true",
        "dependency_mode": item.get("dependency_mode", "soft"),
        "kickoff_bundle": item.get("kickoff_bundle", ""),
        "parallel_group": item.get("parallel_group", ""),
        "wave": item.get("wave", ""),
        "kickoff_action": item.get("kickoff_action", ""),
        "depends_on_any": item.get("depends_on_any", ""),
        "depends_on_all": item.get("depends_on_all", ""),
        "minimum_dependencies_satisfied": item.get("minimum_dependencies_satisfied", ""),
        "refinement_run": item.get("refinement_run", ""),
    }
    body = "\n".join(
        [
            "## FROM: MERIDIAN-ORCHESTRATOR",
            f"## TO: {item['to']}",
            f"## PROJECT: {project}",
            f"## TASK TYPE: {item['task_type']}",
            "## ORIGIN: founder_request",
            f"## RE: {item['subject']}",
            f"## CONTEXT: Generated automatically from founder project setup session or inline action.",
            f"## OUTPUT: See `{source_output}` for the latest project setup artifact.",
            f"## ACTION REQUIRED: {item['action_required']}",
        ]
    )
    write_front_matter(handoff_path, front_matter, body)
    return handoff_path.relative_to(instance_path).as_posix()


def create_meridian_kickoff_handoffs(
    *,
    instance_path: Path,
    project: str,
    stage: str,
    source_output: str,
    session_id: str,
    now: datetime,
    allowed_actions: set[str] | None = None,
) -> list[str]:
    handoff_dir = instance_path / "outputs/handoffs"
    existing_signatures: set[tuple[str, str, str, str]] = set()
    for existing_path in sorted(handoff_dir.glob("*.md")):
        front_matter, _body = read_front_matter(existing_path)
        if front_matter.get("compatibility") == "legacy":
            continue
        existing_signatures.add(
            (
                front_matter.get("from", ""),
                front_matter.get("to", ""),
                front_matter.get("project", ""),
                front_matter.get("task_type", ""),
            )
        )

    created_paths: list[str] = []
    bundle_specs = kickoff_bundle_specs(project, stage, session_id)
    existing_count = len(list(handoff_dir.glob(f"HANDOFF-{now.date().isoformat()}-MERIDIAN-ORCHESTRATOR-*.md")))
    for index, item in enumerate(bundle_specs, start=1):
        if allowed_actions is not None and item.get("kickoff_action", "") not in allowed_actions:
            continue
        signature = ("MERIDIAN-ORCHESTRATOR", item["to"], project, item["task_type"])
        if signature in existing_signatures:
            continue
        handoff_id = f"HANDOFF-{now.date().isoformat()}-MERIDIAN-ORCHESTRATOR-{existing_count + index:03d}"
        created_paths.append(
            create_meridian_handoff_from_spec(
                instance_path=instance_path,
                project=project,
                source_output=source_output,
                now=now,
                handoff_id=handoff_id,
                item=item,
            )
        )
        existing_signatures.add(signature)
    return created_paths


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

    overrides = handoff_runtime_overrides(instance_path, request)
    agent_state = state.get("agents", {}).get(request.agent_id, {})
    max_runs = schedule_entry.get("max_runs_per_day")
    runs_today = agent_state.get("run_budget", {}).get("runs_today", 0)
    if max_runs is not None and runs_today >= max_runs:
        return False, "max_runs_reached"

    last_run = parse_iso8601(agent_state.get("last_run", ""))
    cooldown_minutes = schedule_entry.get("cooldown_minutes", 0)
    now = current_time(schedule)
    execution_mode = dispatcher_execution_mode(schedule)
    cooldown_exempt = (
        is_hot_path_request(request, overrides) if execution_mode == "hybrid" else (
            request.trigger_type == "manual"
            or request.origin == "founder_reply"
            or request.task_type == "founder_reply"
            or overrides.get("founder_priority", False)
        )
    )
    if not cooldown_exempt and last_run is not None and cooldown_minutes and now < last_run + timedelta(minutes=cooldown_minutes):
        return False, "cooldown_active"

    dependency_mode = overrides.get("dependency_mode", "strict")
    schedule_dependencies = [normalize_agent_id(item) for item in schedule_entry.get("depends_on", [])]
    if dependency_mode == "strict":
        dependencies_to_check = overrides.get("depends_on_all") or schedule_dependencies
        for dependency in dependencies_to_check:
            if not dependency_satisfied(
                instance_path,
                state.get("agents", {}).get(dependency, {}),
                dependency,
                request.project,
            ):
                return False, f"blocked_on_{dependency}"
    elif dependency_mode == "all":
        dependencies_to_check = overrides.get("depends_on_all") or schedule_dependencies
        for dependency in dependencies_to_check:
            if not dependency_satisfied(
                instance_path,
                state.get("agents", {}).get(dependency, {}),
                dependency,
                request.project,
            ):
                return False, f"blocked_on_{dependency}"
    elif dependency_mode == "any":
        dependencies_to_check = overrides.get("depends_on_any") or schedule_dependencies
        required = min(
            max(1, int(overrides.get("minimum_dependencies_satisfied", 1))),
            max(1, len(dependencies_to_check)),
        )
        satisfied = dependency_satisfaction_count(instance_path, state, dependencies_to_check, request.project)
        if dependencies_to_check and satisfied < required:
            return False, f"waiting_for_{required}_dependencies"
    elif dependency_mode == "soft":
        pass

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
    execution_mode = dispatcher_execution_mode(schedule)

    handoffs_by_agent: dict[str, list[dict[str, Any]]] = {}
    for handoff in pending_handoffs:
        handoffs_by_agent.setdefault(handoff["agent_id"], []).append(handoff)
    hot_agents = set(handoffs_by_agent.keys())
    if open_escalations:
        hot_agents.add("MERIDIAN-ORCHESTRATOR")
    if active_intake_session(state) is not None:
        hot_agents.add("MERIDIAN-ORCHESTRATOR")

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
        if execution_mode == "hybrid" and agent_id in hot_agents:
            planning_notes.append(f"{agent_id}:background_suppressed_by_hot_path")
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


def archive_reply_file(instance_path: Path, relative_path: str) -> str:
    source_path = instance_path / relative_path
    if not source_path.exists():
        return ""
    replies_root = (instance_path / "inputs/founder-replies").resolve()
    try:
        source_path.resolve().relative_to(replies_root)
    except ValueError:
        return ""
    processed_dir = instance_path / "inputs/founder-replies" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    target_path = processed_dir / source_path.name
    counter = 1
    while target_path.exists():
        target_path = processed_dir / f"{source_path.stem}-{counter}{source_path.suffix}"
        counter += 1
    source_path.rename(target_path)
    return target_path.relative_to(instance_path).as_posix()


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
    instance_path: Path,
    state: dict[str, Any],
    schedule: dict[str, Any],
    project: str,
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
    parallel_snapshot = bundle_status_snapshot(
        instance_path=instance_path,
        state=state,
        schedule=schedule,
        pending_handoffs=pending_handoffs,
        project=project,
    )
    parallel_status_lines = [
        f"- `{item['agent_id']}` `{item['task_type']}` [{item['wave']}] -> `{item['status']}`."
        for item in parallel_snapshot
    ] or ["- No parallel kickoff bundle is currently queued."]
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
            "## Parallel Execution Status",
            *parallel_status_lines,
            "",
            "## Escalation Summary",
            *escalation_summary_lines,
        ]
    )


def build_meridian_project_intake(state: dict[str, Any], instance_path: Path, session: dict[str, Any]) -> str:
    if session.get("mode") == "project_choice":
        project = str(session.get("project", "")).strip() or last_open_project(state)
        projects = known_startup_projects(instance_path, state)
        project_lines = [f"- `{item['name']}` (`{item['slug']}`): {item['summary']}" for item in projects] or [
            "- No startup projects are registered yet. Start a new project."
        ]
        standup = build_project_standup(state, instance_path, project) if project else {
            "summary": ["- No last open project is available."],
            "wins": ["- No prior project work available."],
            "challenges": ["- A new project needs to be created."],
            "blockers": ["- None."],
            "next_steps": ["- Start a new project."],
        }
        return "\n".join(
            [
                "[Acting as: MERIDIAN-ORCHESTRATOR]",
                "",
                "# Founder Standup",
                "",
                "Here is the current status of the last open project and the team so far.",
                "",
                "## Active Startup Projects",
                *project_lines,
                "",
                "## Last Open Project Summary",
                *standup["summary"],
                "",
                "## Wins",
                *standup["wins"],
                "",
                "## Current Challenges",
                *standup["challenges"],
                "",
                "## Blockers",
                *standup["blockers"],
                "",
                "## Next Steps",
                *standup["next_steps"],
                "",
                "## Recommended Actions",
                *recommended_action_lines(project or "this project"),
                "",
                "## Current Question",
                "",
                "## Should we continue on the last open project, or should we start a new one?",
                "",
                "Reply with either `continue on CreditBank` or `start a new project`.",
            ]
        )

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
    next_question = next_intake_question(session)
    asked_fields = [field for field in session.get("asked_questions", []) if session.get("answers", {}).get(field, "").strip()]
    known_answer_lines = [
        f"- {INTAKE_FIELD_TO_QUESTION[field]} {session['answers'][field]}"
        for field in asked_fields[-5:]
    ] or ["- No answers captured yet."]
    progress_line = f"{len(session.get('answers', {}))} of {len(INTAKE_QUESTION_SPECS)} intake answers captured."
    return "\n".join(
        [
            "[Acting as: MERIDIAN-ORCHESTRATOR]",
            "",
            "# Founder Project Intake Required",
            "",
            "Let’s set up or refine a startup project properly.",
            "This intake is conversational and stateful. Reply with the answer to the current question only, and MERIDIAN will persist progress automatically.",
            "",
            "## Active Startup Projects",
            *project_lines,
            "",
            "## Intake Progress",
            f"- Session ID: `{session['session_id']}`",
            f"- Progress: {progress_line}",
                "",
                "## Suggested Next Steps",
                *next_step_lines,
                "",
                "## Recommended Actions",
                *recommended_action_lines(session.get("project", "this project")),
                "",
                "## Recent Answers",
            "",
            *known_answer_lines,
            "",
            "## Current Question",
            "",
            f"## {next_question[0] if next_question else 'Intake complete.'}",
            question_prompt(next_question[0]) if next_question else "MERIDIAN can now populate the project files and trigger kickoff work.",
            "",
            "## Reply Format",
            "",
            f"## {next_question[0] if next_question else 'Intake complete.'}",
            "",
            "<your answer>",
            "",
            "## File Reply Security",
            "",
            "If replying through `inputs/founder-replies/`, copy the `thread_key`, `session_id`, and `reply_token` from front matter, then run `python3 runner/orchestrate.py sign-founder-reply --instance-path . --reply-file inputs/founder-replies/<your-file>.md` before ingesting.",
        ]
    )


def extract_markdown_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_heading = ""
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip().lower()
            current_lines = []
            continue
        current_lines.append(line)
    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()
    return sections


def founder_reply_intake_answers(reply_body: str) -> dict[str, str]:
    sections = extract_markdown_sections(reply_body)
    aliases = intake_field_aliases()
    answers: dict[str, str] = {}
    if not sections and reply_body.strip():
        stripped = reply_body.strip()
        first_line = stripped.splitlines()[0].strip().lower()
        if first_line in aliases:
            sections[first_line] = "\n".join(stripped.splitlines()[1:]).strip()
        else:
            sections[""] = stripped
    for source, value in sections.items():
        target = aliases.get(source)
        if target:
            answers[target] = value
    return answers


def validate_founder_reply(
    *,
    instance_path: Path,
    state: dict[str, Any],
    reply_path: Path,
    front_matter: dict[str, str],
    body: str,
) -> tuple[bool, str, dict[str, str]]:
    replies_root = (instance_path / "inputs/founder-replies").resolve()
    try:
        reply_path.resolve().relative_to(replies_root)
    except ValueError:
        return False, "reply_outside_inbox", {}
    auth_state = founder_reply_auth_store(state)
    used_reply_ids = set(auth_state.setdefault("used_reply_ids", []))
    thread_key = str(front_matter.get("thread_key", "")).strip()
    reply_id = str(front_matter.get("reply_id", reply_path.stem)).strip()
    session_id = str(front_matter.get("session_id", "")).strip()
    reply_token = str(front_matter.get("reply_token", "")).strip()
    reply_signature = str(front_matter.get("reply_signature", "")).strip()
    project = str(front_matter.get("project", "")).strip()
    if reply_id in used_reply_ids:
        return False, "replayed_reply_id", {}
    if not thread_key:
        return False, "missing_thread_key", {}
    active_thread = auth_state.setdefault("active_threads", {}).get(thread_key)
    if not active_thread:
        return False, "unknown_thread_key", {}
    expires_at = parse_iso8601(str(active_thread.get("expires_at", "")))
    if expires_at is not None and datetime.now(expires_at.tzinfo or timezone.utc) > expires_at:
        return False, "expired_reply_token", {}
    if session_id != str(active_thread.get("session_id", "")).strip():
        return False, "session_mismatch", {}
    if reply_token != str(active_thread.get("reply_token", "")).strip():
        return False, "reply_token_mismatch", {}
    if project and project != str(active_thread.get("project", "")).strip():
        return False, "project_mismatch", {}
    config = founder_reply_auth_config(instance_path)
    secret = founder_reply_secret(instance_path)
    if config.get("required", True):
        if not secret:
            return False, "missing_reply_secret", {}
        expected_signature = compute_reply_signature(
            secret=secret,
            thread_key=thread_key,
            session_id=session_id,
            reply_token=reply_token,
            body_markdown=body,
        )
        if not hmac.compare_digest(reply_signature, expected_signature):
            return False, "invalid_reply_signature", {}
    active_session = active_intake_session(state)
    if session_id.startswith("intake-") and active_session is not None:
        if active_session.get("session_id", "") != session_id:
            return False, "inactive_session_reply", {}
    return True, "accepted", {
        "reply_id": reply_id,
        "thread_key": thread_key,
        "session_id": session_id,
        "project": str(active_thread.get("project", "")).strip() or project or STARTUP_WIDE_PROJECT,
    }


def reject_reply_file(instance_path: Path, relative_path: str, reason: str) -> str:
    source_path = instance_path / relative_path
    if not source_path.exists():
        return ""
    rejected_dir = instance_path / "inputs/founder-replies" / "rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    target_path = rejected_dir / source_path.name
    counter = 1
    while target_path.exists():
        target_path = rejected_dir / f"{source_path.stem}-{counter}{source_path.suffix}"
        counter += 1
    front_matter, body = read_front_matter(source_path)
    front_matter["rejection_reason"] = reason
    write_front_matter(target_path, front_matter, body)
    source_path.unlink(missing_ok=True)
    return target_path.relative_to(instance_path).as_posix()


def sign_founder_reply_file(instance_path: Path, reply_path: Path) -> dict[str, str]:
    reply_path = reply_path.resolve()
    instance_path = instance_path.resolve()
    front_matter, body = read_front_matter(reply_path)
    state = load_state(instance_path)
    active_threads = founder_reply_auth_store(state).get("active_threads", {})
    latest_thread = None
    if active_threads:
        latest_thread = sorted(
            active_threads.values(),
            key=lambda item: str(item.get("issued_at", "")),
            reverse=True,
        )[0]
    thread_key = str(front_matter.get("thread_key", "")).strip() or str((latest_thread or {}).get("thread_key", "")).strip()
    session_id = str(front_matter.get("session_id", "")).strip() or str((latest_thread or {}).get("session_id", "")).strip()
    reply_token = str(front_matter.get("reply_token", "")).strip() or str((latest_thread or {}).get("reply_token", "")).strip()
    if not thread_key or not session_id or not reply_token:
        raise SystemExit("Reply file must include `thread_key`, `session_id`, and `reply_token` in front matter.")
    secret = founder_reply_secret(instance_path)
    if not secret:
        config = founder_reply_auth_config(instance_path)
        raise SystemExit(f"Missing founder reply secret in env var `{config['secret_env_var']}`.")
    front_matter["thread_key"] = thread_key
    front_matter["session_id"] = session_id
    front_matter["reply_token"] = reply_token
    if latest_thread and not front_matter.get("project"):
        front_matter["project"] = str(latest_thread.get("project", "")).strip()
    if not front_matter.get("reply_id"):
        front_matter["reply_id"] = reply_path.stem
    front_matter["reply_signature"] = compute_reply_signature(
        secret=secret,
        thread_key=thread_key,
        session_id=session_id,
        reply_token=reply_token,
        body_markdown=body,
    )
    write_front_matter(reply_path, front_matter, body)
    return {
        "status": "signed",
        "reply_path": reply_path.relative_to(instance_path).as_posix(),
        "thread_key": thread_key,
        "session_id": session_id,
    }


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

    intake_state = state.get("founder_intake", {})
    sessions = intake_state.get("sessions", {})
    if sessions:
        state["founder_sessions"] = [
            {
                "session_id": item.get("session_id", session_id),
                "status": item.get("status", ""),
                "project": item.get("project", PORTFOLIO_PROJECT),
                "started_at": item.get("started_at", ""),
                "updated_at": item.get("updated_at", ""),
            }
            for session_id, item in sorted(sessions.items())
        ][-20:]
    prune_founder_reply_auth(state, current_time(schedule))

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


def build_project_setup_body(project_info: dict[str, str], kickoff_handoffs: list[str]) -> str:
    kickoff_lines = [f"- `{path}`" for path in kickoff_handoffs] or ["- No kickoff handoffs were created."]
    return "\n".join(
        [
            "[Acting as: MERIDIAN-ORCHESTRATOR]",
            "",
            f"# Project Setup Completed — {project_info['name']}",
            "",
            f"- Project key: `{project_info['key']}`",
            f"- Project folder: `{project_info['folder_path']}`",
            "- Updated files:",
            f"  - `{project_info['folder_path']}/project.md`",
            f"  - `{project_info['folder_path']}/problem.md`",
            f"  - `{project_info['folder_path']}/icp.md`",
            f"  - `{project_info['folder_path']}/solution.md`",
            f"  - `{project_info['folder_path']}/validation.md`",
            f"  - `{project_info['folder_path']}/strategy.md`",
            f"  - `{project_info['folder_path']}/financials.md`",
            f"  - `{project_info['folder_path']}/roadmap.md`",
            f"  - `{project_info['folder_path']}/decisions.md`",
            "",
            "## Kickoff Bundle",
            *kickoff_lines,
            "",
            "## Recommended Actions",
            *recommended_action_lines(project_info["key"]),
        ]
    )


def build_founder_session_summary(
    *,
    instance_path: Path,
    state: dict[str, Any],
    schedule: dict[str, Any],
    session: dict[str, Any],
    project: str,
    setup_output_path: str,
    kickoff_handoffs: list[str],
    pending_handoffs: list[dict[str, Any]],
) -> str:
    queued = [item for item in pending_handoffs if item["path"] in set(kickoff_handoffs)]
    queued_lines = [
        f"- `{item['to']}`: `{item['task_type']}` ({item['front_matter'].get('wave', 'unscoped')})"
        for item in queued
    ] or ["- No kickoff handoffs are queued."]
    bundle_lines = [
        f"- `{item['agent_id']}` `{item['task_type']}` [{item['wave']}] -> `{item['status']}`."
        for item in bundle_status_snapshot(
            instance_path=instance_path,
            state=state,
            schedule=schedule,
            pending_handoffs=pending_handoffs,
            project=project,
        )
    ] or ["- No kickoff bundle status is currently available."]
    return "\n".join(
        [
            "[Acting as: MERIDIAN-ORCHESTRATOR]",
            "",
            f"# Founder Session Summary — {project}",
            "",
            f"- Session ID: `{session['session_id']}`",
            f"- Session status: `{session['status']}`",
            f"- Setup artifact: `{setup_output_path}`",
            "",
            "## Kickoff Status",
            *queued_lines,
            "",
            "## Parallel Execution Status",
            *bundle_lines,
            "",
            "## Next Founder Actions",
            *recommended_action_lines(project),
        ]
    )


def create_inline_action_handoffs(
    *,
    instance_path: Path,
    state: dict[str, Any],
    project: str,
    action_key: str,
    source_output: str,
    now: datetime,
) -> list[str]:
    project_state = state.get("projects", {}).get(project, {})
    stage = str(project_state.get("stage", "IDEA") or "IDEA")
    session_id = f"inline-{now.strftime('%Y%m%dT%H%M%S')}"
    allowed_actions = None if action_key == "run_kickoff_bundle" else {action_key}
    created: list[str] = []
    for handoff_path in create_meridian_kickoff_handoffs(
        instance_path=instance_path,
        project=project,
        stage=stage,
        source_output=source_output,
        session_id=session_id,
        now=now,
        allowed_actions=allowed_actions,
    ):
        front_matter, _body = read_front_matter(instance_path / handoff_path)
        if action_key == "run_kickoff_bundle":
            created.append(handoff_path)
        elif front_matter.get("kickoff_action", "") == action_key:
            created.append(handoff_path)
    return created


def build_inline_action_body(project: str, action_key: str, created_handoffs: list[str]) -> str:
    action_label = INLINE_ACTION_SPECS.get(action_key, {}).get("label", action_key)
    handoff_lines = [f"- `{path}`" for path in created_handoffs] or ["- No new handoffs were created because the matching work is already queued or completed."]
    return "\n".join(
        [
            "[Acting as: MERIDIAN-ORCHESTRATOR]",
            "",
            f"# Action Accepted — {project}",
            "",
            f"- Requested action: `{action_label}`",
            "",
            "## Result",
            *handoff_lines,
            "",
            "## Next Actions",
            "- Run `make drain` or `run-cycle` to execute newly queued work.",
            f"- Ask MERIDIAN for `run project checkpoint for {project}` once enough outputs land.",
            "- File-backed replies must be signed with `runner/orchestrate.py sign-founder-reply` before ingestion.",
        ]
    )


def attach_reply_challenge(
    *,
    instance_path: Path,
    state: dict[str, Any],
    front_matter: dict[str, str],
    project: str,
    thread_key: str,
    session_id: str,
    now: datetime,
) -> dict[str, str]:
    challenge = issue_founder_reply_challenge(
        instance_path=instance_path,
        state=state,
        project=project,
        thread_key=thread_key,
        session_id=session_id,
        now=now,
    )
    front_matter = dict(front_matter)
    front_matter["thread_key"] = challenge["thread_key"]
    front_matter["session_id"] = challenge["session_id"]
    front_matter["reply_token"] = challenge["reply_token"]
    front_matter["reply_signature_required"] = challenge["reply_signature_required"]
    front_matter["reply_secret_env_var"] = challenge["reply_secret_env_var"]
    write_json(instance_path / "outputs/state.json", state)
    return front_matter


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
    founder_reply_paths = [instance_path / path for path in request.changed_context if path and (instance_path / path).exists()]
    session = active_intake_session(state)
    kickoff_handoffs: list[str] = []

    if request.origin == "founder_reply" and founder_reply_paths:
        reply_path = founder_reply_paths[0]
        front_matter, reply_body = read_front_matter(reply_path)
        action_key = parse_founder_action_request(reply_body)
        if action_key and (session is None or session.get("mode") == "project_choice"):
            project = request.project
            if project in {PORTFOLIO_PROJECT, STARTUP_WIDE_PROJECT, ""}:
                project = last_open_project(state) or project
            created_action_handoffs = create_inline_action_handoffs(
                instance_path=instance_path,
                state=state,
                project=project,
                action_key=action_key,
                source_output=reply_path.relative_to(instance_path).as_posix(),
                now=now,
            )
            filename = f"{now.date().isoformat()}-{project_slug(project, state)}-action-accepted.md"
            output_path = project_output_dir(instance_path, project, "MERIDIAN-ORCHESTRATOR", state) / filename
            front_matter = {
                "artifact_type": "founder_action_acceptance",
                "audience": "founder",
                "project": project,
                "task_type": "founder_action_acceptance",
                "origin": request.origin,
                "source_run_id": result.run_id,
                "status": "completed",
                "google_drive_id": "",
                "google_doc_id": "",
                "communication_thread_id": f"meridian-action-{now.strftime('%Y%m%d')}",
            }
            front_matter = attach_reply_challenge(
                instance_path=instance_path,
                state=state,
                front_matter=front_matter,
                project=project,
                thread_key=front_matter["communication_thread_id"],
                session_id=f"action-{now.strftime('%Y%m%d%H%M%S')}",
                now=now,
            )
            body = build_inline_action_body(project, action_key, created_action_handoffs)
            write_markdown_with_front_matter(output_path, front_matter, body)
            output_paths.append(output_path.relative_to(instance_path).as_posix())
            result.status = "success"
            notes.append(f"founder_action_{action_key}")
        elif session is None:
            session = start_intake_session(state, now, mode="project_choice")
        if output_paths:
            pass
        elif session.get("mode") == "project_choice":
            choice = parse_project_choice_reply(reply_body, session, state)
            session.setdefault("answers", {})["project_choice"] = choice
            session["updated_at"] = now.isoformat(timespec="seconds")
            if choice == "start_new":
                session["mode"] = "project_setup"
                session["answers"] = {}
                session["question_order"] = [field for _question, field in INTAKE_QUESTION_SPECS]
                session["last_question"] = INTAKE_QUESTION_SPECS[0][1]
                session["asked_questions"] = [INTAKE_QUESTION_SPECS[0][1]]
                write_json(instance_path / "outputs/state.json", state)
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
                    "communication_thread_id": f"meridian-intake-{session['session_id']}",
                }
                front_matter = attach_reply_challenge(
                    instance_path=instance_path,
                    state=state,
                    front_matter=front_matter,
                    project=PORTFOLIO_PROJECT,
                    thread_key=front_matter["communication_thread_id"],
                    session_id=session["session_id"],
                    now=now,
                )
                body = build_meridian_project_intake(state, instance_path, session)
                write_markdown_with_front_matter(output_path, front_matter, body)
                output_paths.append(output_path.relative_to(instance_path).as_posix())
                result.status = "waiting_on_founder"
                notes.append("founder_selected_new_project")
            else:
                session["status"] = "completed"
                session["completed_at"] = now.isoformat(timespec="seconds")
                state["founder_intake"]["active_session_id"] = ""
                request.project = str(session.get("project", "")).strip() or last_open_project(state) or PORTFOLIO_PROJECT
                write_json(instance_path / "outputs/state.json", state)
                filename = f"{now.date().isoformat()}-{project_slug(request.project, state)}-manual-standup.md"
                output_path = project_output_dir(instance_path, request.project, "MERIDIAN-ORCHESTRATOR", load_state(instance_path)) / filename
                front_matter = {
                    "artifact_type": "founder_briefing",
                    "audience": "founder",
                    "project": request.project,
                    "task_type": "project_status_report",
                    "origin": request.origin,
                    "source_run_id": result.run_id,
                    "status": "completed",
                    "google_drive_id": "",
                    "google_doc_id": "",
                    "communication_thread_id": f"meridian-standup-{now.strftime('%Y%m%d')}",
                }
                front_matter = attach_reply_challenge(
                    instance_path=instance_path,
                    state=state,
                    front_matter=front_matter,
                    project=request.project,
                    thread_key=front_matter["communication_thread_id"],
                    session_id=f"standup-{now.strftime('%Y%m%d%H%M%S')}",
                    now=now,
                )
                standup = build_project_standup(state, instance_path, request.project)
                bundle_lines = [
                    f"- `{item['agent_id']}` `{item['task_type']}` [{item['wave']}] -> `{item['status']}`."
                    for item in bundle_status_snapshot(
                        instance_path=instance_path,
                        state=state,
                        schedule=schedule,
                        pending_handoffs=discover_pending_handoffs(instance_path),
                        project=request.project,
                    )
                ] or ["- No kickoff bundle is currently queued for this project."]
                body = "\n".join(
                    [
                        "[Acting as: MERIDIAN-ORCHESTRATOR]",
                        "",
                        f"# Project Standup — {request.project}",
                        "",
                        "## Summary",
                        *standup["summary"],
                        "",
                        "## Wins",
                        *standup["wins"],
                        "",
                        "## Current Challenges",
                        *standup["challenges"],
                        "",
                        "## Blockers",
                        *standup["blockers"],
                        "",
                        "## Next Steps",
                        *standup["next_steps"],
                        "",
                        "## Parallel Execution Status",
                        *bundle_lines,
                        "",
                        "## Recommended Actions",
                        *recommended_action_lines(request.project),
                    ]
                )
                write_markdown_with_front_matter(output_path, front_matter, body)
                output_paths.append(output_path.relative_to(instance_path).as_posix())
                result.status = "success"
                notes.append("founder_selected_continue_last_project")
        else:
            answers = founder_reply_intake_answers(reply_body)
            if not answers and reply_body.strip():
                last_question = str(session.get("last_question", "")).strip()
                if last_question:
                    answers[last_question] = reply_body.strip()
            merge_intake_answers(session, answers, now)
            write_json(instance_path / "outputs/state.json", state)
            next_question = next_intake_question(session)
            if next_question is None and session.get("answers", {}).get("project_name", "").strip():
                session["project"] = session["answers"].get("project_key", session["answers"].get("project_name", project_slug("project"))).strip()
                session["status"] = "completed"
                session["completed_at"] = now.isoformat(timespec="seconds")
                state["founder_intake"]["active_session_id"] = ""
                write_json(instance_path / "outputs/state.json", state)
                project_info = upsert_project_from_intake(instance_path, session.get("answers", {}))
                request.project = project_info["key"]
                filename = f"{now.date().isoformat()}-{project_info['slug']}-project-setup.md"
                output_path = project_output_dir(instance_path, project_info["key"], "MERIDIAN-ORCHESTRATOR", load_state(instance_path)) / filename
                kickoff_handoffs = create_meridian_kickoff_handoffs(
                    instance_path=instance_path,
                    project=project_info["key"],
                    stage=session["answers"].get("stage", "IDEA"),
                    source_output=output_path.relative_to(instance_path).as_posix(),
                    session_id=session["session_id"],
                    now=now,
                )
                front_matter = {
                    "artifact_type": "project_setup",
                    "audience": "founder",
                    "project": project_info["key"],
                    "task_type": PROJECT_SETUP_TASK_TYPE,
                    "origin": request.origin,
                    "source_run_id": result.run_id,
                    "status": "completed",
                    "google_drive_id": "",
                    "google_doc_id": "",
                    "communication_thread_id": f"meridian-project-setup-{now.strftime('%Y%m%d')}",
                }
                front_matter = attach_reply_challenge(
                    instance_path=instance_path,
                    state=state,
                    front_matter=front_matter,
                    project=project_info["key"],
                    thread_key=front_matter["communication_thread_id"],
                    session_id=f"setup-{session['session_id']}",
                    now=now,
                )
                body = build_project_setup_body(project_info, kickoff_handoffs)
                write_markdown_with_front_matter(output_path, front_matter, body)
                output_paths.append(output_path.relative_to(instance_path).as_posix())
                summary_path = project_output_dir(instance_path, project_info["key"], "MERIDIAN-ORCHESTRATOR", load_state(instance_path)) / f"{now.date().isoformat()}-{project_info['slug']}-founder-session-summary.md"
                summary_front_matter = {
                    "artifact_type": "founder_session_summary",
                    "audience": "founder",
                    "project": project_info["key"],
                    "task_type": "founder_session_summary",
                    "origin": request.origin,
                    "source_run_id": result.run_id,
                    "status": "completed",
                    "google_drive_id": "",
                    "google_doc_id": "",
                    "communication_thread_id": f"meridian-session-{now.strftime('%Y%m%d')}",
                }
                summary_front_matter = attach_reply_challenge(
                    instance_path=instance_path,
                    state=state,
                    front_matter=summary_front_matter,
                    project=project_info["key"],
                    thread_key=summary_front_matter["communication_thread_id"],
                    session_id=f"session-{session['session_id']}",
                    now=now,
                )
                pending_after_kickoff = discover_pending_handoffs(instance_path)
                summary_body = build_founder_session_summary(
                    instance_path=instance_path,
                    state=load_state(instance_path),
                    schedule=schedule,
                    session=session,
                    project=project_info["key"],
                    setup_output_path=output_paths[0],
                    kickoff_handoffs=kickoff_handoffs,
                    pending_handoffs=pending_after_kickoff,
                )
                write_markdown_with_front_matter(summary_path, summary_front_matter, summary_body)
                output_paths.append(summary_path.relative_to(instance_path).as_posix())
                result.status = "success"
                notes.extend(["founder_project_files_populated", "project_kickoff_bundle_created"])
            else:
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
                    "communication_thread_id": f"meridian-intake-{session['session_id']}",
                }
                front_matter = attach_reply_challenge(
                    instance_path=instance_path,
                    state=state,
                    front_matter=front_matter,
                    project=PORTFOLIO_PROJECT,
                    thread_key=front_matter["communication_thread_id"],
                    session_id=session["session_id"],
                    now=now,
                )
                body = build_meridian_project_intake(state, instance_path, session)
                write_markdown_with_front_matter(output_path, front_matter, body)
                output_paths.append(output_path.relative_to(instance_path).as_posix())
                result.status = "waiting_on_founder"
                notes.append("founder_reply_session_progressed")

    if output_paths:
        pass
    elif needs_project_selection:
        if session is None or session.get("mode") != "project_choice":
            session = start_intake_session(state, now, mode="project_choice")
            write_json(instance_path / "outputs/state.json", state)
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
            "communication_thread_id": f"meridian-intake-{session['session_id']}",
        }
        front_matter = attach_reply_challenge(
            instance_path=instance_path,
            state=state,
            front_matter=front_matter,
            project=PORTFOLIO_PROJECT,
            thread_key=front_matter["communication_thread_id"],
            session_id=session["session_id"],
            now=now,
        )
        body = build_meridian_project_intake(state, instance_path, session)
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
        front_matter = attach_reply_challenge(
            instance_path=instance_path,
            state=state,
            front_matter=front_matter,
            project=request.project,
            thread_key=front_matter["communication_thread_id"],
            session_id=f"briefing-{now.strftime('%Y%m%d%H%M%S')}",
            now=now,
        )
        body = build_meridian_briefing(
            instance_path=instance_path,
            state=state,
            schedule=schedule,
            project=request.project,
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

    archived_source_path = ""
    if request.origin == "founder_reply":
        for relative_path in request.changed_context:
            if relative_path.startswith("inputs/founder-replies/"):
                archived_source_path = archive_reply_file(instance_path, relative_path)
                break
        if archived_source_path:
            payload = load_json(result_path)
            payload["archived_source_path"] = archived_source_path
            write_json(result_path, payload)

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


def run_cycle(instance_path: Path, limit: int | None = None) -> dict[str, Any]:
    schedule = load_schedule(instance_path)
    execution_mode = dispatcher_execution_mode(schedule)
    if execution_mode != "hybrid":
        planned = plan_requests(instance_path)
        drained = drain_queue(instance_path, limit=limit)
        return {
            "status": drained.get("status", "drained"),
            "planned": planned,
            "drained": drained,
        }

    rounds: list[dict[str, Any]] = []
    overall_status = "drained"
    max_rounds = max_event_loop_iterations(schedule)
    for round_index in range(1, max_rounds + 1):
        planned = plan_requests(instance_path)
        queued_count = int(planned.get("queued_count", 0))
        existing_queue = sorted((instance_path / "runtime/queue").glob("*.json"))
        if queued_count == 0 and not existing_queue:
            if not rounds:
                drained = {
                    "status": "drained",
                    "processed_count": 0,
                    "failure_count": 0,
                    "results": [],
                }
                return {"status": "drained", "rounds": [{"round": round_index, "planned": planned, "drained": drained}]}
            break
        drained = drain_queue(instance_path, limit=limit)
        round_status = drained.get("status", "drained")
        if round_status == "drained_with_failures":
            overall_status = round_status
        rounds.append({"round": round_index, "planned": planned, "drained": drained})
        if sorted((instance_path / "runtime/queue").glob("*.json")):
            continue
        follow_up = plan_requests(instance_path)
        if int(follow_up.get("queued_count", 0)) == 0:
            break
        rounds.append({"round": round_index, "planned_follow_up": follow_up})

    aggregate_processed = sum(item.get("drained", {}).get("processed_count", 0) for item in rounds)
    aggregate_failures = sum(item.get("drained", {}).get("failure_count", 0) for item in rounds)
    return {
        "status": overall_status,
        "rounds": rounds,
        "processed_count": aggregate_processed,
        "failure_count": aggregate_failures,
    }


def manual_meridian(instance_path: Path) -> dict[str, Any]:
    request = build_request(
        agent_id="MERIDIAN-ORCHESTRATOR",
        trigger_type="manual",
        reason="manual_founder_session",
        run_timestamp=current_time(load_schedule(instance_path)).isoformat(timespec="seconds"),
        changed_context=[],
        instance_path=instance_path,
        project=PORTFOLIO_PROJECT,
        task_type="project_selection",
        origin="manual",
    )
    queued = queue_request(instance_path, request)
    drained = drain_queue(instance_path)
    return {"status": drained.get("status", "drained"), "queued": queued, "drained": drained}


def ingest_replies(instance_path: Path) -> dict[str, Any]:
    ensure_runtime_dirs(instance_path)
    channel = get_default_channel(instance_path)
    replies = channel.ingest_responses()
    queued: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    state = load_state(instance_path)
    now_dt = current_time(load_schedule(instance_path))
    prune_founder_reply_auth(state, now_dt)
    now = now_dt.isoformat(timespec="seconds")
    for reply in replies:
        reply_path = instance_path / reply["source_path"]
        front_matter, body = read_front_matter(reply_path)
        accepted, reason, validated = validate_founder_reply(
            instance_path=instance_path,
            state=state,
            reply_path=reply_path,
            front_matter=front_matter,
            body=body,
        )
        if not accepted:
            rejected_path = reject_reply_file(instance_path, reply["source_path"], reason)
            founder_reply_auth_store(state).setdefault("rejected_replies", []).append(
                {
                    "reply_id": front_matter.get("reply_id", reply_path.stem),
                    "reason": reason,
                    "path": rejected_path,
                    "rejected_at": now,
                }
            )
            rejected.append({"reply_id": front_matter.get("reply_id", reply_path.stem), "reason": reason, "path": rejected_path})
            continue
        founder_reply_auth_store(state).setdefault("used_reply_ids", []).append(validated["reply_id"])
        active_thread = founder_reply_auth_store(state).setdefault("active_threads", {}).get(validated["thread_key"], {})
        if active_thread:
            active_thread["status"] = "replied"
            active_thread["last_reply_id"] = validated["reply_id"]
            active_thread["replied_at"] = now
        request = build_request(
            agent_id="MERIDIAN-ORCHESTRATOR",
            trigger_type="event",
            reason=f"founder_reply:{validated['reply_id']}",
            run_timestamp=now,
            changed_context=[reply["source_path"]],
            instance_path=instance_path,
            project=validated.get("project", STARTUP_WIDE_PROJECT),
            task_type="founder_reply",
            origin="founder_reply",
        )
        queued.append(queue_request(instance_path, request))
    write_json(instance_path / "outputs/state.json", state)
    return {
        "status": "ingested",
        "reply_count": len(replies),
        "queued_requests": queued,
        "rejected_replies": rejected,
    }


def ingest_and_drain_replies(instance_path: Path) -> dict[str, Any]:
    ingested = ingest_replies(instance_path)
    drained = run_cycle(instance_path)
    return {"status": drained.get("status", "drained"), "ingested": ingested, "drained": drained}


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

    run_cycle_parser = subparsers.add_parser("run-cycle", help="Atomically plan and drain the runtime queue")
    run_cycle_parser.add_argument("--instance-path", default=".")
    run_cycle_parser.add_argument("--limit", type=int, default=None)

    manual_meridian_parser = subparsers.add_parser("manual-meridian", help="Queue and immediately run a manual Meridian founder session")
    manual_meridian_parser.add_argument("--instance-path", default=".")

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

    ingest_and_drain_parser = subparsers.add_parser("ingest-and-drain-replies", help="Ingest founder replies and immediately drain the queue")
    ingest_and_drain_parser.add_argument("--instance-path", default=".")

    sign_reply_parser = subparsers.add_parser("sign-founder-reply", help="Sign a founder reply file for authenticated ingestion")
    sign_reply_parser.add_argument("--instance-path", default=".")
    sign_reply_parser.add_argument("--reply-file", required=True)

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
    elif args.command == "run-cycle":
        payload = run_cycle(instance_path, limit=args.limit)
    elif args.command == "manual-meridian":
        payload = manual_meridian(instance_path)
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
    elif args.command == "ingest-and-drain-replies":
        payload = ingest_and_drain_replies(instance_path)
    elif args.command == "sign-founder-reply":
        reply_path = Path(args.reply_file)
        if not reply_path.is_absolute():
            reply_path = instance_path / reply_path
        payload = sign_founder_reply_file(instance_path, reply_path)
    elif args.command == "reconcile-state":
        payload = reconcile_state(instance_path)
    else:  # pragma: no cover
        parser.error(f"Unknown command: {args.command}")
        return 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload.get("status") in {"failed", "drained_with_failures"} else 0


if __name__ == "__main__":
    sys.exit(main())
