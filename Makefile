all: test

.PHONY: test
test:
	pytest -vv --lg-env config/local.yaml
