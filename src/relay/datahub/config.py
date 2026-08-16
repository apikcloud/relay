# datahub/config.py
import os
from dataclasses import dataclass, field

from ..core.config import TransportConfig


@dataclass(frozen=True, slots=True)
class DatahubConfig:
    base_url: str
    token: str
    transport: TransportConfig = field(default_factory=TransportConfig)

    @classmethod
    def from_env(cls, prefix: str = "DATAHUB_") -> "DatahubConfig":
        return cls(
            base_url=os.environ[f"{prefix}URL"],  # raises if unset — url is mandatory
            token=os.environ[f"{prefix}TOKEN"],  # raises if unset — token is mandatory
        )
