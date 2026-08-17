"""Monitoring status client -- fetches endpoint statuses (availability
history) that consuming services use to detect incidents. Backed by Gatus
(https://gatus.io) today; the client/module is named after the role
(`monitoring`), not the backend vendor, matching `datahub` (Directus) and
`notify` (Apprise)."""

from __future__ import annotations

from ..core.transport import build_client
from .config import MonitoringConfig


class MonitoringClient:
    def __init__(self, config: MonitoringConfig) -> None:
        self._client = build_client(
            base_url=config.base_url,
            transport=config.transport,
            auth=(config.username, config.password),
        )

    def fetch_statuses(self) -> list[dict]:
        """Return Gatus's raw /api/v1/endpoints/statuses payload (list of
        endpoint status dicts: name, group, key, results, events)."""
        results: list[dict] = []
        page = 0
        while True:
            resp = self._client.get(
                "/api/v1/endpoints/statuses", params={"page": page}
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            results.extend(batch)
            page += 1
        return results
