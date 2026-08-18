"""Monitoring status client -- fetches endpoint statuses (availability
history) that consuming services use to detect incidents. Backed by Gatus
(https://gatus.io) today; the client/module is named after the role
(`monitoring`), not the backend vendor, matching `datahub` (Directus) and
`notify` (Apprise)."""

from __future__ import annotations

from ..core.transport import build_client
from .config import MonitoringConfig

_MAX_PAGES = 1000  # hard backstop; far above any realistic Gatus endpoint count


class MonitoringClient:
    def __init__(self, config: MonitoringConfig) -> None:
        self._client = build_client(
            base_url=config.base_url,
            transport=config.transport,
            auth=(config.username, config.password),
        )

    def fetch_statuses(self) -> list[dict]:
        """Return Gatus's raw /api/v1/endpoints/statuses payload (list of
        endpoint status dicts: name, group, key, results, events).

        Some Gatus deployments ignore `page` and return the full list on
        every request; if a page repeats the first page's keys, or the hard
        page cap is hit, the loop stops instead of running forever."""
        results: list[dict] = []
        first_page_keys: frozenset | None = None
        page = 0
        while True:
            resp = self._client.get(
                "/api/v1/endpoints/statuses", params={"page": page}
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            batch_keys = frozenset(item.get("key") for item in batch)
            if page == 0:
                first_page_keys = batch_keys
            elif batch_keys == first_page_keys:
                break
            results.extend(batch)
            page += 1
            if page >= _MAX_PAGES:
                break
        return results
