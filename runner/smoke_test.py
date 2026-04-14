from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def copy_repo(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".DS_Store"),
        dirs_exist_ok=True,
    )


def run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def queue_run(
    *,
    repo: Path,
    agent: str,
    reason: str,
    project: str,
    task_type: str,
    origin: str,
    changed_context: list[str] | None = None,
) -> None:
    command = [
        sys.executable,
        "runner/orchestrate.py",
        "run-once",
        "--agent",
        agent,
        "--trigger-type",
        "event" if agent != "MERIDIAN-ORCHESTRATOR" else "heartbeat",
        "--reason",
        reason,
        "--instance-path",
        ".",
        "--project",
        project,
        "--task-type",
        task_type,
        "--origin",
        origin,
    ]
    for path in changed_context or []:
        command.extend(["--changed-context", path])
    run(command, repo)


def latest_result_for_agent(temp_repo: Path, agent_id: str) -> dict[str, object]:
    results = []
    for path in sorted((temp_repo / "runtime/results").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("agent_id") == agent_id:
            results.append(payload)
    if not results:
        raise RuntimeError(f"No runtime result found for {agent_id}")
    return results[-1]


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="founders-os-smoke-") as tmp_dir:
        temp_repo = Path(tmp_dir) / "repo"
        copy_repo(repo_root, temp_repo)

        forge_handoff = "outputs/handoffs/HANDOFF-2026-04-13-MERIDIAN-ORCHESTRATOR-001.md"
        state_before = json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
        meridian_before = state_before["agents"]["MERIDIAN-ORCHESTRATOR"]["last_run"]

        queue_run(
            repo=temp_repo,
            agent="FORGE-ENGINEERING",
            reason="smoke_test_forge",
            project="SIGNAL",
            task_type="implementation_plan",
            origin="validation",
            changed_context=[forge_handoff],
        )
        run([sys.executable, "runner/orchestrate.py", "drain-queue", "--instance-path", "."], temp_repo)

        forge_result = latest_result_for_agent(temp_repo, "FORGE-ENGINEERING")
        if forge_result.get("status") != "success":
            raise RuntimeError(f"Expected successful FORGE execution, got {forge_result.get('status')}")
        if not forge_result.get("output_paths"):
            raise RuntimeError("Expected FORGE to create a real output artifact")
        if forge_result.get("created_handoffs_count", 0) < 1:
            raise RuntimeError("Expected FORGE to create a downstream handoff")

        forge_output = temp_repo / str(forge_result["output_paths"][0])
        if not forge_output.exists():
            raise RuntimeError("Expected FORGE output artifact to exist")

        forge_source_handoff = (temp_repo / forge_handoff).read_text(encoding="utf-8")
        if "status: completed" not in forge_source_handoff:
            raise RuntimeError("Expected the consumed FORGE handoff to be marked completed")

        created_canvas_handoffs = sorted((temp_repo / "outputs/handoffs").glob("HANDOFF-*-FORGE-ENGINEERING-*.md"))
        if not created_canvas_handoffs:
            raise RuntimeError("Expected FORGE to create a downstream handoff file")

        queue_run(
            repo=temp_repo,
            agent="MERIDIAN-ORCHESTRATOR",
            reason="smoke_test_meridian_after_forge",
            project="startup_ops",
            task_type="operating_review",
            origin="validation",
        )
        run([sys.executable, "runner/orchestrate.py", "drain-queue", "--instance-path", "."], temp_repo)

        meridian_result = latest_result_for_agent(temp_repo, "MERIDIAN-ORCHESTRATOR")
        if meridian_result.get("status") != "success":
            raise RuntimeError(f"Expected successful MERIDIAN orchestration pass, got {meridian_result.get('status')}")
        if not meridian_result.get("output_paths"):
            raise RuntimeError("Expected MERIDIAN to create a founder-facing output")

        founder_output_path = temp_repo / str(meridian_result["output_paths"][0])
        founder_output = founder_output_path.read_text(encoding="utf-8")
        if "FORGE-ENGINEERING" not in founder_output:
            raise RuntimeError("Expected MERIDIAN briefing to summarize FORGE work")

        updated_state = json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
        meridian_after = updated_state["agents"]["MERIDIAN-ORCHESTRATOR"]
        if meridian_after["last_run"] == meridian_before:
            raise RuntimeError("Expected MERIDIAN last_run to be updated")
        if meridian_after.get("last_output") != meridian_result["output_paths"][0]:
            raise RuntimeError("Expected MERIDIAN state to track the produced founder output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
