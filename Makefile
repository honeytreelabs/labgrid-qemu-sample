IMAGE := openwrt-23.05.4-x86-64-generic-ext4-combined.img
IMAGE_URL := https://downloads.openwrt.org/releases/23.05.4/targets/x86/64/openwrt-23.05.4-x86-64-generic-ext4-combined.img.gz

all: test

test: $(IMAGE)
	pytest -vv --lg-env local.yaml -k shell

download: $(IMAGE)

$(IMAGE):
	curl -LO $(IMAGE_URL)
	-gunzip $(IMAGE).gz
