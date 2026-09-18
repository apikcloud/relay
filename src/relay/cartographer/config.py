# cartographer/config.py
import os
from dataclasses import dataclass, field

from ..core.config import TransportConfig


@dataclass(frozen=True, slots=True)
class CartographerConfig:
    base_url: str = "https://cartographer.apik.tech"
    transport: TransportConfig = field(default_factory=TransportConfig)

    @classmethod
    def from_env(cls, prefix: str = "CARTOGRAPHER_") -> "CartographerConfig":
        base_url = os.environ.get(f"{prefix}URL", cls.base_url)
        return cls(base_url=base_url)
