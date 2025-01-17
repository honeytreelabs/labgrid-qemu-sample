from unittest.mock import MagicMock

from opkg import is_package_installed, list_installed_names

OPKG_LIST_INSTALLED_OUTPUT: str = """base-files - 1559-r24012-d8dd03c46f
bnx2-firmware - 20230804-1
busybox - 1.36.1-1
ca-bundle - 20230311-1
cgi-io - 2022-08-10-901b0f04-21
dnsmasq - 2.90-2
dropbear - 2022.82-6
e2fsprogs - 1.47.0-2
firewall4 - 2023-09-01-598d9fbb-1
fstools - 2023-02-28-bfe882d5-1
fwtool - 2019-11-12-8f7fe925-1
getrandom - 2022-08-13-4c7b720b-2
grub2 - 2.06-5
grub2-bios-setup - 2.06-5
grub2-efi - 2.06-5
jansson4 - 2.14-3
jshn - 2023-05-23-75a3b870-1
jsonfilter - 2024-01-23-594cfa86-1
kernel - 5.15.162-1-59d1431675acc6823a33c7eb2323daeb
kmod-amazon-ena - 5.15.162-1
kmod-amd-xgbe - 5.15.162-1
kmod-bnx2 - 5.15.162-1
kmod-button-hotplug - 5.15.162-3
kmod-crypto-acompress - 5.15.162-1
kmod-crypto-crc32c - 5.15.162-1
kmod-crypto-hash - 5.15.162-1
kmod-e1000 - 5.15.162-1
kmod-e1000e - 5.15.162-1
kmod-forcedeth - 5.15.162-1
kmod-fs-vfat - 5.15.162-1
kmod-hwmon-core - 5.15.162-1
kmod-i2c-algo-bit - 5.15.162-1
kmod-i2c-core - 5.15.162-1
kmod-igb - 5.15.162-1
kmod-igc - 5.15.162-1
kmod-input-core - 5.15.162-1
kmod-ixgbe - 5.15.162-1
kmod-lib-crc-ccitt - 5.15.162-1
kmod-lib-crc32c - 5.15.162-1
kmod-lib-lzo - 5.15.162-1
kmod-libphy - 5.15.162-1
kmod-mdio - 5.15.162-1
kmod-mdio-devres - 5.15.162-1
kmod-mii - 5.15.162-1
"""


def test_list_installed_names() -> None:
    shell = MagicMock()
    shell.run_check.return_value = OPKG_LIST_INSTALLED_OUTPUT.split("\n")

    assert list_installed_names(shell) == [
        "base-files",
        "bnx2-firmware",
        "busybox",
        "ca-bundle",
        "cgi-io",
        "dnsmasq",
        "dropbear",
        "e2fsprogs",
        "firewall4",
        "fstools",
        "fwtool",
        "getrandom",
        "grub2",
        "grub2-bios-setup",
        "grub2-efi",
        "jansson4",
        "jshn",
        "jsonfilter",
        "kernel",
        "kmod-amazon-ena",
        "kmod-amd-xgbe",
        "kmod-bnx2",
        "kmod-button-hotplug",
        "kmod-crypto-acompress",
        "kmod-crypto-crc32c",
        "kmod-crypto-hash",
        "kmod-e1000",
        "kmod-e1000e",
        "kmod-forcedeth",
        "kmod-fs-vfat",
        "kmod-hwmon-core",
        "kmod-i2c-algo-bit",
        "kmod-i2c-core",
        "kmod-igb",
        "kmod-igc",
        "kmod-input-core",
        "kmod-ixgbe",
        "kmod-lib-crc-ccitt",
        "kmod-lib-crc32c",
        "kmod-lib-lzo",
        "kmod-libphy",
        "kmod-mdio",
        "kmod-mdio-devres",
        "kmod-mii",
    ]


def test_is_package_installed() -> None:
    shell = MagicMock()
    shell.run_check.return_value = OPKG_LIST_INSTALLED_OUTPUT.split("\n")

    assert is_package_installed(shell, "kmod-ixgbe")
