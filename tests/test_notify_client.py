import json

import httpx
import pytest

from relay.core.models import Status
from relay.notify.client import MAX_BODY_LEN, NotifyClient
from relay.notify.config import NotifyConfig


def _make_client(requests: list[httpx.Request]) -> NotifyClient:
    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        requests.append(request)
        return httpx.Response(200)

    client = NotifyClient(NotifyConfig(base_url="http://notify.test/notify/key"))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def _form_fields(request: httpx.Request) -> dict[str, str]:
    """Plain (non-file) fields of a multipart request."""
    _, boundary = request.headers["content-type"].split("boundary=")
    fields = {}
    for part in request.content.split(f"--{boundary}".encode()):
        head, _, value = part.partition(b"\r\n\r\n")
        if b"filename=" in head or b'name="' not in head:
            continue
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        fields[name] = value.removesuffix(b"\r\n").decode()
    return fields


def test_notify_sends_type_value():
    requests: list[httpx.Request] = []
    _make_client(requests).warning(title="t", body="b")

    [request] = requests
    payload = json.loads(request.content)
    assert payload["type"] == "warning"
    assert payload["tag"] == ["jobs"]


def test_notify_with_attachment_sends_type_value_as_form_field():
    requests: list[httpx.Request] = []
    _make_client(requests).notify_with_attachment(
        title="t",
        body="<p>b</p>",
        content="# report",
        notify_type=Status.WARNING,
        filename="report.md",
        body_format="html",
    )

    [request] = requests
    fields = _form_fields(request)
    assert fields["type"] == "warning"  # not "Status.WARNING"
    assert fields["tag"] == "reports"
    assert fields["format"] == "html"
    assert b'filename="report.md"' in request.content


def test_notify_with_attachment_accepts_plain_type_value():
    requests: list[httpx.Request] = []
    _make_client(requests).notify_with_attachment(
        title="t", body="b", content="x", notify_type="failure"
    )

    assert _form_fields(requests[0])["type"] == "failure"


def test_notify_rejects_body_over_gateway_limit():
    requests: list[httpx.Request] = []
    client = _make_client(requests)

    with pytest.raises(ValueError, match="32769 chars"):
        client.notify(title="t", body="x" * (MAX_BODY_LEN + 1))
    with pytest.raises(ValueError):
        client.notify_with_attachment(
            title="t", body="x" * (MAX_BODY_LEN + 1), content="x"
        )
    assert requests == []


def test_notify_accepts_body_at_gateway_limit():
    requests: list[httpx.Request] = []
    _make_client(requests).notify(title="t", body="x" * MAX_BODY_LEN)

    assert len(requests) == 1


def test_inactive_client_still_rejects_oversized_body():
    with pytest.raises(ValueError):
        NotifyClient(None).notify(title="t", body="x" * (MAX_BODY_LEN + 1))


def test_failure_logs_response_text(caplog):
    client = NotifyClient(NotifyConfig(base_url="http://notify.test/notify/key"))
    client._client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, text="Bad FORM Payload provided")
        )
    )

    client.notify_with_attachment(title="t", body="b", content="x")

    assert "Bad FORM Payload provided" in caplog.text
