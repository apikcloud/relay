import httpx

from relay.monitoring.client import MonitoringClient
from relay.monitoring.config import MonitoringConfig


def _make_client(handler: httpx.MockTransport) -> MonitoringClient:
    client = MonitoringClient(
        MonitoringConfig(base_url="http://gatus.test", password="secret")
    )
    client._client = httpx.Client(base_url="http://gatus.test", transport=handler)
    return client


def test_fetch_statuses_normal_pagination():
    pages = {
        0: [{"key": "a"}, {"key": "b"}],
        1: [{"key": "c"}],
        2: [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(200, json=pages[page])

    client = _make_client(httpx.MockTransport(handler))

    results = client.fetch_statuses()

    assert results == [{"key": "a"}, {"key": "b"}, {"key": "c"}]


def test_fetch_statuses_stops_when_page_ignored_and_repeats():
    batch = [{"key": "a"}, {"key": "b"}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=batch)

    client = _make_client(httpx.MockTransport(handler))

    results = client.fetch_statuses()

    assert results == batch
