# cartographer/client.py
from dataclasses import dataclass
from typing import Any

from ..core.transport import build_client
from .config import CartographerConfig


@dataclass(slots=True)
class ModuleVersion:
    branch: str
    depends: list[str]
    installable: bool | None
    application: bool | None


@dataclass(slots=True)
class Module:
    repo: str
    kind: str
    module_name: str
    depends: list[str]
    versions: list[ModuleVersion]


@dataclass(slots=True)
class CustomModule:
    module_name: str
    submodule_repo: str | None
    submodule_path: str | None
    submodule_branch: str | None


@dataclass(slots=True)
class CustomRepoRef:
    ref: str
    ref_kind: str
    odoo_version_raw: str | None
    requirements_python: list[str]
    requirements_bin: list[str]
    modules: list[CustomModule]


@dataclass(slots=True)
class CustomRepo:
    repo: str
    repo_url: str
    refs: list[CustomRepoRef]


@dataclass(slots=True)
class ExpandResult:
    modules: list[dict[str, str]]  # {repo, module_name, kind}
    ambiguous: list[dict[str, Any]]
    unavailable: list[dict[str, Any]]
    warnings: list[str]
    requirements_python: list[str]
    requirements_bin: list[str]


@dataclass(slots=True)
class BaseImageTag:
    tag: str
    digest: str | None
    version: str | None
    edition: str | None


@dataclass(slots=True)
class ResolveCandidate:
    repo: str
    kind: str


@dataclass(slots=True)
class ResolveResult:
    module_name: str
    series: str
    candidates: list[ResolveCandidate]
    preferred: ResolveCandidate | None


@dataclass(slots=True)
class AvailableModule:
    module_name: str
    repo: str
    kind: str
    name: str | None
    summary: str | None
    license: str | None
    depends: list[str] | None


@dataclass(slots=True)
class HostedByCandidate:
    repo: str
    kind: str
    is_preferred: bool


@dataclass(slots=True)
class DependsSource:
    kind: str
    repo: str | None
    ref: str | None
    sha: str | None


@dataclass(slots=True)
class CustomRefModule:
    """One module a custom repo carries at one ref. `origin` is `"flat"`
    (the repo holds the source itself) or `"symlink"` (a root symlink
    activates a vendored `.gitmodules` submodule — `submodule_*` are that
    pointer). When `depends` was requested, a symlinked module's `depends`
    is followed through to wherever it really lives (its own row stores an
    empty manifest) and `depends_source` names which tier answered."""

    module_name: str
    origin: str
    sha: str
    name: str | None
    summary: str | None
    license: str | None
    odoo_major_version: str | None
    version_flag: str
    submodule_repo: str | None
    submodule_sha: str | None
    submodule_path: str | None
    submodule_branch: str | None
    hosted_by: list[HostedByCandidate]
    depends: list[str] | None
    depends_source: DependsSource | None


@dataclass(slots=True)
class CustomRefModules:
    repo: str
    repo_url: str
    ref: str
    ref_kind: str
    odoo_version_raw: str | None
    odoo_major_version: str | None
    release: str | None
    edition: str | None
    requirements_python: list[str]
    requirements_bin: list[str]
    count: int
    results: list[CustomRefModule]


