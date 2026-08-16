# core/config.py
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransportConfig:
    timeout: float = 10.0
    max_retries: int = 3
    backoff_cap: float = 30.0
