"""Directus REST client -- a small Protocol + one real implementation."""

from __future__ import annotations

import json
from typing import Protocol

from ..core.transport import build_client
from .config import DatahubConfig


class DatahubClientProtocol(Protocol):
    def create_item(self, collection: str, data: dict) -> dict: ...
    def update_item(self, collection: str, item_id: int, data: dict) -> dict: ...
    def list_items(
        self, collection: str, filter_: dict, limit: int = -1
    ) -> list[dict]: ...


class DatahubClient:
    def __init__(self, config: DatahubConfig) -> None:
        self._client = build_client(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.token}"},
            transport=config.transport,
        )

    def create_item(self, collection: str, data: dict) -> dict:
        resp = self._client.post(f"/items/{collection}", json=data)
        resp.raise_for_status()
        # Directus returns 204 No Content (empty body) on some instances/configs.
        return resp.json()["data"] if resp.content else {}

    def update_item(self, collection: str, item_id: int, data: dict) -> dict:
        resp = self._client.patch(f"/items/{collection}/{item_id}", json=data)
        resp.raise_for_status()
        return resp.json()["data"] if resp.content else {}

    def list_items(self, collection: str, filter_: dict, limit: int = -1) -> list[dict]:
        resp = self._client.get(
            f"/items/{collection}",
            params={"filter": json.dumps(filter_), "limit": limit},
        )
        resp.raise_for_status()
        return resp.json()["data"]
