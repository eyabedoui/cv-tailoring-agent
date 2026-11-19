# ============================================================
# CV-Tailoring Agent — common development tasks
# Run with:  make <target>
# On Windows use:  python -m sandbox <command>  or  make via Git Bash / WSL
# ============================================================

.PHONY: install test sandbox-setup sandbox-seed sandbox-reset run-fake run

install:
	pip install -r requirements.txt

test:
	python3 -m pytest -q

sandbox-setup:
	python3 -m sandbox setup

sandbox-seed:
	python3 -m sandbox seed

sandbox-reset:
	python3 -m sandbox reset

run-fake:
	python3 -m sandbox reset
	python3 -m sandbox seed
	python3 -m agent --model fake --auto-approve

run:
	python3 -m sandbox reset
	python3 -m sandbox seed
	python3 -m agent --model openai --auto-approve

eval-fake:
	python3 -m eval.runner --model fake

eval-real:
	python3 -m eval.runner --model real
