# labgrid QEMU Sample

This repository demonstrates the use of [pytest](https://pytest.org/) and [labgrid](https://labgrid.readthedocs.io) for interacting with a QEMU virtual machine (VM) running the OpenWrt firmware.

Utilizing pytest and labgrid simplifies the creation of complex test scenarios, ensuring the reliable and efficient operation of the system under test with minimal code (i.e. less than 500 lines of Python code).

The controlled virtual testing environment enhances both accuracy and reliability of the firmare under test, providing a scalable solution for continuous integration and quality assurance in embedded systems.

## Overview

Our goal is to validate the ability of OpenWrt to establish an OpenVPN connection using a server hosted in a standalone Docker Compose environment which is set up in the course of the test execution process as well.

**Test steps**:

1. Boot the Firmware
2. Set up SSH access to the OpenWrt firmware
3. Generate PKI (CA + server/client certs)
4. Start dedicated docker compose environment with the OpenVPN server
5. Update list of packages in OpenWrt
6. Install OpenVPN client in OpenWrt
7. Set up OpenVPN client in OpenWrt
8. Configure firewall in OpenWrt
9. Verify the OpenVPN tunnel has been established successfully

## Requirements

- Linux Host
- Docker Engine + Docker Compose (see [Installation Instructions](https://docs.docker.com/engine/install/debian/))
- GNU Make

## Setup Instructions

1. **Clone the repository**:

``` shell
git clone https://github.com/honeytreelabs/labgrid-qemu-sample.git
cd labgrid-qemu-sample
```

2. **Prepare the Environment:**

Ensure all the necessary dependencies are met on your host machine.
   
3. **Running Tests**:

```shell
make test-docker
```

## Demo

This is what you should see when running this sample:

![](./qemu_demo-opt.gif)
