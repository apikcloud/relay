# notify/config.py
import os
from dataclasses import dataclass, field

from ..core.config import TransportConfig


@dataclass(frozen=True, slots=True)
class NotifyConfig:
    base_url: str
    token: str | None = None
    jobs_tag: tuple[str, ...] = ("jobs",)
    reports_tag: tuple[str, ...] = ("reports",)
    transport: TransportConfig = field(default_factory=TransportConfig)

    @classmethod
    def from_env(cls, prefix: str = "NOTIFY_") -> "NotifyConfig":
        # raises if unset — url is mandatory
        return cls(
            base_url=os.environ[f"{prefix}URL"],
            # token=os.environ[f"{prefix}TOKEN"],
        )
