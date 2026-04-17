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


def scaffold_project(instance_path: Path, *, name: str, project_key: str | None, project_type: str, stage: str, summary: str) -> dict[str, str]:
    state_path = instance_path / "outputs/state.json"
    state = load_json(state_path)

    slug = slugify(project_key or name)
    key = project_key or name
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
