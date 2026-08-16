# Relay

Lightweight, shared clients for internal services (github, datahub, notify),
built on a common httpx transport (timeout, `max_retries`, 429 `Retry-After`
backoff) living in `conduit.core`.

## Install

Pinned tag over Git SSH:

    uv add "conduit @ git+ssh://git@github.com/apikcloud/relay.git@v0.1.0"

Pull only what a service needs via extras:

    uv add "conduit[github] @ git+ssh://git@github.com/apikcloud/relay.git@v0.1.0"

`notify` and `core` need no extra — httpx only.

## Usage

    from relay.notify import notify
    from relay.github import GitHubClient

Each client composes its own config around `conduit.core.config.TransportConfig`.
