.PHONY: help install test lint serve image run

IMAGE := afm-pathological

# List the targets
help:
	@echo 'install  create .venv with pytest and flake8'
	@echo 'test     run the tests'
	@echo 'lint     run flake8'
	@echo 'serve    run the server on port 8080 with no container'
	@echo 'image    build the container image $(IMAGE)'
	@echo 'run      run the container image on port 8080'

# Create .venv with pytest and flake8, with uv if it is installed
install:
	@if command -v uv >/dev/null 2>&1; then \
		[ -d .venv ] || uv venv .venv; \
		uv pip install --python .venv/bin/python pytest flake8; \
	else \
		[ -d .venv ] || python3 -m venv .venv; \
		.venv/bin/pip install pytest flake8; \
	fi

test:
	.venv/bin/pytest test --no-header -q

lint:
	.venv/bin/flake8 --max-line-length 120 afm_pathological test main.py

serve:
	PORT=8080 .venv/bin/python main.py

image:
	docker build -t $(IMAGE) .

run:
	docker run --rm -p 8080:8080 -e PATHOLOGICAL_OPERATOR -e PATHOLOGICAL_FAVICON $(IMAGE)
