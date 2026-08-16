import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from ..core.models import Status
from .client import DatahubClient
from .repository import Repository


@dataclass(frozen=True, slots=True)
class Report:
    collection: ClassVar[str] = "reports"

    title: str
    source: str
    content: str
    id: int | None = None
    status: Status | str = Status.INFO
    summary: str | None = None
    job: str | None = None
    duration: float | None = None
    tags: tuple[str, ...] = ()

    def to_item(self) -> dict:
        # ID deliberately excluded: Directus assigns it (create) or it is included in the URL (update)
        item = {
            "title": self.title,
            "source": self.source,
            "content": self.content,
            "status": self.status,
        }
        if self.summary is not None:
            item["summary"] = self.summary
        if self.job is not None:
            item["job"] = self.job
        if self.duration is not None:
            item["duration"] = self.duration
        if self.tags:
            item["tags"] = list(self.tags)
        return item

    @classmethod
    def from_item(cls, data: dict) -> "Report":
        fields = {f.name for f in dataclasses.fields(cls)}
        kwargs = {
            k: v for k, v in data.items() if k in fields
        }  # ignore id_seq, date_created, user_*, etc.
        if kwargs.get("tags") is not None:
            kwargs["tags"] = tuple(kwargs["tags"])
        return cls(**kwargs)


def create_report(client: DatahubClient, report: Report) -> dict:
    reports = Repository(client, Report)
    return reports.create(report)
