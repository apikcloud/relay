# Copyright 2026 Apik (https://apik.cloud).
# License AGPL-3.0-only (https://www.gnu.org/licenses/agpl-3.0.html)
#
# File: client.py — github/client.py

"""Minimal GitHub REST API client — just enough to open/update a PR carrying
a suggested `projects.yaml` and comment on it. No `git`/`gh` subprocess: the
Contents API commits files directly via the REST API, so no clone/checkout
is needed in the pod."""

import base64

from ..core.transport import build_client
from .config import GithubConfig


class GithubClient:
    def __init__(self, config: GithubConfig, repo: str) -> None:
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
