import json

import httpx

from relay.cartographer.client import CartographerClient
from relay.cartographer.config import CartographerConfig


def _make_client(handler: httpx.MockTransport) -> CartographerClient:
    client = CartographerClient(CartographerConfig(base_url="http://cartographer.test"))
    client._client = httpx.Client(
        base_url="http://cartographer.test", transport=handler
    )
    return client


def test_custom_repo_detail_parses_nested_refs_and_modules():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/code/custom/apik/client-repo"
        return httpx.Response(
            200,
            json={
                "repo": "apik/client-repo",
                "repo_url": "https://github.com/apik/client-repo",
                "refs": [
                    {
                        "ref": "19.0",
                        "ref_kind": "branch",
                        "odoo_version_raw": "19.0",
                        "requirements_python": ["foo"],
                        "requirements_bin": ["git"],
                        "readme_text": None,
                        "changelog_text": None,
                        "modules": [
                            {
                                "module_name": "my_module",
                                "submodule_repo": "apik/my-module",
                                "submodule_sha": "deadbeef",
                                "submodule_path": "my_module",
                                "submodule_branch": "19.0",
                                "hosted_by": [],
                            }
                        ],
                    }
                ],
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    detail = client.custom_repo_detail("apik/client-repo")

    assert detail.repo == "apik/client-repo"
    assert detail.repo_url == "https://github.com/apik/client-repo"
    assert len(detail.refs) == 1
    ref = detail.refs[0]
    assert ref.ref == "19.0"
    assert ref.ref_kind == "branch"
    assert ref.odoo_version_raw == "19.0"
    assert ref.requirements_python == ["foo"]
    assert ref.requirements_bin == ["git"]
    assert len(ref.modules) == 1
    module = ref.modules[0]
    assert module.module_name == "my_module"
    assert module.submodule_repo == "apik/my-module"
    assert module.submodule_path == "my_module"
    assert module.submodule_branch == "19.0"


def test_module_detail_parses_versions():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/code/modules/odoo/odoo/sale"
        return httpx.Response(
            200,
            json={
                "repo": "odoo/odoo",
                "kind": "core",
                "module_name": "sale",
                "depends": ["base"],
                "versions": [
                    {
                        "branch": "19.0",
                        "depends": ["base", "account"],
                        "installable": True,
                        "application": True,
                    }
                ],
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    module = client.module_detail("odoo/odoo", "sale")

    assert module.repo == "odoo/odoo"
    assert module.kind == "core"
    assert module.module_name == "sale"
    assert len(module.versions) == 1
    version = module.versions[0]
    assert version.branch == "19.0"
    assert version.depends == ["base", "account"]
    assert version.installable is True
    assert version.application is True


def test_live_refs_returns_branches_and_tags():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/code/custom/apik/client-repo/refs"
        return httpx.Response(
            200,
            json={"branches": {"19.0": "abc123"}, "tags": {"v1.0": "def456"}},
        )

    client = _make_client(httpx.MockTransport(handler))

    refs = client.live_refs("apik/client-repo")

    assert refs == {"branches": {"19.0": "abc123"}, "tags": {"v1.0": "def456"}}


def test_resolve_expand_sends_expected_body_and_parses_ambiguous_unavailable():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/code/resolve/expand"
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "modules": [
                    {"repo": "odoo/odoo", "module_name": "sale", "kind": "core"}
                ],
                "ambiguous": [
                    {
                        "module_name": "custom_sale",
                        "candidates": [{"repo": "odoo/odoo", "kind": "core"}],
                        "required_by": [],
                        "candidate_closures": {},
                    }
                ],
                "unavailable": [{"module_name": "missing_dep", "required_by": []}],
                "warnings": ["some warning"],
                "requirements_python": ["foo"],
                "requirements_bin": ["git"],
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.resolve_expand(
        [("apik/client-repo", "custom_sale")], series="19.0", enterprise=True
    )

    assert captured["body"] == {
        "modules": [{"repo": "apik/client-repo", "module_name": "custom_sale"}],
        "series": "19.0",
        "enterprise": True,
    }
    assert result.modules == [
        {"repo": "odoo/odoo", "module_name": "sale", "kind": "core"}
    ]
    assert result.ambiguous[0]["module_name"] == "custom_sale"
    assert result.unavailable[0]["module_name"] == "missing_dep"
    assert result.warnings == ["some warning"]
    assert result.requirements_python == ["foo"]
    assert result.requirements_bin == ["git"]


def test_base_images_sends_expected_params_and_parses_results():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/images/base-images"
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "tag": "19.0-enterprise",
                        "digest": "sha256:abc",
                        "version": "19.0",
                        "edition": "enterprise",
                    }
                ],
                "total": 1,
                "limit": 100,
                "offset": 0,
                "sort": None,
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    images = client.base_images(version="19.0", edition="enterprise")

    assert captured["params"] == {
        "version": "19.0",
        "edition": "enterprise",
        "limit": "100",
    }
    assert len(images) == 1
    assert images[0].tag == "19.0-enterprise"
    assert images[0].digest == "sha256:abc"
    assert images[0].version == "19.0"
    assert images[0].edition == "enterprise"