class CartographerClient:
    """Reads Cartographer's catalog — module discovery, classification,
    dependencies for client/custom repos, and Odoo base-image tags.
    Read-only, no write endpoints exist on Cartographer's API today, and
    it requires no auth (see cartographer's own `k8s/ingress.yaml`)."""

    def __init__(self, config: CartographerConfig | None = None) -> None:
        self._config = config or CartographerConfig.from_env()
        self._client = build_client(
            base_url=self._config.base_url, transport=self._config.transport
        )

    def custom_repo_detail(self, repo: str) -> CustomRepo:
        resp = self._client.get(f"/v1/code/custom/{repo}")
        resp.raise_for_status()
        body = resp.json()
        return CustomRepo(
            repo=body["repo"],
            repo_url=body["repo_url"],
            refs=[
                CustomRepoRef(
                    ref=r["ref"],
                    ref_kind=r["ref_kind"],
                    odoo_version_raw=r["odoo_version_raw"],
                    requirements_python=r["requirements_python"],
                    requirements_bin=r["requirements_bin"],
                    modules=[
                        CustomModule(
                            module_name=m["module_name"],
                            submodule_repo=m["submodule_repo"],
                            submodule_path=m["submodule_path"],
                            submodule_branch=m["submodule_branch"],
                        )
                        for m in r["modules"]
                    ],
                )
                for r in body["refs"]
            ],
        )

    def module_detail(self, repo: str, module_name: str) -> Module:
        resp = self._client.get(f"/v1/code/modules/{repo}/{module_name}")
        resp.raise_for_status()
        body = resp.json()
        return Module(
            repo=body["repo"],
            kind=body["kind"],
            module_name=body["module_name"],
            depends=body["depends"],
            versions=[
                ModuleVersion(
                    branch=v["branch"],
                    depends=v["depends"],
                    installable=v["installable"],
                    application=v["application"],
                )
                for v in body["versions"]
            ],
        )

    def live_refs(self, repo: str) -> dict[str, dict[str, str]]:
        """Uncached GitHub passthrough: {"branches": {name: sha}, "tags": {name: sha}}."""
        resp = self._client.get(f"/v1/code/custom/{repo}/refs")
        resp.raise_for_status()
        return resp.json()

    def custom_modules(
        self, repo: str, ref: str, include_dependencies: bool = False
    ) -> CustomRefModules:
        """Every module `repo` carries at `ref`, with symlinked/submodule
        entries already resolved to their real provider's `depends` when
        `include_dependencies` is true — no need to separately walk
        `.gitmodules`/`hosted_by` or fall back to `module_detail` per name,
        which returns an empty stub for a symlinked entry Cartographer
        hasn't crawled as a first-class provider (e.g. an unlisted OCA
        repo). `odoo_major_version`/`release`/`edition` are parsed out of
        this ref's `odoo_version.txt` content (itself a DockerHub image
        reference) — no need to parse it client-side either."""
        resp = self._client.get(
            f"/v1/code/custom/{repo}/modules",
            params={"ref": ref, "include_dependencies": include_dependencies},
        )
        resp.raise_for_status()
        body = resp.json()
        return CustomRefModules(
            repo=body["repo"],
            repo_url=body["repo_url"],
            ref=body["ref"],
            ref_kind=body["ref_kind"],
            odoo_version_raw=body["odoo_version_raw"],
            odoo_major_version=body["odoo_major_version"],
            release=body["release"],
            edition=body["edition"],
            requirements_python=body["requirements_python"],
            requirements_bin=body["requirements_bin"],
            count=body["count"],
            results=[
                CustomRefModule(
                    module_name=m["module_name"],
                    origin=m["origin"],
                    sha=m["sha"],
                    name=m["name"],
                    summary=m["summary"],
                    license=m["license"],
                    odoo_major_version=m["odoo_major_version"],
                    version_flag=m["version_flag"],
                    submodule_repo=m["submodule_repo"],
                    submodule_sha=m["submodule_sha"],
                    submodule_path=m["submodule_path"],
                    submodule_branch=m["submodule_branch"],
                    hosted_by=[
                        HostedByCandidate(
                            repo=h["repo"],
                            kind=h["kind"],
                            is_preferred=h["is_preferred"],
                        )
                        for h in m["hosted_by"]
                    ],
                    depends=m["depends"],
                    depends_source=(
                        DependsSource(
                            kind=m["depends_source"]["kind"],
                            repo=m["depends_source"]["repo"],
                            ref=m["depends_source"]["ref"],
                            sha=m["depends_source"]["sha"],
                        )
                        if m["depends_source"]
                        else None
                    ),
                )
                for m in body["results"]
            ],
        )

    def resolve(self, module_name: str, series: str) -> ResolveResult:
        """Every provider-kind repo (core/enterprise/oca/third_party) that hosts
        `module_name` at `series`, plus the same auto-pick `resolve_expand` uses
        internally. Used to find which repo a real dependency name resolves to,
        so its own `depends` can be fetched via `module_detail` — `resolve_expand`
        deliberately excludes core/enterprise from its output and never returns
        `depends` for anything, so it can't answer that question on its own."""
        resp = self._client.get(
            f"/v1/code/resolve/{module_name}", params={"series": series}
        )
        resp.raise_for_status()
        body = resp.json()
        candidates = [
            ResolveCandidate(repo=c["repo"], kind=c["kind"]) for c in body["candidates"]
        ]
        preferred = (
            ResolveCandidate(
                repo=body["preferred"]["repo"], kind=body["preferred"]["kind"]
            )
            if body.get("preferred")
            else None
        )
        return ResolveResult(
            module_name=body["module_name"],
            series=body["series"],
            candidates=candidates,
            preferred=preferred,
        )

    def available_modules(
        self,
        odoo_version: str,
        enterprise: bool = False,
        include_dependencies: bool = False,
    ) -> list[AvailableModule]:
        """Every standard-tree module Odoo `odoo_version` actually ships —
        `core` always, `enterprise` too when requested — in one unpaginated
        call (~650 rows core-only, ~1330 core+enterprise, at the busiest
        version). `depends` is that module's real manifest depends at this
        exact version when `include_dependencies` is true, else `None`."""
        resp = self._client.get(
            "/v1/code/modules/available",
            params={
                "odoo_version": odoo_version,
                "enterprise": enterprise,
                "include_dependencies": include_dependencies,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        return [
            AvailableModule(
                module_name=m["module_name"],
                repo=m["repo"],
                kind=m["kind"],
                name=m["name"],
                summary=m["summary"],
                license=m["license"],
                depends=m["depends"],
            )
            for m in body["results"]
        ]

    def resolve_expand(
        self, modules: list[tuple[str, str]], series: str, enterprise: bool = False
    ) -> ExpandResult:
        resp = self._client.post(
            "/v1/code/resolve/expand",
            json={
                "modules": [{"repo": r, "module_name": m} for r, m in modules],
                "series": series,
                "enterprise": enterprise,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        return ExpandResult(
            modules=body["modules"],
            ambiguous=body["ambiguous"],
            unavailable=body["unavailable"],
            warnings=body["warnings"],
            requirements_python=body["requirements_python"],
            requirements_bin=body["requirements_bin"],
        )

    def base_images(self, version: str, edition: str) -> list[BaseImageTag]:
        resp = self._client.get(
            "/v1/images/base-images",
            params={"version": version, "edition": edition, "limit": 100},
        )
        resp.raise_for_status()
        return [
            BaseImageTag(
                tag=t["tag"],
                digest=t["digest"],
                version=t["version"],
                edition=t["edition"],
            )
            for t in resp.json()["results"]
        ]
