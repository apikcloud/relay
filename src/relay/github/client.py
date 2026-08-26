# Copyright 2026 Apik (https://apik.cloud).
# License AGPL-3.0-only (https://www.gnu.org/licenses/agpl-3.0.html)
#
# File: client.py — github/client.py

"""GitHub REST + GraphQL client. Started as just enough to open/update a PR
carrying a suggested `projects.yaml` and comment on it (Contents API commits
files directly, no `git`/`gh` subprocess, no clone/checkout needed in the
pod); extended with read-oriented GraphQL/REST operations (branch-head
sweep, recursive tree listing, compare, batched blob text, org repo listing)
for callers that read across many repos rather than write to one."""

import base64
import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from ..core.transport import build_client
from .config import GithubConfig

_GRAPHQL_PATH = "/graphql"


class GraphQLError(Exception):
    """Raised when a GraphQL response carries a non-empty top-level `errors`."""


class TreeTruncatedError(Exception):
    """Raised when a recursive tree listing is truncated by GitHub — the
    caller must decide how to handle a partial tree rather than silently
    working with one."""

    def __init__(self, repo: str, sha: str) -> None:
        super().__init__(f"tree listing truncated for {repo}@{sha}")
        self.repo = repo
        self.sha = sha


@dataclass(slots=True)
class CompareResult:
    files: list[str]
    truncated: bool


