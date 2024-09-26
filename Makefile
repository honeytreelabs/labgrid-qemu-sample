all: test

.PHONY: test
test:
	pytest -vv --lg-env config/qemu.yaml

.PHONY: check-format
check-format:
	ruff format --check

.PHONY: lint
lint:
	ruff check
