# Datahub Client

## Usage

Define model (frozen dataclass, must satisfy `Model` protocol: `collection`,
`to_item()`, `from_item()`), then bind it to `Repository`.

```python
import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from relay.datahub.client import DatahubClient
from relay.datahub.config import DatahubConfig
from relay.datahub.repository import Repository


@dataclass(frozen=True, slots=True)
class Incident:
    collection: ClassVar[str] = "incidents"

    title: str
    id: int | None = None
    resolved: bool = False

    def to_item(self) -> dict:
        # id excluded: Directus assigns it (create) or it's in the URL (update)
        return {"title": self.title, "resolved": self.resolved}

    @classmethod
    def from_item(cls, data: dict) -> "Incident":
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in fields})


client = DatahubClient(DatahubConfig.from_env())
incidents = Repository(client, Incident)

created = incidents.create(Incident(title="API down"))
# created.id set from Directus response

open_ = incidents.list({"resolved": {"_eq": False}})  # list[Incident]

# immutable update: derive a copy with dataclasses.replace, id is kept
incidents.update(dataclasses.replace(created, resolved=True))
```
