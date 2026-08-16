import enum


class Status(str, enum.Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    FAILURE = "failure"
