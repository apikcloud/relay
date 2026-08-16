# Relay

Lightweight, shared clients for internal services (github, datahub, notify,
bucket_manager), built on a common httpx transport (timeout, `max_retries`, 429
`Retry-After` backoff) living in `relay.core`.

## Install

Pinned commit over Git SSH:

    uv add "relay @ git+ssh://git@github.com/apikcloud/relay.git@<commit-sha>"

Pull only what a service needs via extras:

    uv add "relay[github] @ git+ssh://git@github.com/apikcloud/relay.git@<commit-sha>"

`core` needs no extra — httpx only.

## Usage

    from relay.notify.client import NotifyClient
    from relay.github.client import GithubClient
    from relay.bucket_manager.client import BucketManager
    from relay.datahub.client import DatahubClient

    notifier = NotifyClient.from_env()
    notifier.failure(title="job", body="something broke")

Each client composes its own config around `relay.core.config.TransportConfig`,
and exposes a `from_env()` constructor plus an `is_active` property (a missing
or invalid env config yields an inactive, no-op instance instead of raising).
