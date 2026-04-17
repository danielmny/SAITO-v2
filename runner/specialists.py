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
    "CANVAS-PRODUCT",
    "COUNSEL-LEGAL",
    "FORGE-ENGINEERING",
    "CURRENT-SALES",
    "MARKETING-BRAND",
    "NEXUS-TALENT",
    "LEDGER-FINANCE",
    "VECTOR-ANALYTICS",
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
        "CANVAS-PRODUCT": "product_memo",
        "COUNSEL-LEGAL": "legal_brief",
        "FORGE-ENGINEERING": "engineering_memo",
        "CURRENT-SALES": "sales_brief",
        "MARKETING-BRAND": "marketing_brief",
        "NEXUS-TALENT": "talent_brief",
        "LEDGER-FINANCE": "finance_memo",
        "VECTOR-ANALYTICS": "analytics_brief",
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
    if agent_id == "CANVAS-PRODUCT":
        roadmap = [
            "Lock the v1 scope around psychographic profile storage, company vector capture, match explanation, and evidence instrumentation before expansion work.",
            "Defer non-core growth surfaces until the core matching loop has user feedback and measurable proof.",
            "Translate engineering tradeoffs into a Now / Next / Later roadmap so execution stays tied to validation milestones.",
        ]
        return [
            "## Scope",
            action_required or "Review the product dependency and define the minimum product scope decisions needed next.",
            "",
            "## Product Decisions",
            *[f"- {item}" for item in roadmap],
            "",
            "## Backlog Priorities",
            "- Now: profile persistence, company-side vector inputs, and match-quality evidence capture.",
            "- Next: synthesis and recruiter-facing explanation surfaces that improve trust in the match output.",
            "- Later: broader workflow integrations once the initial wedge is commercially validated.",
            "",
            "## Risks",
            "- If scope stays fuzzy, engineering effort will spread across validation and expansion work at the same time.",
            "- Product claims will weaken if instrumentation is not defined before core feature delivery.",
            "",
            "## Recommended Next Actions",
            "- Freeze the current MVP boundary in repo-native artifacts so engineering and sales work from the same definition.",
            "- Keep proof-generating metrics tied to each roadmap increment so MERIDIAN can summarize progress cleanly.",
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
    if agent_id == "LEDGER-FINANCE":
        readiness = [
            "Start with a lightweight investor pipeline: target list, status tracker, and a short rationale for why each investor fits the SIGNAL story.",
            "Treat the first data room as a minimum viable package: company narrative, roadmap, early proof points, and operating metrics already available in-repo.",
            "Keep fundraising readiness explicitly coupled to evidence quality so narrative work does not outrun actual traction.",
        ]
        return [
            "## Scope",
            action_required or "Prepare the minimum fundraising and finance readiness package for the assigned handoff.",
            "",
            "## Fundraising Readiness",
            *[f"- {item}" for item in readiness],
            "",
            "## Required Artifacts",
            "- Investor target list with stage and thesis fit notes.",
            "- Data room checklist covering deck, product status, GTM proof, and operating metrics.",
            "- Short runway and capital-needs framing once commercial assumptions firm up.",
            "",
            "## Risks",
            "- Investor outreach will underperform if proof points stay qualitative rather than repo-backed and measurable.",
            "- Data-room work can sprawl unless the minimum diligence package is defined up front.",
            "",
            "## Recommended Next Actions",
            "- Convert existing specialist outputs into diligence-ready supporting material rather than recreating context from scratch.",
            "- Keep finance preparation synchronized with HERALD narrative work so claims stay evidence-backed.",
            "",
            "## Handoffs Triggered",
        ]
    if agent_id == "MARKETING-BRAND":
        messaging = [
            "Lead with a wedge message around better candidate-company alignment rather than generic AI recruiting automation.",
            "Keep the first external story anchored on psychographic fit, faster signal quality, and a pilot-friendly deployment path.",
            "Separate current proof from future promise so outreach and fundraising language stay credible at pre-seed stage.",
        ]
        return [
            "## Scope",
            action_required or "Draft the messaging foundation and demand-generation framing for the assigned project handoff.",
            "",
            "## Messaging Or Campaign Plan",
            *[f"- {item}" for item in messaging],
            "",
            "## Success Signals",
            "- Higher response quality in founder-led outbound and design-partner conversations.",
            "- Clearer message consistency across research, sales, and fundraising materials.",
            "- Proof gaps stay explicit instead of being blurred by broad brand claims.",
            "",
            "## Dependencies",
            "- ATLAS research should keep pressure-testing ICP language and buyer objections.",
            "- HERALD should reuse the strongest proof-backed lines for investor-facing narrative work.",
            "",
            "## Handoffs Triggered",
        ]
    if agent_id == "VECTOR-ANALYTICS":
        metrics = [
            "Use a North Star focused on qualified psychographic match outcomes rather than raw traffic or scrape volume.",
            "Instrument the seeker profile completion, company vector completion, match generation, and follow-up conversion path first.",
            "Keep the first dashboard lightweight: activation, match quality signals, pilot pipeline, and founder operating cadence.",
        ]
        return [
            "## Scope",
            action_required or "Define the initial metrics, instrumentation, and dashboard signals for the assigned project handoff.",
            "",
            "## Metrics And Signals",
            *[f"- {item}" for item in metrics],
            "",
            "## Dashboard Implications",
            "- The future founder dashboard should show project health through activation, evidence quality, and commercial traction together.",
            "- Product and sales instrumentation should roll up into one project view rather than separate unconnected metric sets.",
            "",
            "## Data Gaps",
            "- Match quality has to be operationalized before it can function as a defensible north-star metric.",
            "- Event names and ownership should be locked now so engineering instrumentation stays consistent with product and GTM reporting.",
            "",
            "## Handoffs Triggered",
        ]
    if agent_id == "COUNSEL-LEGAL":
        risks = [
            "Candidate and employer data handling should be governed by explicit privacy disclosures, retention limits, and internal access boundaries before broader deployment.",
            "Pre-seed fundraising preparation should include a lightweight diligence checklist so company records, IP ownership, and core policies are not assembled ad hoc under investor pressure.",
            "Terms of service, privacy policy, and contractor or assignment paperwork should be treated as launch-blocking housekeeping rather than deferred cleanup.",
        ]
        return [
            "## Scope",
            action_required or "Outline the immediate legal and compliance priorities for the assigned project handoff.",
            "",
            "## Risk Summary",
            *[f"- {item}" for item in risks],
            "- [REVIEW WITH QUALIFIED COUNSEL BEFORE ACTING]",
            "",
            "## Required Actions",
            "- Create a minimum policy set covering privacy, terms, and internal data handling expectations for SIGNAL.",
            "- Confirm IP assignment and contribution ownership across any contractors, founders, and collaborators touching the code or fundraising materials.",
            "- Prepare a diligence-ready legal checklist covering entity docs, cap table hygiene, material agreements, and customer-data handling assumptions.",
            "",
            "## Open Questions",
            "- What candidate data is retained, for how long, and under what deletion or access process?",
            "- Which jurisdictions are most likely to matter first for privacy and employment-related compliance?",
            "- Are there any unsigned contributor, contractor, or advisor agreements that could create IP ambiguity later?",
            "",
            "## Handoffs Triggered",
        ]
    if agent_id == "NEXUS-TALENT":
        recommendations = [
            "Do not scale headcount ahead of customer proof; the next hires should be framed as capability gaps to watch rather than immediate recruiting actions.",
            "The first likely non-founder additions are a product-minded engineer with strong data-modeling instincts and a GTM operator once outreach converts into repeatable demand.",
            "Any hiring sequence should stay coupled to runway, customer evidence, and whether founders can still absorb execution load without slowing validation.",
        ]
        return [
            "## Scope",
            action_required or "Produce the current talent-readiness view and recommend the next likely roles or waiting posture.",
            "",
            "## Talent Recommendation",
            *[f"- {item}" for item in recommendations],
            "",
            "## Risks Or Dependencies",
            "- Hiring too early would increase burn before the SIGNAL wedge and sales motion are validated.",
            "- Waiting too long to identify capability gaps can leave engineering or GTM load concentrated on founders at the wrong moment.",
            "- Budget and fundraising timing should shape any hiring sequence rather than abstract org-chart ambition.",
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


def downstream_handoff_specs(
    *,
    agent_id: str,
    project: str,
    handoff: dict[str, Any],
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
    if agent_id == "CANVAS-PRODUCT" and ("instrumentation" in action_required or "metrics" in action_required or "analytics" in handoff["body"].lower()):
        created.append(
            {
                "to": "VECTOR-ANALYTICS",
                "task_type": "instrumentation_definition",
                "reason": "Product scoping identified an analytics dependency for proof-generating instrumentation.",
                "subject": "Instrumentation Definition",
                "action_required": "Define the minimum metrics and instrumentation events required to validate the current product roadmap.",
            }
        )
    if agent_id == "LEDGER-FINANCE" and ("data-room" in action_required or "compliance" in action_required or "legal" in handoff["body"].lower()):
        created.append(
            {
                "to": "COUNSEL-LEGAL",
                "task_type": "diligence_readiness",
                "reason": "Finance preparation identified a legal or diligence dependency that should be made explicit.",
                "subject": "Diligence Readiness",
                "action_required": "Outline the minimum legal and diligence artifacts needed before formal fundraising outreach accelerates.",
            }
        )
    if agent_id == "MARKETING-BRAND" and ("herald-comms" in action_required or "investor" in handoff["body"].lower() or "narrative" in handoff["body"].lower()):
        created.append(
            {
                "to": "HERALD-COMMS",
                "task_type": "narrative_alignment",
                "reason": "Marketing messaging work produced narrative inputs that should carry into founder and investor communications.",
                "subject": "Narrative Alignment",
                "action_required": "Fold the approved messaging foundation into founder-facing and investor-facing narrative materials.",
            }
        )
    if agent_id == "VECTOR-ANALYTICS" and ("meridian-orchestrator" in action_required or "north star" in handoff["body"].lower() or "dashboard" in handoff["body"].lower()):
        created.append(
            {
                "to": "MERIDIAN-ORCHESTRATOR",
                "task_type": "metric_alignment_review",
                "reason": "Analytics work defined operating metrics that should be reflected in the founder-level operating view.",
                "subject": "Metric Alignment Review",
                "action_required": "Review the recommended North Star and dashboard signals, then decide which metrics should appear in founder briefings.",
            }
        )
    if agent_id == "NEXUS-TALENT" and ("budget" in action_required or "fundraising" in action_required or "runway" in handoff["body"].lower()):
        created.append(
            {
                "to": "LEDGER-FINANCE",
                "task_type": "hiring_budget_alignment",
                "reason": "Talent planning surfaced a sequencing dependency on runway and fundraising timing.",
                "subject": "Hiring Budget Alignment",
                "action_required": "Assess when the next likely hires become financially responsible relative to current runway and fundraising assumptions.",
            }
        )

    return created


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
    created_paths: list[dict[str, str]] = []
    handoff_dir = instance_path / "outputs/handoffs"
    created = downstream_handoff_specs(agent_id=agent_id, project=project, handoff=handoff)

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

    existing_count = len(list(handoff_dir.glob(f"HANDOFF-{now.date().isoformat()}-{agent_id}-*.md")))
    for index, item in enumerate(created, start=1):
        signature = (agent_id, item["to"], project, item["task_type"])
        if signature in existing_signatures:
            continue
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
        existing_signatures.add(signature)
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
        downstream_specs = downstream_handoff_specs(agent_id=agent_id, project=project, handoff=handoff)

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

        handoff_lines = [f"- `{item['to']}` -> downstream handoff justified." for item in downstream_specs]
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

        downstream = downstream_handoffs_for_agent(
            instance_path=instance_path,
            agent_id=agent_id,
            project=project,
            handoff=handoff,
            output_relative_path=output_relative_path,
            run_id=run_id,
            now=now,
        )

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
