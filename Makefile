PYTHON ?= python3

.PHONY: validate plan run-meridian drain

validate:
	PYTHONPYCACHEPREFIX=/tmp/founders-os-pyc $(PYTHON) -m py_compile runner/orchestrate.py runner/communications.py runner/google_workspace.py runner/smoke_test.py
	$(PYTHON) runner/smoke_test.py

plan:
	$(PYTHON) runner/orchestrate.py plan --instance-path .

run-meridian:
	$(PYTHON) runner/orchestrate.py run-once --agent MERIDIAN-ORCHESTRATOR --trigger-type heartbeat --reason make_run_meridian --instance-path . --project startup_ops --task-type operating_review --origin manual

drain:
	$(PYTHON) runner/orchestrate.py drain-queue --instance-path .
