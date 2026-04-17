from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def canonical_project_identity(state: dict[str, Any], *, name: str, project_key: str | None) -> dict[str, str]:
    requested_key = (project_key or name).strip()
    requested_slug = slugify(requested_key or name)
    requested_name = name.strip()
    projects = state.get("projects", {})

    for existing_key, existing in projects.items():
        existing_slug = str(existing.get("slug", ""))
        existing_name = str(existing.get("name", existing_key))
        if requested_key and existing_key.lower() == requested_key.lower():
            return {"key": existing_key, "slug": existing_slug or slugify(existing_key), "name": existing_name}
        if requested_name and existing_name.lower() == requested_name.lower():
            return {"key": existing_key, "slug": existing_slug or slugify(existing_key), "name": existing_name}
        if requested_slug and existing_slug == requested_slug:
            return {"key": existing_key, "slug": existing_slug, "name": existing_name}

    return {"key": requested_key or requested_name, "slug": requested_slug, "name": requested_name}


def field_status(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or normalized in {"tbd", "none"}:
        return "unknown"
    unknown_markers = (
        "undetermined",
        "needs research",
        "needs validation",
        "needs to be researched",
        "needs some research",
        "to be determined",
        "not yet",
        "not clear",
        "all",
    )
    if any(marker in normalized for marker in unknown_markers):
        return "hypothesis"
    return "known"


def knowledge_block(items: list[tuple[str, str]]) -> list[str]:
    lines = ["## Knowledge Status", ""]
    for label, value in items:
        lines.append(f"- {label}: `{field_status(value)}`")
    lines.append("")
    return lines


def scaffold_project(instance_path: Path, *, name: str, project_key: str | None, project_type: str, stage: str, summary: str) -> dict[str, str]:
    state_path = instance_path / "outputs/state.json"
    state = load_json(state_path)

    identity = canonical_project_identity(state, name=name, project_key=project_key)
    slug = identity["slug"]
    key = identity["key"]
    name = identity["name"]
    project_dir = instance_path / "projects" / slug
    template_dir = instance_path / "projects" / "_template"

    if project_dir.exists():
        raise SystemExit(f"Project directory already exists: {project_dir}")
    if key in state.get("projects", {}):
        raise SystemExit(f"Project key already exists in state: {key}")
    if not template_dir.exists():
        raise SystemExit(f"Missing template directory: {template_dir}")

    shutil.copytree(template_dir, project_dir)

    project_overview = "\n".join(
        [
            f"# {name}",
            "",
            f"- Name: {name}",
            f"- Slug: {slug}",
            f"- Type: {project_type}",
            f"- Stage: {stage}",
            "- Status: Active",
            "- Owner: MERIDIAN-ORCHESTRATOR",
            f"- Summary: {summary}",
            "",
            "## Operating Posture",
            "",
            "- Stage template: idea-stage startup unless future evidence moves it forward.",
            "- Unknowns are expected and should be treated as explicit hypotheses rather than missing work.",
            "",
            "## Objective",
            "",
            "Describe what this startup is trying to prove or build now.",
        ]
    )
    (project_dir / "project.md").write_text(project_overview + "\n", encoding="utf-8")

    (project_dir / "outputs").mkdir(parents=True, exist_ok=True)

    state.setdefault("projects", {})[key] = {
        "folder_path": f"projects/{slug}",
        "last_activity_at": "",
        "name": name,
        "owner_agent": "MERIDIAN-ORCHESTRATOR",
        "priority": "medium",
        "project_id": slug,
        "slug": slug,
        "status": "in_progress",
        "summary": summary,
        "type": project_type,
        "work_mode": "project",
    }

    write_json(state_path, state)
    return {"name": name, "key": key, "slug": slug, "folder_path": f"projects/{slug}"}


def _render_section_file(title: str, sections: list[tuple[str, str]]) -> str:
    lines = [f"# {title}", ""]
    lines.extend(knowledge_block(sections))
    for heading, body in sections:
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(body.strip() if body.strip() else "TBD")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def upsert_project_from_intake(instance_path: Path, answers: dict[str, str]) -> dict[str, str]:
    name = answers.get("project_name", "").strip()
    if not name:
        raise SystemExit("Founder intake is missing Project Name.")

    requested_project_key = answers.get("project_key", "").strip() or name
    project_type = answers.get("project_type", "").strip() or "product"
    stage = answers.get("stage", "").strip() or "IDEA"
    summary = answers.get("summary", "").strip() or "Founder-defined startup project."

    state_path = instance_path / "outputs/state.json"
    state = load_json(state_path)
    identity = canonical_project_identity(state, name=name, project_key=requested_project_key)
    project_key = identity["key"]
    name = identity["name"] or name
    slug = identity["slug"]
    project_dir = instance_path / "projects" / slug

    if not project_dir.exists():
        scaffold_project(
            instance_path,
            name=name,
            project_key=project_key,
            project_type=project_type,
            stage=stage,
            summary=summary,
        )
        state = load_json(state_path)

    project_overview = "\n".join(
        [
            f"# {name}",
            "",
            f"- Name: {name}",
            f"- Slug: {slug}",
            f"- Type: {project_type}",
            f"- Stage: {stage}",
            "- Status: Active",
            "- Owner: MERIDIAN-ORCHESTRATOR",
            f"- Summary: {summary}",
            "",
            "## Operating Posture",
            "",
            f"- Stage template: `{stage}`",
            "- Treat unknowns as explicit hypotheses to validate, not as missing documentation.",
            "- Use specialist work to convert `unknown` and `hypothesis` sections into evidence-backed decisions.",
            "",
            *knowledge_block(
                [
                    ("Objective", answers.get("objective", "")),
                    ("Summary", summary),
                ]
            ),
            "## Objective",
            "",
            answers.get("objective", "").strip() or "TBD",
        ]
    )
    write_text(project_dir / "project.md", project_overview)
    write_text(
        project_dir / "problem.md",
        _render_section_file(
            "Problem",
            [
                ("Core Problem", answers.get("core_problem", "")),
                ("Who Feels It", answers.get("who_feels_it", "")),
                ("Why It Matters Now", answers.get("why_now", "")),
            ],
        ),
    )
    write_text(
        project_dir / "icp.md",
        _render_section_file(
            "ICP",
            [
                ("Primary ICP", answers.get("primary_icp", "")),
                ("Observable Traits", answers.get("observable_traits", "")),
                ("Early Adopters", answers.get("early_adopters", "")),
            ],
        ),
    )
    write_text(
        project_dir / "solution.md",
        _render_section_file(
            "Solution",
            [
                ("Product Wedge", answers.get("product_wedge", "")),
                ("Core Workflow", answers.get("core_workflow", "")),
                ("Why It Wins", answers.get("why_it_wins", "")),
            ],
        ),
    )
    write_text(
        project_dir / "validation.md",
        _render_section_file(
            "Validation",
            [
                ("Evidence Collected", answers.get("evidence_collected", "")),
                ("Assumptions To Test", answers.get("assumptions_to_test", "")),
                ("Next Proof Steps", answers.get("next_proof_steps", "")),
            ],
        ),
    )
    write_text(
        project_dir / "strategy.md",
        _render_section_file(
            "Strategy",
            [
                ("Go-To-Market", answers.get("go_to_market", "")),
                ("Positioning", answers.get("positioning", "")),
                ("Key Risks", answers.get("key_risks", "")),
            ],
        ),
    )
    write_text(
        project_dir / "financials.md",
        _render_section_file(
            "Financials",
            [
                ("Revenue Model", answers.get("revenue_model", "")),
                ("Costs And Burn", answers.get("costs_and_burn", "")),
                ("Fundraising Notes", answers.get("fundraising_notes", "")),
            ],
        ),
    )
    write_text(
        project_dir / "roadmap.md",
        _render_section_file(
            "Roadmap",
            [
                ("Now", answers.get("roadmap_now", "")),
                ("Next", answers.get("roadmap_next", "")),
                ("Later", answers.get("roadmap_later", "")),
            ],
        ),
    )
    write_text(
        project_dir / "decisions.md",
        _render_section_file(
            "Decisions",
            [
                ("Open Decisions", answers.get("open_decisions", "")),
                ("Locked Decisions", answers.get("locked_decisions", "")),
                ("Revisit Later", answers.get("revisit_later", "")),
            ],
        ),
    )

    state.setdefault("projects", {})[project_key] = {
        "folder_path": f"projects/{slug}",
        "last_activity_at": state.get("projects", {}).get(project_key, {}).get("last_activity_at", ""),
        "canonical_name": name,
        "canonical_key": project_key,
        "name": name,
        "owner_agent": "MERIDIAN-ORCHESTRATOR",
        "priority": state.get("projects", {}).get(project_key, {}).get("priority", "medium"),
        "project_id": slug,
        "slug": slug,
        "status": "in_progress",
        "summary": summary,
        "type": project_type,
        "work_mode": "project",
    }
    write_json(state_path, state)
    return {"name": name, "key": project_key, "slug": slug, "folder_path": f"projects/{slug}"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project scaffolding for SAITO")
    parser.add_argument("--instance-path", default=".")
    parser.add_argument("--name", required=True)
    parser.add_argument("--project-key")
    parser.add_argument("--type", default="product")
    parser.add_argument("--stage", default="IDEA")
    parser.add_argument("--summary", default="New startup project scaffolded from the SAITO template.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = scaffold_project(
        Path(args.instance_path).resolve(),
        name=args.name,
        project_key=args.project_key,
        project_type=args.type,
        stage=args.stage,
        summary=args.summary,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
