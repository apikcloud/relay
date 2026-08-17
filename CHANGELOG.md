# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-17

### Added

- Shared `TransportConfig` and `build_client` helper (`relay.core`) providing a common `httpx`-based transport with retry/backoff for all clients
- `GithubClient` for GitHub API access
- `DatahubClient` for DataHub (Directus) access, including report and repository helpers
- `NotifyClient` for sending notifications
- `BucketManagerClient` for bucket management operations
- `relay.logging` — stdlib-only JSON log formatter helper for consuming services
