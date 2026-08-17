# monitoring/config.py
import os
from dataclasses import dataclass, field

from ..core.config import TransportConfig


@dataclass(frozen=True, slots=True)
class MonitoringConfig:
    base_url: str
    password: str
    username: str = "admin"
    transport: TransportConfig = field(default_factory=TransportConfig)

    @classmethod
    def from_env(cls, prefix: str = "MONITORING_") -> "MonitoringConfig":
        return cls(
            base_url=os.environ[f"{prefix}URL"],  # raises if unset — url is mandatory
            password=os.environ[f"{prefix}BASIC_AUTH_PASSWORD"],  # raises if unset
            username=os.environ.get(f"{prefix}BASIC_AUTH_USERNAME", "admin"),
        )
