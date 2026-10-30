# Relay

Lightweight, shared clients for internal services (github, datahub, notify,
bucket_manager, monitoring), built on a common httpx transport (timeout, `max_retries`,
429 `Retry-After` backoff) living in `relay.core`.

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
    from relay.monitoring.client import MonitoringClient

    notifier = NotifyClient.from_env()
    notifier.failure(title="job", body="something broke")

Each client composes its own config around `relay.core.config.TransportConfig`,
and exposes a `from_env()` constructor plus an `is_active` property (a missing
or invalid env config yields an inactive, no-op instance instead of raising).

### HTML emails

`relay.notify.html` (needs the `notify` extra, which brings `markdown`) gives
every mailing the same layout: a pale grey page with a white content area
(90% of the width, at most 1000px), styled inline for email clients.

    from relay.notify.html import markdown_to_html

    body = markdown_to_html("# Report\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n",
                            title="Report", footer="Sent by my-job")
    notifier.notify_with_attachment(title="Report", body=body, body_format="html", ...)

`render_email(html)` wraps HTML you built yourself in the same layout. Colors
and widths are module constants (`PAGE_BACKGROUND`, `CONTENT_WIDTH`, …).
