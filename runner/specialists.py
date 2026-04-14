from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ENABLED_SPECIALISTS = {
    "ATLAS-RESEARCH",
    "FORGE-ENGINEERING",
    "CURRENT-SALES",
    "HERALD-COMMS",
}


@dataclass
class SpecialistExecutionResult:
    status: str
    output_paths: list[str]
    processed_handoff_paths: list[str]
    created_handoff_paths: list[str]
    notes: list[str]


def load_json(path: Path) -> dict[str, Any]:
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


def write_front_matter(path: Path, front_matter: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in front_matter.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    path.write_text("\n".join(lines) + "\n" + body.lstrip("\n"), encoding="utf-8")


def slugify(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")


def extract_handoff_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for line in body.splitlines():
        if line.startswith("## ") and ":" in line:
            label, value = line[3:].split(":", 1)
            sections[label.strip().lower()] = value.strip()
    return sections


def relevant_context_paths(
    instance_path: Path,
    schedule_entry: dict[str, Any],
    handoffs: list[dict[str, Any]],
    agent_id: str,
) -> list[str]:
    paths = set(schedule_entry.get("context_inputs", []))
    paths.update(handoff["path"] for handoff in handoffs)
    existing: list[str] = []
    for relative_path in sorted(paths):
        full_path = instance_path / relative_path
        if full_path.exists():
            existing.append(relative_path)
    return existing


def collect_recent_project_outputs(instance_path: Path, project: str, exclude_agent: str) -> list[dict[str, str]]:
    outputs_root = instance_path / "outputs"
    collected: list[dict[str, str]] = []
    for agent_dir in sorted(path for path in outputs_root.iterdir() if path.is_dir()):
        if agent_dir.name in {"handoffs", "escalations", "communications"} or agent_dir.name == exclude_agent:
            continue
        files = sorted(agent_dir.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not files:
            continue
        latest_path = files[0]
        front_matter, body = read_front_matter(latest_path)
        if front_matter.get("project", project) != project:
            continue
        collected.append(
            {
                "agent": agent_dir.name,
                "path": latest_path.relative_to(instance_path).as_posix(),
                "summary": next((line.strip("- ").strip() for line in body.splitlines() if line.startswith("- ")), body.splitlines()[0] if body.splitlines() else ""),
            }
        )
    return collected


def artifact_type_for_agent(agent_id: str) -> str:
    return {
        "ATLAS-RESEARCH": "research_brief",
        "FORGE-ENGINEERING": "engineering_memo",
        "CURRENT-SALES": "sales_brief",
        "HERALD-COMMS": "communications_brief",
    }[agent_id]


def body_sections_for_agent(
    agent_id: str,
    project: str,
    handoff: dict[str, Any],
    action_required: str,
    recent_outputs: list[dict[str, str]],
) -> list[str]:
    body = handoff["body"]
    if agent_id == "ATLAS-RESEARCH":
        findings = [
            f"The most plausible initial ICP for `{project}` is innovation-forward teams willing to test psychographic matching as a hiring wedge.",
            "The highest-risk assumptions are employer willingness to pay before proof of match quality and whether hiring managers value culture-vector data in early screening.",
        ]
        if recent_outputs:
            findings.append(f"Recent cross-functional context: `{recent_outputs[0]['agent']}` last wrote `{recent_outputs[0]['path']}`.")
        implications = [
            "Sales outreach should anchor on lower-risk pilot asks and learning-oriented LOIs.",
            "Engineering should prioritize evidence-generating features before breadth expansion.",
        ]
        return [
            "## Scope",
            action_required or "Clarify the initial ICP and open assumptions for the assigned project.",
            "",
            "## Findings",
            *[f"- {item}" for item in findings],
            "",
            "## Assumptions And Evidence",
            "- Evidence is derived from the company brief, the requesting handoff, and current repo state rather than external browsing.",
            "- Assumption quality remains constrained until customer interviews or outbound feedback are captured in-repo.",
            "",
            "## Implications",
            *[f"- {item}" for item in implications],
            "",
            "## Recommended Next Actions",
            "- Use this ICP framing to tighten target-account selection and outreach messaging.",
            "- Capture interview and outreach feedback in future specialist outputs so MERIDIAN can update shared state with stronger evidence.",
            "",
            "## Handoffs Triggered",
        ]
    if agent_id == "FORGE-ENGINEERING":
        plan = [
            "Sequence work as psychographic profile storage -> LLM-powered CV analysis -> company intelligence synthesis -> additional scraper coverage.",
            "Expose each milestone behind stable repo-facing contracts so later app surfaces can reuse the same backend model.",
            "Treat company-vector storage and evaluation instrumentation as the riskiest dependency because both product proof and research depend on them.",
        ]
        return [
            "## Scope",
            action_required or "Produce an engineering plan for the assigned project handoff.",
            "",
            "## Technical Plan",
            *[f"- {item}" for item in plan],
            "",
            "## Dependencies",
            "- Product scoping help is needed once engineering reaches prioritization tradeoffs between profile storage, inference quality, and UI surface area.",
            "- Research outputs should keep refining the first customer wedge so implementation sequencing stays tied to buyer evidence.",
            "",
            "## Risks",
            "- Overbuilding scraper breadth before the psychographic core is proven would dilute engineering effort.",
            "- Missing instrumentation would make later validation and fundraising claims weak.",
            "",
            "## Handoffs Triggered",
        ]
    if agent_id == "CURRENT-SALES":
        pipeline = [
            "Prioritize 10 early targets among mission-driven startups, hiring leaders at fast-moving small teams, and design-partner friendly recruiting operators.",
            "Lead with a low-friction commercial ask: pilot, LOI, or structured discovery conversation tied to hiring fit quality.",
            "Track objections around data quality, implementation friction, and willingness to change current screening habits.",
        ]
        return [
            "## Scope",
            action_required or "Build the project pipeline plan and outreach motion.",
            "",
            "## Pipeline Or Outreach Status",
            *[f"- {item}" for item in pipeline],
            "",
            "## Recommended Actions",
            "- Start with founder-led outreach and capture reply patterns in repo-native outputs.",
            "- Use ATLAS research to sharpen which buyer roles convert fastest and what language lands.",
            "",
            "## Risks And Blockers",
            "- ICP ambiguity will lower response quality if targeting is too broad.",
            "- Without proof points, pricing and urgency language should stay exploratory rather than assertive.",
            "",
            "## Handoffs Triggered",
        ]
    draft = [
        "The core story arc is: broken hiring signal -> psychographic matching wedge -> better candidate-company alignment -> stronger early proof once pilots land.",
        "Current proof gaps are customer evidence, measurable match outcomes, and a disciplined roadmap narrative.",
        "The minimum next materials are a pitch outline, evidence tracker, and a clean explanation of why SIGNAL wins before full workflow replacement.",
    ]
    return [
        "## Scope",
        action_required or "Draft the narrative and communications response for the assigned project handoff.",
        "",
        "## Draft Or Narrative",
        *[f"- {item}" for item in draft],
        "",
        "## Dependencies",
        "- Finance and fundraising support will matter once investor targeting and data room preparation start.",
        "- Sales and research outputs should supply the proof points that strengthen the story arc.",
        "",
        "## Recommended Next Actions",
        "- Turn this outline into founder-facing fundraising materials once supporting evidence is captured.",
        "- Keep proof gaps explicit so MERIDIAN can escalate only the decisions that truly need founder input.",
        "",
        "## Handoffs Triggered",
    ]


def downstream_handoffs_for_agent(
    *,
    instance_path: Path,
    agent_id: str,
    project: str,
    handoff: dict[str, Any],
    output_relative_path: str,
    run_id: str,
    now: datetime,
) -> list[dict[str, str]]:
    action_required = handoff["action_required"].lower()
    created: list[dict[str, str]] = []
    if agent_id == "FORGE-ENGINEERING" and "canvas-product" in action_required:
        created.append(
            {
                "to": "CANVAS-PRODUCT",
                "task_type": "product_dependency_review",
                "reason": "Engineering identified product prioritization questions that require CANVAS-PRODUCT input.",
                "subject": "Product Scope Dependency Review",
                "action_required": "Review the engineering plan tradeoffs and recommend which scope decisions should be locked before build execution continues.",
            }
        )
    if agent_id == "CURRENT-SALES" and "atlas-research" in action_required:
        created.append(
            {
                "to": "ATLAS-RESEARCH",
                "task_type": "targeting_refinement",
                "reason": "Sales outreach planning needs tighter ICP evidence before founder-led outbound begins.",
                "subject": "ICP Targeting Refinement",
                "action_required": "Tighten the first-buyer hypothesis and note the strongest signals to improve target-account selection and outreach language.",
            }
        )
    if agent_id == "HERALD-COMMS" and "ledger-finance" in action_required:
        created.append(
            {
                "to": "LEDGER-FINANCE",
                "task_type": "fundraise_preparation",
                "reason": "Communications work identified a dependency on investor-list or data-room planning.",
                "subject": "Fundraise Preparation Dependency",
                "action_required": "Prepare the minimum investor-pipeline and data-room planning inputs needed to support the narrative work.",
            }
        )
    if agent_id == "ATLAS-RESEARCH" and ("go-to-market wedge" in handoff["body"].lower() or "sales work" in handoff["body"].lower()):
        created.append(
            {
                "to": "CURRENT-SALES",
                "task_type": "icp_outreach_alignment",
                "reason": "Research findings materially affect the first go-to-market wedge and outreach targeting.",
                "subject": "ICP Outreach Alignment",
                "action_required": "Use the updated ICP framing to refine the first outbound list and commercial ask.",
            }
        )

    created_paths: list[dict[str, str]] = []
    handoff_dir = instance_path / "outputs/handoffs"
    existing_count = len(list(handoff_dir.glob(f"HANDOFF-{now.date().isoformat()}-{agent_id}-*.md")))
    for index, item in enumerate(created, start=1):
        handoff_id = f"HANDOFF-{now.date().isoformat()}-{agent_id}-{existing_count + index:03d}"
        handoff_path = handoff_dir / f"{handoff_id}.md"
        front_matter = {
            "handoff_id": handoff_id,
            "from": agent_id,
            "to": item["to"],
            "project": project,
            "task_type": item["task_type"],
            "origin": "handoff",
            "status": "queued",
            "created_at": now.isoformat(timespec="seconds"),
            "reason": item["reason"],
            "source_output": output_relative_path,
            "compatibility": "canonical",
        }
        body = "\n".join(
            [
                f"## FROM: {agent_id}",
                f"## TO: {item['to']}",
                f"## PROJECT: {project}",
                f"## TASK TYPE: {item['task_type']}",
                "## ORIGIN: handoff",
                f"## RE: {item['subject']}",
                f"## CONTEXT: Triggered from `{handoff['handoff_id']}` during `{run_id}`.",
                f"## OUTPUT: See `{output_relative_path}` for the specialist output that justified this follow-on work.",
                f"## ACTION REQUIRED: {item['action_required']}",
            ]
        )
        write_front_matter(handoff_path, front_matter, body)
        created_paths.append({"path": handoff_path.relative_to(instance_path).as_posix()})
    return created_paths


def mark_source_handoffs_completed(instance_path: Path, handoff_paths: list[str], run_id: str, finished_at: str) -> int:
    completed = 0
    for relative_path in sorted(set(handoff_paths)):
        path = instance_path / relative_path
        if not path.exists():
            continue
        front_matter, body = read_front_matter(path)
        if front_matter.get("status") != "queued":
            continue
        front_matter["status"] = "completed"
        front_matter["completed_at"] = finished_at
        front_matter["runtime_result"] = f"runtime/results/{run_id}.json"
        write_front_matter(path, front_matter, body)
        completed += 1
    return completed


def execute_specialist(
    *,
    instance_path: Path,
    agent_id: str,
    schedule_entry: dict[str, Any],
    request: Any,
    run_id: str,
) -> SpecialistExecutionResult:
    if agent_id not in ENABLED_SPECIALISTS:
        return SpecialistExecutionResult(
            status="success",
            output_paths=[],
            processed_handoff_paths=[],
            created_handoff_paths=[],
            notes=["no_specialist_executor_registered"],
        )

    handoff_dir = instance_path / "outputs/handoffs"
    candidate_handoffs: list[dict[str, Any]] = []
    requested_paths = set(request.changed_context or [])
    for handoff_path in sorted(handoff_dir.glob("*.md")):
        relative_path = handoff_path.relative_to(instance_path).as_posix()
        if requested_paths and relative_path not in requested_paths:
            continue
        front_matter, body = read_front_matter(handoff_path)
        if front_matter.get("status") != "queued":
            continue
        if front_matter.get("to") != agent_id:
            continue
        sections = extract_handoff_sections(body)
        candidate_handoffs.append(
            {
                "path": relative_path,
                "handoff_id": front_matter.get("handoff_id", handoff_path.stem),
                "project": front_matter.get("project", request.project),
                "task_type": front_matter.get("task_type", request.task_type),
                "origin": front_matter.get("origin", request.origin),
                "reason": front_matter.get("reason", request.reason),
                "body": body,
                "action_required": sections.get("action required", ""),
            }
        )

    if not candidate_handoffs:
        return SpecialistExecutionResult(
            status="skipped",
            output_paths=[],
            processed_handoff_paths=[],
            created_handoff_paths=[],
            notes=["no_pending_handoffs_for_specialist"],
        )

    now = datetime.now(timezone.utc)
    output_paths: list[str] = []
    processed_paths: list[str] = []
    created_handoff_paths: list[str] = []
    notes: list[str] = []

    for handoff in candidate_handoffs:
        project = handoff["project"]
        context_paths = relevant_context_paths(instance_path, schedule_entry, [handoff], agent_id)
        recent_outputs = collect_recent_project_outputs(instance_path, project, agent_id)
        sections = body_sections_for_agent(agent_id, project, handoff, handoff["action_required"], recent_outputs)
        downstream = downstream_handoffs_for_agent(
            instance_path=instance_path,
            agent_id=agent_id,
            project=project,
            handoff=handoff,
            output_relative_path="",
            run_id=run_id,
            now=now,
        )

        slug = f"{slugify(project)}-{slugify(handoff['task_type'])}-{slugify(handoff['handoff_id'])[-12:]}"
        output_path = instance_path / "outputs" / agent_id / f"{now.date().isoformat()}-{slug}.md"
        front_matter = {
            "artifact_type": artifact_type_for_agent(agent_id),
            "audience": "internal",
            "project": project,
            "task_type": handoff["task_type"],
            "origin": handoff["origin"],
            "source_run_id": run_id,
            "status": "completed",
        }
        if agent_id == "HERALD-COMMS":
            front_matter["audience"] = "founder"

        handoff_lines = [f"- `{Path(item['path']).stem}` -> downstream handoff created." for item in downstream]
        if not handoff_lines:
            handoff_lines = ["- No downstream handoffs were justified in this pass."]

        context_lines = [f"- `{path}`" for path in context_paths] or ["- No additional context files were available beyond the source handoff."]
        recent_output_lines = [f"- `{item['agent']}`: `{item['path']}`" for item in recent_outputs] or ["- No recent same-project specialist outputs were available."]

        body = "\n".join(
            sections
            + [
                "",
                "## Context Inputs Reviewed",
                *context_lines,
                "",
                "## Recent Project Outputs Reviewed",
                *recent_output_lines,
                "",
                *handoff_lines,
            ]
        )
        write_front_matter(output_path, front_matter, body)
        output_relative_path = output_path.relative_to(instance_path).as_posix()
        output_paths.append(output_relative_path)

        if downstream:
            for created in downstream:
                handoff_path = instance_path / created["path"]
                created_front_matter, created_body = read_front_matter(handoff_path)
                created_front_matter["source_output"] = output_relative_path
                write_front_matter(handoff_path, created_front_matter, created_body)
                created_handoff_paths.append(created["path"])

        processed_paths.append(handoff["path"])
        notes.append(f"processed_{handoff['handoff_id']}")

    mark_source_handoffs_completed(instance_path, processed_paths, run_id, now.isoformat(timespec="seconds"))
    if created_handoff_paths:
        notes.append(f"created_{len(created_handoff_paths)}_downstream_handoff(s)")
    return SpecialistExecutionResult(
        status="success",
        output_paths=output_paths,
        processed_handoff_paths=processed_paths,
        created_handoff_paths=created_handoff_paths,
        notes=notes,
    )
