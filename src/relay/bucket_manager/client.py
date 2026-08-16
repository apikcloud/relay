"""Directus REST client -- a small Protocol + one real implementation."""

from __future__ import annotations

import logging

import httpx

from ..core.transport import build_client
from .config import BucketManagerConfig

logger = logging.getLogger(__name__)


class BucketManager:
    def __init__(self, config: BucketManagerConfig | None = None) -> None:
        self._config = config
        self._client = (
            build_client(
                base_url=config.base_url,
                headers={"Authorization": f"Bearer {config.token}"},
                transport=config.transport,
            )
            if config
            else None
        )

    @classmethod
    def from_env(cls, prefix: str = "BUCKET_MANAGER_") -> BucketManager:
        try:
            config = BucketManagerConfig.from_env(prefix=prefix)
        except Exception as err:
            logger.error(str(err))
            config = None
        return cls(config)

    @property
    def is_active(self) -> bool:
        return bool(self._client)

    def ensure_bucket(self, name: str) -> bool:
        """Ask bucket-manager to ensure this project's S3 bucket exists and is policy-granted."""
        if not self.is_active:
            return False

        try:
            response = self._client.post(f"/buckets/{name}/ensure")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Error: %s", exc)
            return False

        return True
