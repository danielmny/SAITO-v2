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


def reset_runtime_fixture(repo: Path) -> None:
    for relative_dir in [
        "runtime/requests",
        "runtime/queue",
        "runtime/results",
        "runtime/logs",
        "outputs/handoffs",
        "outputs/ATLAS-RESEARCH",
        "outputs/CANVAS-PRODUCT",
        "outputs/COUNSEL-LEGAL",
        "outputs/CURRENT-SALES",
        "outputs/FORGE-ENGINEERING",
        "outputs/MARKETING-BRAND",
        "outputs/HERALD-COMMS",
        "outputs/LEDGER-FINANCE",
        "outputs/NEXUS-TALENT",
        "outputs/VECTOR-ANALYTICS",
    ]:
        target = repo / relative_dir
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)

    pending_escalations = repo / "outputs/escalations/pending"
    if pending_escalations.exists():
        for path in pending_escalations.glob("*.md"):
            path.unlink()

    projects_root = repo / "projects"
    if projects_root.exists():
        for project_dir in projects_root.iterdir():
            outputs_dir = project_dir / "outputs"
            if outputs_dir.exists():
                shutil.rmtree(outputs_dir, ignore_errors=True)

    schedule_path = repo / "config/schedule.json"
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    for entry in schedule.get("agents", {}).values():
        entry["quiet_hours_policy"] = {"mode": "allow", "start_hour_local": 0, "end_hour_local": 0}
    schedule_path.write_text(json.dumps(schedule, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_handoff(
    *,
    repo: Path,
    handoff_id: str,
    to_agent: str,
    task_type: str,
    reason: str,
    subject: str,
    action_required: str,
) -> str:
    handoff_path = repo / "outputs/handoffs" / f"{handoff_id}.md"
    handoff_path.write_text(
        "\n".join(
            [
                "---",
                f"handoff_id: {handoff_id}",
                "from: MERIDIAN-ORCHESTRATOR",
                f"to: {to_agent}",
                "project: SIGNAL",
                f"task_type: {task_type}",
                "origin: founder_request",
                "status: queued",
                "created_at: 2026-04-17T10:00:00+00:00",
                f"reason: {reason}",
                "source_output: outputs/MERIDIAN-ORCHESTRATOR/2026-04-14-operating-checkpoint.md",
                "compatibility: canonical",
                "---",
                "## FROM: MERIDIAN-ORCHESTRATOR",
                f"## TO: {to_agent}",
                "## PROJECT: SIGNAL",
                f"## TASK TYPE: {task_type}",
                "## ORIGIN: founder_request",
                f"## RE: {subject}",
                "## CONTEXT: Seeded by smoke test.",
                "## OUTPUT: None yet.",
                f"## ACTION REQUIRED: {action_required}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return handoff_path.relative_to(repo).as_posix()


def queue_run(
    *,
    repo: Path,
    agent: str,
    trigger_type: str,
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
        trigger_type,
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


def latest_result_for_agent_with_status(temp_repo: Path, agent_id: str, status: str) -> dict[str, object]:
    matches = []
    for path in sorted((temp_repo / "runtime/results").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("agent_id") == agent_id and payload.get("status") == status:
            matches.append(payload)
    if not matches:
        raise RuntimeError(f"No runtime result found for {agent_id} with status {status}")
    return matches[-1]


def result_count_for_agent(temp_repo: Path, agent_id: str) -> int:
    count = 0
    for path in sorted((temp_repo / "runtime/results").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("agent_id") == agent_id:
            count += 1
    return count


def write_state(repo: Path, state: dict[str, object]) -> None:
    (repo / "outputs/state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="founders-os-smoke-") as tmp_dir:
        temp_repo = Path(tmp_dir) / "repo"
        copy_repo(repo_root, temp_repo)
        reset_runtime_fixture(temp_repo)

        forge_handoff = write_handoff(
            repo=temp_repo,
            handoff_id="HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-901",
            to_agent="FORGE-ENGINEERING",
            task_type="implementation_plan",
            reason="Need an implementation plan for the psychographic matching core.",
            subject="Implementation Plan",
            action_required="Produce the implementation plan and flag any CANVAS-PRODUCT dependency that must be resolved before build execution continues.",
        )
        write_handoff(
            repo=temp_repo,
            handoff_id="HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-902",
            to_agent="FORGE-ENGINEERING",
            task_type="implementation_plan",
            reason="Need a second implementation note tied to the same project.",
            subject="Implementation Plan Follow-up",
            action_required="Extend the engineering plan with sequencing notes and keep any CANVAS-PRODUCT dependency explicit.",
        )

        state_before = json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
        meridian_before = state_before["agents"]["MERIDIAN-ORCHESTRATOR"]["last_run"]

        run([sys.executable, "runner/orchestrate.py", "plan", "--instance-path", "."], temp_repo)
        queued_requests = sorted((temp_repo / "runtime/queue").glob("*.json"))
        forge_requests = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in queued_requests
            if json.loads(path.read_text(encoding="utf-8")).get("agent_id") == "FORGE-ENGINEERING"
        ]
        if len(forge_requests) != 1:
            raise RuntimeError(f"Expected planner to coalesce FORGE into one queued request, got {len(forge_requests)}")
        if sorted(forge_requests[0].get("changed_context", [])) != sorted(
            [
                "outputs/handoffs/HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-901.md",
                "outputs/handoffs/HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-902.md",
            ]
        ):
            raise RuntimeError("Expected planner to carry both pending FORGE handoffs into one request")

        run([sys.executable, "runner/orchestrate.py", "drain-queue", "--instance-path", "."], temp_repo)

        forge_result = latest_result_for_agent(temp_repo, "FORGE-ENGINEERING")
        if forge_result.get("status") != "success":
            raise RuntimeError(f"Expected successful FORGE execution, got {forge_result.get('status')}")
        if not forge_result.get("output_paths"):
            raise RuntimeError("Expected FORGE to create a real output artifact")
        if forge_result.get("created_handoffs_count", 0) < 1:
            raise RuntimeError("Expected FORGE to create a downstream handoff")
        if forge_result.get("processed_handoffs_count") != 2:
            raise RuntimeError("Expected FORGE to consume both coalesced handoffs")

        forge_output = temp_repo / str(forge_result["output_paths"][0])
        if not forge_output.exists():
            raise RuntimeError("Expected FORGE output artifact to exist")

        for seeded_handoff in [
            forge_handoff,
            "outputs/handoffs/HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-902.md",
        ]:
            handoff_text = (temp_repo / seeded_handoff).read_text(encoding="utf-8")
            if "status: completed" not in handoff_text:
                raise RuntimeError("Expected each consumed FORGE handoff to be marked completed")

        created_canvas_handoffs = sorted((temp_repo / "outputs/handoffs").glob("HANDOFF-*-FORGE-ENGINEERING-*.md"))
        if len(created_canvas_handoffs) != 1:
            raise RuntimeError("Expected FORGE to create a downstream handoff file")

        herald_handoff = write_handoff(
            repo=temp_repo,
            handoff_id="HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-903",
            to_agent="HERALD-COMMS",
            task_type="communications_brief",
            reason="Need narrative work tied to early fundraising readiness.",
            subject="Communications Brief",
            action_required="Draft the narrative and keep any LEDGER-FINANCE dependency explicit for investor-list and data-room planning.",
        )
        queue_run(
            repo=temp_repo,
            agent="HERALD-COMMS",
            trigger_type="event",
            reason="smoke_test_herald",
            project="SIGNAL",
            task_type="communications_brief",
            origin="validation",
            changed_context=[herald_handoff],
        )
        run([sys.executable, "runner/orchestrate.py", "drain-queue", "--instance-path", "."], temp_repo)

        herald_result = latest_result_for_agent(temp_repo, "HERALD-COMMS")
        if herald_result.get("status") != "success":
            raise RuntimeError(f"Expected successful HERALD execution, got {herald_result.get('status')}")
        if herald_result.get("created_handoffs_count", 0) < 1:
            raise RuntimeError("Expected HERALD to create a downstream LEDGER handoff")

        write_handoff(
            repo=temp_repo,
            handoff_id="HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-904",
            to_agent="MARKETING-BRAND",
            task_type="marketing_brief",
            reason="Need messaging and demand framing for early outreach.",
            subject="Marketing Brief",
            action_required="Write the memo to outputs/MARKETING-BRAND and coordinate assumptions with ATLAS-RESEARCH and HERALD-COMMS outputs.",
        )
        write_handoff(
            repo=temp_repo,
            handoff_id="HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-905",
            to_agent="VECTOR-ANALYTICS",
            task_type="analytics_brief",
            reason="Need a north-star metric and instrumentation baseline.",
            subject="Analytics Brief",
            action_required="Write the memo to outputs/VECTOR-ANALYTICS and coordinate metric definitions with CANVAS-PRODUCT, CURRENT-SALES, and MERIDIAN-ORCHESTRATOR priorities.",
        )
        write_handoff(
            repo=temp_repo,
            handoff_id="HANDOFF-2026-04-17-MERIDIAN-ORCHESTRATOR-906",
            to_agent="NEXUS-TALENT",
            task_type="talent_brief",
            reason="Need an early talent readiness snapshot tied to current build and GTM demands.",
            subject="Talent Brief",
            action_required="Write the brief to outputs/NEXUS-TALENT and flag any sequencing dependencies with budget or fundraising constraints.",
        )

        updated_state = json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
        updated_state["agents"]["MERIDIAN-ORCHESTRATOR"]["last_run"] = ""
        updated_state["agents"]["MERIDIAN-ORCHESTRATOR"]["cooldown_until"] = ""
        updated_state["agents"]["ATLAS-RESEARCH"]["last_success"] = "2026-04-17T10:05:00+00:00"
        updated_state["agents"]["ATLAS-RESEARCH"]["status"] = "success"
        updated_state["agents"]["CURRENT-SALES"]["last_success"] = "2026-04-17T10:05:00+00:00"
        updated_state["agents"]["CURRENT-SALES"]["status"] = "success"
        write_state(temp_repo, updated_state)

        run([sys.executable, "runner/orchestrate.py", "plan", "--instance-path", "."], temp_repo)
        queued_requests = sorted((temp_repo / "runtime/queue").glob("*.json"))
        queued_agent_ids = sorted(json.loads(path.read_text(encoding="utf-8")).get("agent_id", "") for path in queued_requests)
        for agent_id in ["CANVAS-PRODUCT", "LEDGER-FINANCE", "MARKETING-BRAND", "NEXUS-TALENT"]:
            if agent_id not in queued_agent_ids:
                raise RuntimeError(f"Expected queued downstream request for {agent_id}, got {queued_agent_ids}")

        run([sys.executable, "runner/orchestrate.py", "drain-queue", "--instance-path", "."], temp_repo)

        canvas_result = latest_result_for_agent(temp_repo, "CANVAS-PRODUCT")
        ledger_result = latest_result_for_agent(temp_repo, "LEDGER-FINANCE")
        marketing_result = latest_result_for_agent(temp_repo, "MARKETING-BRAND")
        nexus_result = latest_result_for_agent(temp_repo, "NEXUS-TALENT")
        if canvas_result.get("status") != "success":
            raise RuntimeError(f"Expected successful CANVAS execution, got {canvas_result.get('status')}")
        if ledger_result.get("status") != "success":
            raise RuntimeError(f"Expected successful LEDGER execution, got {ledger_result.get('status')}")
        if marketing_result.get("status") != "success":
            raise RuntimeError(f"Expected successful MARKETING execution, got {marketing_result.get('status')}")
        if nexus_result.get("status") != "success":
            raise RuntimeError(f"Expected successful NEXUS execution, got {nexus_result.get('status')}")
        if not canvas_result.get("output_paths"):
            raise RuntimeError("Expected CANVAS to create a real output artifact")
        if not ledger_result.get("output_paths"):
            raise RuntimeError("Expected LEDGER to create a real output artifact")
        if not marketing_result.get("output_paths"):
            raise RuntimeError("Expected MARKETING to create a real output artifact")
        if not nexus_result.get("output_paths"):
            raise RuntimeError("Expected NEXUS to create a real output artifact")
        if result_count_for_agent(temp_repo, "CANVAS-PRODUCT") != 1:
            raise RuntimeError("Expected exactly one CANVAS runtime result in the smoke test")
        if result_count_for_agent(temp_repo, "LEDGER-FINANCE") != 1:
            raise RuntimeError("Expected exactly one LEDGER runtime result in the smoke test")
        if result_count_for_agent(temp_repo, "MARKETING-BRAND") != 1:
            raise RuntimeError("Expected exactly one MARKETING runtime result in the smoke test")
        if result_count_for_agent(temp_repo, "NEXUS-TALENT") != 1:
            raise RuntimeError("Expected exactly one NEXUS runtime result in the smoke test")

        run([sys.executable, "runner/orchestrate.py", "plan", "--instance-path", "."], temp_repo)
        queued_requests = sorted((temp_repo / "runtime/queue").glob("*.json"))
        queued_agent_ids = sorted(json.loads(path.read_text(encoding="utf-8")).get("agent_id", "") for path in queued_requests)
        for agent_id in ["VECTOR-ANALYTICS", "COUNSEL-LEGAL"]:
            if agent_id not in queued_agent_ids:
                raise RuntimeError(f"Expected queued {agent_id} request after downstream specialist success, got {queued_agent_ids}")

        run([sys.executable, "runner/orchestrate.py", "drain-queue", "--instance-path", "."], temp_repo)

        vector_result = latest_result_for_agent(temp_repo, "VECTOR-ANALYTICS")
        counsel_result = latest_result_for_agent(temp_repo, "COUNSEL-LEGAL")
        if vector_result.get("status") != "success":
            raise RuntimeError(f"Expected successful VECTOR execution, got {vector_result.get('status')}")
        if counsel_result.get("status") != "success":
            raise RuntimeError(f"Expected successful COUNSEL execution, got {counsel_result.get('status')}")
        if not vector_result.get("output_paths"):
            raise RuntimeError("Expected VECTOR to create a real output artifact")
        if not counsel_result.get("output_paths"):
            raise RuntimeError("Expected COUNSEL to create a real output artifact")
        if result_count_for_agent(temp_repo, "VECTOR-ANALYTICS") != 1:
            raise RuntimeError("Expected exactly one VECTOR runtime result in the smoke test")
        if result_count_for_agent(temp_repo, "COUNSEL-LEGAL") != 1:
            raise RuntimeError("Expected exactly one COUNSEL runtime result in the smoke test")

        updated_state = json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
        updated_state["agents"]["MERIDIAN-ORCHESTRATOR"]["last_run"] = ""
        updated_state["agents"]["MERIDIAN-ORCHESTRATOR"]["cooldown_until"] = ""
        write_state(temp_repo, updated_state)

        queue_run(
            repo=temp_repo,
            agent="MERIDIAN-ORCHESTRATOR",
            trigger_type="heartbeat",
            reason="smoke_test_meridian_after_forge",
            project="startup_ops",
            task_type="operating_review",
            origin="validation",
        )
        run([sys.executable, "runner/orchestrate.py", "drain-queue", "--instance-path", "."], temp_repo)

        meridian_result = latest_result_for_agent(temp_repo, "MERIDIAN-ORCHESTRATOR")
        if meridian_result.get("status") not in {"success", "skipped"}:
            raise RuntimeError(f"Expected MERIDIAN orchestration to complete or skip cleanly, got {meridian_result.get('status')}")

        successful_meridian_result = latest_result_for_agent_with_status(temp_repo, "MERIDIAN-ORCHESTRATOR", "success")
        if not successful_meridian_result.get("output_paths"):
            raise RuntimeError("Expected MERIDIAN to create a founder-facing output during the smoke test")

        founder_output_path = temp_repo / str(successful_meridian_result["output_paths"][0])
        founder_output = founder_output_path.read_text(encoding="utf-8")
        for section in [
            "## Wins",
            "## Risks",
            "## Decisions Needed",
            "## Next Actions",
            "## Open Handoffs Summary",
            "## Escalation Summary",
        ]:
            if section not in founder_output:
                raise RuntimeError(f"Expected MERIDIAN briefing to include section {section}")

        updated_state = json.loads((temp_repo / "outputs/state.json").read_text(encoding="utf-8"))
        meridian_after = updated_state["agents"]["MERIDIAN-ORCHESTRATOR"]
        if meridian_after["last_run"] == meridian_before:
            raise RuntimeError("Expected MERIDIAN last_run to be updated")
        if meridian_after.get("last_output") != successful_meridian_result["output_paths"][0]:
            raise RuntimeError("Expected MERIDIAN state to track the produced founder output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
