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
