# relay/logging.py  — optional app-side helper, stdlib only
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # your current JsonFormatter silently drops tracebacks: logger.exception()
        # loses the stack because format() only builds those four fields.
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: int = logging.INFO, *, as_json: bool = True) -> None:
    """Configure the root logger once, from the application entrypoint.

    stdout only: in Kubernetes the collector reads container stdout, not
    files inside an ephemeral pod filesystem.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if as_json
        else logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
