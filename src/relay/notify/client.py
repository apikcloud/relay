import logging

import httpx

from ..core.models import Status
from ..core.transport import build_client
from .config import NotifyConfig

logger = logging.getLogger(__name__)

# The gateway's form validation rejects a longer body outright ("Bad FORM
# Payload provided"), before Apprise's own overflow handling could apply.
MAX_BODY_LEN = 32768


def _check_body(body: str) -> None:
    if len(body) > MAX_BODY_LEN:
        raise ValueError(
            f"Notification body is {len(body)} chars, over the gateway's"
            f" {MAX_BODY_LEN} limit; send the full content as an attachment"
        )


def _failure_detail(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.text
    return ""


class NotifyClient:
    """Talks to the shared `notify-gateway` (an Apprise API instance).

    `config.base_url` is the full notify endpoint for our config key, e.g.
    ``http://notify-gateway.notifications.svc.cluster.local:8000/notify/internal``.
    If `config` is None, every call is a no-op — same "optional notifier"
    behavior as before.
    """

    def __init__(self, config: NotifyConfig | None = None) -> None:
        self._config = config
        self._client = (
            build_client(
                transport=config.transport,
                headers={"Authorization": f"Bearer {config.token}"}
                if config.token
                else {},
            )
            if config
            else None
        )

    @classmethod
    def from_env(cls, prefix: str = "NOTIFY_") -> "NotifyClient":
        try:
            config = NotifyConfig.from_env(prefix=prefix)
        except Exception as err:
            logger.error(str(err))
            config = None
        return cls(config)

    @property
    def is_active(self) -> bool:
        return bool(self._client)

    def notify(
        self,
        title: str,
        body: str,
        tag: list[str] | None = None,
        notify_type: Status = Status.INFO,
        body_format: str | None = None,
    ) -> None:
        _check_body(body)
        if not self.is_active:
            return

        if tag is None:
            tag = self._config.jobs_tag

        payload = {
            "title": title,
            "body": body,
            "tag": tag,
            "type": Status(notify_type).value,
        }
        if body_format:
            payload["format"] = body_format

        try:
            response = self._client.post(self._config.base_url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Notification failed: %s %s", exc, _failure_detail(exc))

    def info(
        self,
        title: str,
        body: str,
        tag: list[str] | None = None,
    ) -> None:
        return self.notify(
            title=title,
            body=body,
            notify_type=Status.INFO,
            tag=tag,
        )

    def success(
        self,
        title: str,
        body: str,
        tag: list[str] | None = None,
    ) -> None:
        return self.notify(
            title=title,
            body=body,
            notify_type=Status.SUCCESS,
            tag=tag,
        )

    def warning(
        self,
        title: str,
        body: str,
        tag: list[str] | None = None,
    ) -> None:
        return self.notify(
            title=title,
            body=body,
            notify_type=Status.WARNING,
            tag=tag,
        )

    def failure(
        self,
        title: str,
        body: str,
        tag: list[str] | None = None,
    ) -> None:
        return self.notify(
            title=title,
            body=body,
            notify_type=Status.FAILURE,
            tag=tag,
        )

    def notify_with_attachment(
        self,
        title: str,
        body: str,
        content: str | bytes,
        content_type: str = "text/markdown",
        notify_type: Status = Status.INFO,
        filename: str = "attachment",
        tag: list[str] | None = None,
        body_format: str = "markdown",
    ) -> None:
        _check_body(body)
        if not self.is_active:
            return

        if tag is None:
            tag = self._config.reports_tag

        # Form fields are sent as str(value): a Status member would go out as
        # "Status.WARNING", which Apprise rejects ("Invalid FORM Payload").
        data = {
            "title": title,
            "body": body,
            "tag": ",".join(tag),
            "type": Status(notify_type).value,
        }
        if body_format:
            data["format"] = body_format

        try:
            response = self._client.post(
                self._config.base_url,
                data=data,
                files={"attach": (filename, content, content_type)},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "Notification with attachment failed: %s %s",
                exc,
                _failure_detail(exc),
            )
