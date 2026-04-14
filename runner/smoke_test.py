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


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="founders-os-smoke-") as tmp_dir:
        temp_repo = Path(tmp_dir) / "repo"
        copy_repo(repo_root, temp_repo)

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
                "smoke_test",
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

        json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
