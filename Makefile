all: test

.PHONY: test
test:
	pytest -vv --lg-env config/qemu.yaml