def _chunk(items: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


class GithubClient:
    def __init__(self, config: GithubConfig, repo: str | None = None) -> None:
        self.repo = repo
        self._client = build_client(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            transport=config.transport,
        )
        # Rate-limit headers from the most recent GraphQL response — callers
        # that sweep many repos read this after each batch to observe real
        # consumption rather than guessing a request budget upfront.
        self.last_rate_limit: dict[str, str] = {}

    def get_ref_sha(self, branch: str) -> str:
        """SHA the tip of `branch` currently points at."""
        resp = self._client.get(f"/repos/{self.repo}/git/ref/heads/{branch}")
        resp.raise_for_status()
        return resp.json()["object"]["sha"]

    def branch_exists(self, branch: str) -> bool:
        resp = self._client.get(f"/repos/{self.repo}/git/ref/heads/{branch}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def create_branch(self, branch: str, from_sha: str) -> None:
        resp = self._client.post(
            f"/repos/{self.repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": from_sha},
        )
        resp.raise_for_status()

    def get_file(self, path: str, ref: str) -> str | None:
        """Blob SHA of `path` on `ref`, or None if it doesn't exist there yet."""
        resp = self._client.get(
            f"/repos/{self.repo}/contents/{path}", params={"ref": ref}
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()["sha"]

    def put_file(
        self, path: str, branch: str, content: str, message: str, sha: str | None
    ) -> None:
        """Create or update `path` on `branch` with `content` in one commit."""
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        resp = self._client.put(f"/repos/{self.repo}/contents/{path}", json=payload)
        resp.raise_for_status()

    def find_open_pr(self, head_branch: str) -> dict | None:
        owner = self.repo.split("/", 1)[0]
        resp = self._client.get(
            f"/repos/{self.repo}/pulls",
            params={"head": f"{owner}:{head_branch}", "state": "open"},
        )
        resp.raise_for_status()
        results = resp.json()
        return results[0] if results else None

    def create_pr(self, head: str, base: str, title: str, body: str) -> dict:
        resp = self._client.post(
            f"/repos/{self.repo}/pulls",
            json={"head": head, "base": base, "title": title, "body": body},
        )
        resp.raise_for_status()
        return resp.json()

    def create_pr_comment(self, pr_number: int, body: str) -> None:
        resp = self._client.post(
            f"/repos/{self.repo}/issues/{pr_number}/comments", json={"body": body}
        )
        resp.raise_for_status()

    # -- Read-oriented GraphQL/REST operations -----------------------------

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """POST `query` to GitHub's GraphQL endpoint, raising on both HTTP
        errors and a non-empty top-level `errors` array in the response."""
        resp = self._client.post(
            _GRAPHQL_PATH, json={"query": query, "variables": variables}
        )
        resp.raise_for_status()
        self.last_rate_limit = {
            k[len("x-ratelimit-") :]: v
            for k, v in resp.headers.items()
            if k.lower().startswith("x-ratelimit-")
        }
        body = resp.json()
        if body.get("errors"):
            raise GraphQLError(str(body["errors"]))
        return body["data"]

    def sweep_branch_heads(
        self, repos: list[str], batch_size: int = 40
    ) -> dict[str, dict[str, str]]:
        """Branch name -> head oid, per repo, via aliased GraphQL batches."""
        result: dict[str, dict[str, str]] = {}
        for batch in _chunk(repos, batch_size):
            result.update(self._sweep_batch(batch))
        return result

    def _sweep_batch(self, repos: list[str]) -> dict[str, dict[str, str]]:
        aliases = {f"r{i}": repo for i, repo in enumerate(repos)}
        fields = "\n".join(
            f'{alias}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) '
            '{ refs(refPrefix: "refs/heads/", first: 100) '
            "{ nodes { name target { oid } } pageInfo { hasNextPage endCursor } } }"
            for alias, (owner, name) in (
                (alias, repo.split("/", 1)) for alias, repo in aliases.items()
            )
        )
        data = self.graphql(f"query {{ {fields} }}", {})

        out: dict[str, dict[str, str]] = {}
        pending: list[tuple[str, str]] = []
        for alias, repo in aliases.items():
            node = data.get(alias)
            if node is None:
                out[repo] = {}
                continue
            refs = node["refs"]
            out[repo] = {n["name"]: n["target"]["oid"] for n in refs["nodes"]}
            if refs["pageInfo"]["hasNextPage"]:
                pending.append((repo, refs["pageInfo"]["endCursor"]))

        for repo, cursor in pending:
            out[repo].update(self._sweep_paginate(repo, cursor))
        return out

    def _sweep_paginate(self, repo: str, cursor: str) -> dict[str, str]:
        owner, name = repo.split("/", 1)
        query = (
            "query($owner: String!, $name: String!, $cursor: String) "
            "{ repository(owner: $owner, name: $name) "
            '{ refs(refPrefix: "refs/heads/", first: 100, after: $cursor) '
            "{ nodes { name target { oid } } pageInfo { hasNextPage endCursor } } } }"
        )
        heads: dict[str, str] = {}
        next_cursor: str | None = cursor
        while next_cursor is not None:
            data = self.graphql(
                query, {"owner": owner, "name": name, "cursor": next_cursor}
            )
            refs = data["repository"]["refs"]
            heads.update({n["name"]: n["target"]["oid"] for n in refs["nodes"]})
            next_cursor = (
                refs["pageInfo"]["endCursor"] if refs["pageInfo"]["hasNextPage"] else None
            )
        return heads

    def list_tree(self, repo: str, sha: str) -> list[str]:
        """Flattened blob paths of the full tree at `sha`, one REST call.

        Raises `TreeTruncatedError` if GitHub truncates the listing —
        callers must decide how to handle a partial tree explicitly."""
        resp = self._client.get(
            f"/repos/{repo}/git/trees/{sha}", params={"recursive": "1"}
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("truncated"):
            raise TreeTruncatedError(repo, sha)
        return [entry["path"] for entry in body["tree"] if entry["type"] == "blob"]

    def compare(self, repo: str, base: str, head: str) -> CompareResult:
        """Changed file paths between `base` and `head`.

        `truncated=True` mirrors GitHub's own truncation signal for this
        endpoint: the `files` list is capped (~300 entries) and, past that
        cap, may be omitted entirely rather than returned partial — either
        case is reported here so callers fall back to a full re-listing."""
        resp = self._client.get(f"/repos/{repo}/compare/{base}...{head}")
        resp.raise_for_status()
        body = resp.json()
        raw_files = body.get("files")
        files = [f["filename"] for f in raw_files] if raw_files is not None else []
        truncated = raw_files is None or len(raw_files) >= 300
        return CompareResult(files=files, truncated=truncated)

    def get_blobs_text(
        self, repo: str, ref: str, paths: list[str], batch_size: int = 40
    ) -> dict[str, str | None]:
        """Blob text at `ref` for each of `paths`, batched via aliased
        GraphQL. A path that doesn't resolve (deleted/renamed between
        listing and fetch) maps to `None` rather than raising — an expected
        race in an incremental crawl, not an error."""
        owner, name = repo.split("/", 1)
        result: dict[str, str | None] = {}
        for batch in _chunk(paths, batch_size):
            aliases = {f"b{i}": path for i, path in enumerate(batch)}
            fields = "\n".join(
                f"{alias}: object(expression: {json.dumps(f'{ref}:{path}')}) "
                "{ ... on Blob { text } }"
                for alias, path in aliases.items()
            )
            data = self.graphql(
                f"query {{ repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
                f"{{ {fields} }} }}",
                {},
            )
            repo_data = data["repository"]
            for alias, path in aliases.items():
                node = repo_data.get(alias)
                result[path] = node["text"] if node else None
        return result

    def list_org_repos(self, org: str) -> list[str]:
        """Full names (`owner/repo`) of every repo in `org`, REST-paginated."""
        full_names: list[str] = []
        page = 1
        while True:
            resp = self._client.get(
                f"/orgs/{org}/repos", params={"per_page": 100, "page": page}
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            full_names.extend(r["full_name"] for r in batch)
            page += 1
        return full_names
