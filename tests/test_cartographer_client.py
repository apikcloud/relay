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


def test_resolve_sends_series_param_and_parses_preferred():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/code/resolve/sale"
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "module_name": "sale",
                "series": "19.0",
                "candidates": [{"repo": "odoo/odoo", "kind": "core"}],
                "preferred": {"repo": "odoo/odoo", "kind": "core"},
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.resolve("sale", series="19.0")

    assert captured["params"] == {"series": "19.0"}
    assert result.module_name == "sale"
    assert result.series == "19.0"
    assert len(result.candidates) == 1
    assert result.candidates[0].repo == "odoo/odoo"
    assert result.candidates[0].kind == "core"
    assert result.preferred is not None
    assert result.preferred.repo == "odoo/odoo"
    assert result.preferred.kind == "core"


def test_resolve_returns_none_preferred_when_ambiguous():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "module_name": "some_module",
                "series": "19.0",
                "candidates": [
                    {"repo": "oca/repo-a", "kind": "oca"},
                    {"repo": "oca/repo-b", "kind": "oca"},
                ],
                "preferred": None,
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.resolve("some_module", series="19.0")

    assert result.preferred is None
    assert len(result.candidates) == 2


def test_available_modules_sends_expected_params_and_parses_results():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/code/modules/available"
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "odoo_version": "18.0",
                "enterprise": True,
                "count": 1,
                "results": [
                    {
                        "module_name": "account",
                        "repo": "odoo/odoo",
                        "kind": "core",
                        "name": "Invoicing",
                        "summary": "Invoices, Payments, Follow-ups & Bank Synchronization",
                        "license": "LGPL-3",
                        "depends": ["base_setup", "onboarding", "product", "analytic"],
                    }
                ],
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    results = client.available_modules(
        "18.0", enterprise=True, include_dependencies=True
    )

    assert captured["params"] == {
        "odoo_version": "18.0",
        "enterprise": "true",
        "include_dependencies": "true",
    }
    assert len(results) == 1
    assert results[0].module_name == "account"
    assert results[0].repo == "odoo/odoo"
    assert results[0].kind == "core"
    assert results[0].depends == ["base_setup", "onboarding", "product", "analytic"]


def test_available_modules_depends_none_when_not_requested():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "odoo_version": "18.0",
                "enterprise": False,
                "count": 1,
                "results": [
                    {
                        "module_name": "base",
                        "repo": "odoo/odoo",
                        "kind": "core",
                        "name": "Base",
                        "summary": None,
                        "license": "LGPL-3",
                        "depends": None,
                    }
                ],
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    results = client.available_modules("18.0")

    assert results[0].depends is None


def test_custom_modules_sends_expected_params_and_parses_symlink_entry():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/code/custom/apik/client-repo/modules"
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "repo": "apik/client-repo",
                "repo_url": "https://github.com/apik/client-repo",
                "ref": "v1.2.92",
                "ref_kind": "tag",
                "odoo_version_raw": "ofleet/odoo:13-20230607-enterprise",
                "odoo_major_version": "13.0",
                "release": "20230607",
                "edition": "enterprise",
                "requirements_python": ["ofxparse"],
                "requirements_bin": [],
                "count": 1,
                "results": [
                    {
                        "module_name": "account_bank_statement_import_ofx",
                        "origin": "symlink",
                        "sha": "deadbeef",
                        "name": None,
                        "summary": None,
                        "license": None,
                        "odoo_major_version": None,
                        "version_flag": "unresolved",
                        "submodule_repo": "oca/bank-statement-import",
                        "submodule_sha": "cafebabe",
                        "submodule_path": "account_bank_statement_import_ofx",
                        "submodule_branch": "13.0",
                        "hosted_by": [
                            {
                                "repo": "oca/bank-statement-import",
                                "kind": "unknown",
                                "is_preferred": True,
                            },
                            {
                                "repo": "odoo/enterprise",
                                "kind": "enterprise",
                                "is_preferred": False,
                            },
                        ],
                        "depends": ["account_bank_statement_import"],
                        "depends_source": {
                            "kind": "resolve_only_reference",
                            "repo": "oca/bank-statement-import",
                            "ref": "13.0",
                            "sha": "cafebabe",
                        },
                    }
                ],
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.custom_modules(
        "apik/client-repo", "v1.2.92", include_dependencies=True
    )

    assert captured["params"] == {"ref": "v1.2.92", "include_dependencies": "true"}
    assert result.repo == "apik/client-repo"
    assert result.odoo_major_version == "13.0"
    assert result.edition == "enterprise"
    assert result.count == 1
    module = result.results[0]
    assert module.origin == "symlink"
    assert module.depends == ["account_bank_statement_import"]
    assert module.depends_source is not None
    assert module.depends_source.kind == "resolve_only_reference"
    assert len(module.hosted_by) == 2
    preferred = next(h for h in module.hosted_by if h.is_preferred)
    assert preferred.repo == "oca/bank-statement-import"
    assert preferred.kind == "unknown"


def test_custom_modules_flat_origin_has_no_depends_source_when_not_requested():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "repo": "apik/client-repo",
                "repo_url": "https://github.com/apik/client-repo",
                "ref": "main",
                "ref_kind": "branch",
                "odoo_version_raw": None,
                "odoo_major_version": None,
                "release": None,
                "edition": None,
                "requirements_python": [],
                "requirements_bin": [],
                "count": 1,
                "results": [
                    {
                        "module_name": "my_module",
                        "origin": "flat",
                        "sha": "deadbeef",
                        "name": "My Module",
                        "summary": None,
                        "license": "AGPL-3",
                        "odoo_major_version": "19.0",
                        "version_flag": "declared_unverified",
                        "submodule_repo": None,
                        "submodule_sha": None,
                        "submodule_path": None,
                        "submodule_branch": None,
                        "hosted_by": [],
                        "depends": None,
                        "depends_source": None,
                    }
                ],
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    result = client.custom_modules("apik/client-repo", "main")

    module = result.results[0]
    assert module.origin == "flat"
    assert module.hosted_by == []
    assert module.depends is None
    assert module.depends_source is None


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
