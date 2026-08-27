# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-08-27

### Added

- `GithubClient.get_blob_content` — raw bytes of a file via the REST
  Contents API, for binary content (icons, images) that GraphQL's
  `Blob.text` can't return

## [0.7.0] - 2026-08-27

### Changed

- `GithubClient.list_tree` now returns `list[TreeEntry]` (`path`, `type`,
  `mode`) instead of `list[str]` of blob paths — callers can now
  distinguish a symlink (`mode == "120000"`) or a git submodule
  (`type == "commit"`) from a real file, instead of both being silently
  filtered out

## [0.5.0] - 2026-08-27

### Added

- `GithubConfig` accepts GitHub App credentials (`app_id`, `installation_id`,
  `private_key`) as an alternative to a PAT `token`; `from_env()` prefers
  App env vars (`GITHUB_APP_ID`/`GITHUB_APP_INSTALLATION_ID`/
  `GITHUB_APP_PRIVATE_KEY`) when present, falling back to `GITHUB_TOKEN`,
  and raises clearly on a partial App config or on neither being set
- `GithubAppAuth` — `httpx.Auth` implementation that signs RS256 JWTs and
  exchanges them for GitHub App installation access tokens, caching and
  proactively refreshing before expiry (and reactively on a 401)
- `GithubClient` transparently uses `GithubAppAuth` when `GithubConfig` is
  built with App credentials instead of a token

## [0.4.1] - 2026-08-26

### Added

- `GithubClient.last_rate_limit` — GitHub's `x-ratelimit-*` response headers
  from the most recent `graphql()` call, so callers sweeping many repos can
  observe real rate-limit consumption instead of guessing a budget upfront

## [0.4.0] - 2026-08-26

### Added

- `GithubClient.graphql` — raw GraphQL call, raising on both HTTP errors and a
  non-empty top-level `errors` array
- `GithubClient.sweep_branch_heads` — branch name -> head oid per repo, via
  aliased/batched GraphQL, with per-repo pagination for repos with >100
  branches
- `GithubClient.list_tree` — flattened recursive tree listing via REST Git
  Trees; raises `TreeTruncatedError` if GitHub truncates the response
- `GithubClient.compare` — changed file paths between two refs, reporting
  truncation via `CompareResult.truncated`
- `GithubClient.get_blobs_text` — batched blob text fetch via aliased
  GraphQL, mapping an unresolvable path to `None` instead of raising
- `GithubClient.list_org_repos` — paginated REST listing of every repo in an
  org
- `GithubClient(config, repo=...)` — `repo` is now optional; the new
  operations above take `repo` per call instead of being bound to one repo

## [0.3.1] - 2026-08-18

### Fixed

- `MonitoringClient.fetch_statuses()` no longer loops forever against a Gatus deployment that
  ignores the `page` query param and always returns the full endpoint list

## [0.3.0] - 2026-08-17

### Added

- `MonitoringClient` for Gatus-backed monitoring access, authenticating via HTTP Basic

## [0.2.0] - 2026-08-17

### Added

- `DatahubClient.list_items` accepts an optional `fields` param, passed
  through to Directus for eager-loading relations
- `DatahubClient.delete_item` (and `DatahubClientProtocol`)

## [0.1.0] - 2026-08-17

### Added

- Shared `TransportConfig` and `build_client` helper (`relay.core`) providing a common `httpx`-based transport with retry/backoff for all clients
- `GithubClient` for GitHub API access
- `DatahubClient` for DataHub (Directus) access, including report and repository helpers
- `NotifyClient` for sending notifications
- `BucketManagerClient` for bucket management operations
- `relay.logging` — stdlib-only JSON log formatter helper for consuming services
