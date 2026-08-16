# core/transport.py — shared httpx transport: timeout, max_retries, 429 Retry-After backoff
from __future__ import annotations

import time

import httpx

from .config import TransportConfig


class RetryTransport(httpx.HTTPTransport):
    """Retries transient connection errors and 429s, honoring `Retry-After`.

    Falls back to capped exponential backoff when a 429 has no `Retry-After`
    header, or when the error is a connection/timeout failure.
    """

    def __init__(self, config: TransportConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config = config

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = super().handle_request(request)
            except httpx.TransportError:
                if attempt >= self._config.max_retries:
                    raise
                time.sleep(_backoff_delay(attempt, self._config.backoff_cap))
                attempt += 1
                continue

            if response.status_code == 429 and attempt < self._config.max_retries:
                response.close()
                time.sleep(_retry_after_delay(response, attempt, self._config.backoff_cap))
                attempt += 1
                continue

            return response


def _backoff_delay(attempt: int, cap: float) -> float:
    return min(cap, 2**attempt)


def _retry_after_delay(response: httpx.Response, attempt: int, cap: float) -> float:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(cap, float(header))
        except ValueError:
            pass
    return _backoff_delay(attempt, cap)


def build_client(
    *,
    transport: TransportConfig,
    base_url: str = "",
    headers: dict | None = None,
) -> httpx.Client:
    return httpx.Client(
        base_url=base_url,
        headers=headers or {},
        timeout=transport.timeout,
        transport=RetryTransport(transport),
    )
