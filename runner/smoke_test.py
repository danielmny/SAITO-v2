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


def seed_meridian_handoff(temp_repo: Path) -> str:
    handoff_id = "HANDOFF-2026-04-14-TEST-MERIDIAN-001"
    handoff_path = temp_repo / "outputs/handoffs" / f"{handoff_id}.md"
    handoff_path.write_text(
        "\n".join(
            [
                "---",
                f"handoff_id: {handoff_id}",
                "from: FORGE-ENGINEERING",
                "to: MERIDIAN-ORCHESTRATOR",
                "project: startup_ops",
                "task_type: operating_review",
                "origin: handoff",
                "status: queued",
                "created_at: 2026-04-14T15:00:00+02:00",
                "reason: Smoke test requests a real MERIDIAN orchestration pass.",
                "source_output: outputs/FORGE-ENGINEERING/2026-04-14-test.md",
                "compatibility: canonical",
                "---",
                "",
                "## ACTION REQUIRED: Summarize this handoff in a founder-facing MERIDIAN briefing.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return handoff_id


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="founders-os-smoke-") as tmp_dir:
        temp_repo = Path(tmp_dir) / "repo"
        copy_repo(repo_root, temp_repo)
        handoff_id = seed_meridian_handoff(temp_repo)

        state_before = json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
        meridian_before = state_before["agents"]["MERIDIAN-ORCHESTRATOR"]
        last_run_before = meridian_before["last_run"]

        run(
            [
                sys.executable,
                "runner/orchestrate.py",
                "run-once",
                "--agent",
                "MERIDIAN-ORCHESTRATOR",
                "--trigger-type",
                "heartbeat",
                "--reason",
                "smoke_test_meridian",
                "--instance-path",
                ".",
                "--project",
                "startup_ops",
                "--task-type",
                "operating_review",
                "--origin",
                "validation",
            ],
            temp_repo,
        )
        run([sys.executable, "runner/orchestrate.py", "drain-queue", "--instance-path", "."], temp_repo)

        result_files = sorted((temp_repo / "runtime/results").glob("*.json"))
        if not result_files:
            raise RuntimeError("Smoke test expected at least one runtime result manifest")
        result = json.loads(result_files[-1].read_text(encoding="utf-8"))
        if result.get("status") != "success":
            raise RuntimeError(f"Expected a successful MERIDIAN orchestration pass, got: {result.get('status')}")
        if result.get("processed_handoffs_count", 0) < 1:
            raise RuntimeError("Expected MERIDIAN to process at least one handoff")
        if not result.get("output_paths"):
            raise RuntimeError("Expected MERIDIAN to create a founder-facing output")

        founder_output = temp_repo / result["output_paths"][0]
        if not founder_output.exists():
            raise RuntimeError("Expected founder-facing MERIDIAN output file to exist")

        updated_state = json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
        meridian_after = updated_state["agents"]["MERIDIAN-ORCHESTRATOR"]
        if meridian_after["last_run"] == last_run_before:
            raise RuntimeError("Expected MERIDIAN last_run to be updated")
        if meridian_after.get("last_output") != result["output_paths"][0]:
            raise RuntimeError("Expected MERIDIAN last_output to match the produced founder briefing")

        handoff_text = (temp_repo / "outputs/handoffs" / f"{handoff_id}.md").read_text(encoding="utf-8")
        if "status: processed" not in handoff_text:
            raise RuntimeError("Expected consumed MERIDIAN handoff to be marked processed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
