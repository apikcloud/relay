# cartographer/config.py
import os
from dataclasses import dataclass, field

from ..core.config import TransportConfig

DEFAULT_BASE_URL = "https://cartographer.apik.tech"


@dataclass(frozen=True, slots=True)
class CartographerConfig:
    base_url: str = DEFAULT_BASE_URL
    transport: TransportConfig = field(default_factory=TransportConfig)

    @classmethod
    def from_env(cls, prefix: str = "CARTOGRAPHER_") -> "CartographerConfig":
        # `cls.base_url` isn't usable as the fallback here: a slotted dataclass
        # doesn't keep a field's default as a class attribute (the slot
        # descriptor shadows it), so `cls.base_url` would return that
        # descriptor object, not the string.
        base_url = os.environ.get(f"{prefix}URL", DEFAULT_BASE_URL)
        return cls(base_url=base_url)
