# github/config.py
import os
from dataclasses import dataclass, field

from ..core.config import TransportConfig


@dataclass(frozen=True, slots=True)
class GithubConfig:
    token: str
    base_url: str = "https://api.github.com"
    transport: TransportConfig = field(default_factory=TransportConfig)

    @classmethod
    def from_env(cls, prefix: str = "GITHUB_") -> "GithubConfig":
        return cls(
            token=os.environ[f"{prefix}TOKEN"],  # raises if unset — token is mandatory
        )
