import json

import httpx
import pytest

from relay.github.client import GithubClient, GraphQLError, TreeTruncatedError
from relay.github.config import GithubConfig


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

    assert result == {
        "oca/repo-a": {"16.0": "aaa"},
        "oca/repo-b": {"17.0": "bbb"},
    }


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

    assert result == {"oca/repo-a": {"16.0": "aaa", "17.0": "bbb"}}
    assert calls["n"] == 2


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
