PYTHON ?= python

.PHONY: help ui share bundle release core security github

help:
	@echo "Zero OS tasks"
	@echo "  make ui        Launch the best available Zero OS UI"
	@echo "  make bundle    Export a clean Zero OS bundle into dist/"
	@echo "  make share     Create a shareable Zero OS zip package"
	@echo "  make release   Create a share zip and print the tag flow"
	@echo "  make core      Run Zero OS core status"
	@echo "  make security  Run Zero OS security overview"
	@echo "  make github    Run Zero OS GitHub status"

ui:
	$(PYTHON) zero_os_ui.py

bundle:
	$(PYTHON) src/main.py "zero os export bundle"

share:
	$(PYTHON) src/main.py "zero os share package"

release: share
	@echo git tag v1.0.0
	@echo git push origin v1.0.0

core:
	$(PYTHON) src/main.py "core status"

security:
	$(PYTHON) src/main.py "security overview"

github:
	$(PYTHON) src/main.py "github status"
