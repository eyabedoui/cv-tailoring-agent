# ============================================================
# CV-Tailoring Agent — common development tasks
# Run with:  make <target>
# On Windows use:  python -m sandbox <command>  or  make via Git Bash / WSL
# Override Python with:  make PYTHON=python <target>
# ============================================================

PYTHON ?= python3

.PHONY: install test sandbox-setup sandbox-seed sandbox-reset run demo-fake run-auto eval-fake eval-real

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

sandbox-setup:
	$(PYTHON) -m sandbox setup

sandbox-seed:
	$(PYTHON) -m sandbox seed

sandbox-reset:
	$(PYTHON) -m sandbox reset

# Production run — requires OPENAI_API_KEY; waits for human approval at checkpoint
run:
	$(PYTHON) -m sandbox reset
	$(PYTHON) -m sandbox seed
	$(PYTHON) -m agent --model openai

# Auto-approve run for CI or demos (not for production use)
run-auto:
	$(PYTHON) -m sandbox reset
	$(PYTHON) -m sandbox seed
	$(PYTHON) -m agent --model openai --auto-approve

# Offline demo with fake model (auto-approved, no API key needed)
demo-fake:
	$(PYTHON) -m sandbox reset
	$(PYTHON) -m sandbox seed
	$(PYTHON) -m agent --model fake --auto-approve

eval-fake:
	$(PYTHON) -m eval.runner --model fake

eval-real:
	$(PYTHON) -m eval.runner --model real
