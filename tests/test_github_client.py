import json

import httpx
import pytest

from relay.github.client import GithubClient, GraphQLError, TreeTruncatedError
from relay.github.config import GithubConfig


def test_from_env_prefers_app_vars_when_present(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "67890")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\n...")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    config = GithubConfig.from_env()

    assert config.app_id == "12345"
    assert config.installation_id == "67890"
    assert config.token is None


def test_from_env_prefers_app_vars_over_token_when_both_set(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "67890")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\n...")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")

    config = GithubConfig.from_env()

    assert config.app_id == "12345"
    assert config.token is None


def test_from_env_falls_back_to_token_when_no_app_vars(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "secret")

    config = GithubConfig.from_env()

    assert config.token == "secret"
    assert config.app_id is None


def test_from_env_raises_on_partial_app_vars(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError):
        GithubConfig.from_env()


def test_from_env_raises_when_neither_set(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(KeyError):
        GithubConfig.from_env()


def _make_client(handler: httpx.MockTransport) -> GithubClient:
    client = GithubClient(GithubConfig(token="secret", base_url="http://github.test"))
    client._client = httpx.Client(base_url="http://github.test", transport=handler)
    return client


def test_graphql_raises_on_errors_array():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "boom"}]})

    client = _make_client(httpx.MockTransport(handler))

    with pytest.raises(GraphQLError):
        client.graphql("query {}", {})


def test_graphql_captures_rate_limit_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {}},
            headers={
                "X-RateLimit-Remaining": "4987",
                "X-RateLimit-Reset": "1700000000",
                "X-RateLimit-Limit": "5000",
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    client.graphql("query {}", {})

    assert client.last_rate_limit == {
        "remaining": "4987",
        "reset": "1700000000",
        "limit": "5000",
    }


def test_sweep_branch_heads_aliasing():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "r0" in body["query"]
        assert "r1" in body["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "r0": {
                        "refs": {
                            "nodes": [{"name": "16.0", "target": {"oid": "aaa"}}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    },
                    "r1": {
                        "refs": {
                            "nodes": [{"name": "17.0", "target": {"oid": "bbb"}}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    },
                }
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.sweep_branch_heads(["oca/repo-a", "oca/repo-b"])

    assert result.heads == {
        "oca/repo-a": {"16.0": "aaa"},
        "oca/repo-b": {"17.0": "bbb"},
    }
    assert result.unresolved == []


def test_sweep_branch_heads_paginates_per_repo():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "r0": {
                            "refs": {
                                "nodes": [{"name": "16.0", "target": {"oid": "aaa"}}],
                                "pageInfo": {"hasNextPage": True, "endCursor": "cur1"},
                            }
                        }
                    }
                },
            )
        assert body["variables"]["cursor"] == "cur1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "repository": {
                        "refs": {
                            "nodes": [{"name": "17.0", "target": {"oid": "bbb"}}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.sweep_branch_heads(["oca/repo-a"])

    assert result.heads == {"oca/repo-a": {"16.0": "aaa", "17.0": "bbb"}}
    assert result.unresolved == []
    assert calls["n"] == 2


def test_graphql_error_carries_structured_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errors": [{"type": "NOT_FOUND", "path": ["r0"], "message": "nope"}]},
        )

    client = _make_client(httpx.MockTransport(handler))

    with pytest.raises(GraphQLError) as exc_info:
        client.graphql("query {}", {})

    assert exc_info.value.errors == [
        {"type": "NOT_FOUND", "path": ["r0"], "message": "nope"}
    ]


def test_sweep_branch_heads_isolates_single_not_found():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.loads(request.content)
        if calls["n"] == 1:
            assert "r0" in body["query"]
            assert "r1" in body["query"]
            return httpx.Response(
                200,
                json={
                    "errors": [
                        {
                            "type": "NOT_FOUND",
                            "path": ["r1"],
                            "message": (
                                "Could not resolve to a Repository with the "
                                "name 'oca/missing'."
                            ),
                        }
                    ]
                },
            )
        assert "r0" in body["query"]
        assert "r1" not in body["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "r0": {
                        "refs": {
                            "nodes": [{"name": "16.0", "target": {"oid": "aaa"}}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.sweep_branch_heads(["oca/repo-a", "oca/missing"])

    assert result.heads == {"oca/repo-a": {"16.0": "aaa"}}
    assert result.unresolved == ["oca/missing"]
    assert calls["n"] == 2


def test_sweep_branch_heads_isolates_multiple_not_found_in_one_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "errors": [
                        {"type": "NOT_FOUND", "path": ["r0"], "message": "nope"},
                        {"type": "NOT_FOUND", "path": ["r2"], "message": "nope"},
                    ]
                },
            )
        body = json.loads(request.content)
        assert "r0" in body["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "r0": {
                        "refs": {
                            "nodes": [{"name": "16.0", "target": {"oid": "bbb"}}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.sweep_branch_heads(
        ["oca/missing-a", "oca/repo-b", "oca/missing-c"]
    )

    assert result.heads == {"oca/repo-b": {"16.0": "bbb"}}
    assert set(result.unresolved) == {"oca/missing-a", "oca/missing-c"}
    assert calls["n"] == 2


def test_sweep_branch_heads_all_not_found_no_extra_call():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200,
            json={"errors": [{"type": "NOT_FOUND", "path": ["r0"], "message": "nope"}]},
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.sweep_branch_heads(["oca/missing"])

    assert result.heads == {}
    assert result.unresolved == ["oca/missing"]
    assert calls["n"] == 1


def test_sweep_branch_heads_raises_on_non_not_found_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "errors": [
                    {"type": "RATE_LIMITED", "path": ["r0"], "message": "slow down"}
                ]
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    with pytest.raises(GraphQLError):
        client.sweep_branch_heads(["oca/repo-a"])


def test_list_tree_raises_on_truncation():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"truncated": True, "tree": []})

    client = _make_client(httpx.MockTransport(handler))

    with pytest.raises(TreeTruncatedError):
        client.list_tree("odoo/odoo", "deadbeef")


def test_list_tree_filters_to_blobs():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {"path": "addons/sale", "type": "tree"},
                    {"path": "addons/sale/__manifest__.py", "type": "blob"},
                ],
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    paths = client.list_tree("odoo/odoo", "deadbeef")

    assert paths == ["addons/sale/__manifest__.py"]


def test_compare_reports_truncation_when_files_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total_commits": 5000})

    client = _make_client(httpx.MockTransport(handler))

    result = client.compare("odoo/odoo", "base", "head")

    assert result.truncated is True
    assert result.files == []


def test_compare_not_truncated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"files": [{"filename": "a/__manifest__.py"}], "total_commits": 1}
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.compare("odoo/odoo", "base", "head")

    assert result.truncated is False
    assert result.files == ["a/__manifest__.py"]


def test_get_blobs_text_returns_none_for_missing_path():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "repository": {
                        "b0": {"text": "name = 'Sale'"},
                        "b1": None,
                    }
                }
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.get_blobs_text(
        "odoo/odoo", "16.0", ["addons/sale/__manifest__.py", "addons/sale/README.rst"]
    )

    assert result == {
        "addons/sale/__manifest__.py": "name = 'Sale'",
        "addons/sale/README.rst": None,
    }


def test_list_org_repos_paginates_until_empty_page():
    pages = {
        1: [{"full_name": "oca/a"}, {"full_name": "oca/b"}],
        2: [{"full_name": "oca/c"}],
        3: [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(200, json=pages[page])

    client = _make_client(httpx.MockTransport(handler))

    result = client.list_org_repos("oca")

    assert result == ["oca/a", "oca/b", "oca/c"]
