# ============================================================
# CV-Tailoring Agent — common development tasks
# Run with:  make <target>
# On Windows use:  python -m sandbox <command>  or  make via Git Bash / WSL
# ============================================================

.PHONY: install test sandbox-setup sandbox-seed sandbox-reset run-fake run

install:
	pip install -r requirements.txt

test:
	python -m pytest -q

sandbox-setup:
	python -m sandbox setup

sandbox-seed:
	python -m sandbox seed

sandbox-reset:
	python -m sandbox reset

run-fake:
	python -m sandbox reset
	python -m sandbox seed
	python -m agent --model fake --auto-approve

run:
	python -m sandbox reset
	python -m sandbox seed
	python -m agent --model anthropic --auto-approve
