.PHONY: all
all:
	echo "Please select `test-docker` or `test-local` manually."

.PHONY: test-docker
test-docker:
	docker compose build \
		--build-arg USER_ID=$$(id -u) \
		--build-arg GROUP_ID=$$(id -g) \
		--build-arg DOCKER_GID=$$(stat -c '%g' /var/run/docker.sock)
	docker compose up -d
	docker compose exec -ti debian pytest -svv --lg-env config/qemu.yaml

.PHONY: test-local
test-local:
	pytest -vv --lg-env config/qemu.yaml

qemu_demo.cast:
	asciinema rec -c "make test-docker" qemu_demo.cast

qemu_demo.gif: qemu_demo.cast
	agg $< $@

img/qemu_demo-opt.gif: qemu_demo.gif
	gifsicle --lossy=80 -k 128 -O2 -Okeep-empty $< -o $@

.PHONY: check-format
check-format:
	ruff format --check

.PHONY: lint
lint:
	ruff check
