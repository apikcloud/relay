# datahub/config.py
import os
from dataclasses import dataclass, field

from ..core.config import TransportConfig


@dataclass(frozen=True, slots=True)
class BucketManagerConfig:
    base_url: str
    token: str
    # ensure_bucket is a best-effort, non-fatal call made once per project per
    # run — retrying transient failures just multiplies latency (up to ~47s
    # per call with the shared default) for no benefit, since a failure here
    # is already logged and tolerated by every caller.
    transport: TransportConfig = field(default_factory=lambda: TransportConfig(max_retries=0))

    @classmethod
    def from_env(cls, prefix: str = "BUCKET_MANAGER_") -> "BucketManagerConfig":
        return cls(
            base_url=os.environ[f"{prefix}URL"],  # raises if unset — url is mandatory
            token=os.environ[f"{prefix}TOKEN"],  # raises if unset — token is mandatory
        )
