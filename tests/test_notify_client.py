import json

import httpx

from relay.core.models import Status
from relay.notify.client import NotifyClient
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
