PYTHON ?= python3

.PHONY: validate plan run-meridian drain scaffold-project

validate:
	PYTHONPYCACHEPREFIX=/tmp/founders-os-pyc $(PYTHON) -m py_compile runner/orchestrate.py runner/communications.py runner/google_workspace.py runner/specialists.py runner/smoke_test.py
	$(PYTHON) runner/smoke_test.py

plan:
	$(PYTHON) runner/orchestrate.py plan --instance-path .

run-meridian:
	$(PYTHON) runner/orchestrate.py manual-meridian --instance-path .

drain:
	$(PYTHON) runner/orchestrate.py drain-queue --instance-path .

run-cycle:
	$(PYTHON) runner/orchestrate.py run-cycle --instance-path .

scaffold-project:
	$(PYTHON) runner/projects.py --instance-path . --name "$(NAME)" --project-key "$(KEY)" --type "$(TYPE)" --stage "$(STAGE)" --summary "$(SUMMARY)"
