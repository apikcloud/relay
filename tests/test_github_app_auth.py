from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from relay.core.config import TransportConfig
from relay.github.app_auth import GithubAppAuth


@pytest.fixture(scope="module")
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _make_auth(keypair, handler) -> GithubAppAuth:
    private_pem, _ = keypair
    token_client = httpx.Client(
        base_url="http://github.test", transport=httpx.MockTransport(handler)
    )
    return GithubAppAuth(
        app_id="12345",
        installation_id="67890",
        private_key=private_pem,
        base_url="http://github.test",
        transport=TransportConfig(),
        token_client=token_client,
    )


def _make_client(keypair, handler) -> httpx.Client:
    auth = _make_auth(keypair, handler)
    return httpx.Client(
        base_url="http://github.test", transport=httpx.MockTransport(handler), auth=auth
    )


def _token_response(token: str, expires_at: datetime) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "token": token,
            "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )


def test_jwt_claims_and_signature(keypair):
    _, public_pem = keypair
    auth = _make_auth(keypair, lambda request: httpx.Response(200, json={}))

    token = auth._generate_jwt()
    claims = jwt.decode(token, public_pem, algorithms=["RS256"], options={"verify_exp": False})

    assert claims["iss"] == "12345"
    assert claims["exp"] - claims["iat"] == 60 + 540


def test_first_request_fetches_token_and_sets_header(keypair):
    calls = {"token_fetches": 0}
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            calls["token_fetches"] += 1
            return _token_response("installation-token-1", expires_at)
        assert request.headers["Authorization"] == "Bearer installation-token-1"
        return httpx.Response(200, json={})

    client = _make_client(keypair, handler)

    resp = client.get("/repos/foo/bar")

    assert resp.status_code == 200
    assert calls["token_fetches"] == 1


def test_cached_token_not_refetched_within_expiry(keypair):
    calls = {"token_fetches": 0}
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            calls["token_fetches"] += 1
            return _token_response("installation-token-1", expires_at)
        return httpx.Response(200, json={})

    client = _make_client(keypair, handler)

    client.get("/repos/foo/bar")
    client.get("/repos/foo/bar")

    assert calls["token_fetches"] == 1


def test_expired_token_triggers_refetch(keypair):
    calls = {"token_fetches": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            calls["token_fetches"] += 1
            expires_at = datetime.now(UTC) + timedelta(hours=1)
            return _token_response(f"installation-token-{calls['token_fetches']}", expires_at)
        return httpx.Response(200, json={})

    auth = _make_auth(keypair, handler)
    client = httpx.Client(
        base_url="http://github.test", transport=httpx.MockTransport(handler), auth=auth
    )

    client.get("/repos/foo/bar")
    auth._expires_at = datetime.now(UTC) - timedelta(seconds=1)
    client.get("/repos/foo/bar")

    assert calls["token_fetches"] == 2


def test_401_triggers_one_forced_refresh_and_retry(keypair):
    calls = {"token_fetches": 0, "api_calls": 0}
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            calls["token_fetches"] += 1
            return _token_response(f"installation-token-{calls['token_fetches']}", expires_at)
        calls["api_calls"] += 1
        if calls["api_calls"] == 1:
            return httpx.Response(401, json={"message": "Bad credentials"})
        return httpx.Response(200, json={})

    client = _make_client(keypair, handler)

    resp = client.get("/repos/foo/bar")

    assert resp.status_code == 200
    assert calls["token_fetches"] == 2
    assert calls["api_calls"] == 2


def test_second_401_does_not_loop_forever(keypair):
    calls = {"token_fetches": 0, "api_calls": 0}
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            calls["token_fetches"] += 1
            return _token_response(f"installation-token-{calls['token_fetches']}", expires_at)
        calls["api_calls"] += 1
        return httpx.Response(401, json={"message": "Bad credentials"})

    client = _make_client(keypair, handler)

    resp = client.get("/repos/foo/bar")

    assert resp.status_code == 401
    assert calls["token_fetches"] == 2
    assert calls["api_calls"] == 2
