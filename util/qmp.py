import json
import logging
from collections.abc import Callable


class QMPMonitor:
    def __init__(self, monitor_out: Callable[[], str], monitor_in: Callable[[str], None]) -> None:
        self.monitor_out = monitor_out  # QMP output from QEMU
        self.monitor_in = monitor_in  # QMP input to QEMU
        self.logger = logging.getLogger(f"{self}")
        self._negotiate_capabilities()

    def _negotiate_capabilities(self) -> None:
        greeting = self._read_parse_json()
        if not greeting.get("QMP"):
            raise QMPError("QMP greeting message invalid")

        self.monitor_in(json.dumps({"execute": "qmp_capabilities"}))
        self.monitor_in("\n")

        answer = self._read_parse_json()
        if "return" not in answer:
            raise QMPError(f"Could not connect to QMP: {answer}")

    def _read_parse_json(self) -> dict:
        line = self.monitor_out()
        self.logger.debug("Received line: %s", line.rstrip("\r\n"))
        if not line:
            raise QMPError("Received empty response")
        return json.loads(line)

    def execute(self, command: str, arguments: dict | None = None) -> str:
        if arguments is None:
            arguments = {}
        json_command = {"execute": command, "arguments": arguments}

        self.monitor_in(json.dumps(json_command))
        self.monitor_in("\n")

        answer = self._read_parse_json()
        # skip all asynchronous events
        while answer.get("event"):
            answer = self._read_parse_json()
        if "error" in answer:
            raise QMPError(answer["error"])
        return answer["return"]


class QMPError(Exception):
    pass
