# datahub/repository.py
from __future__ import annotations

from .client import DatahubClientProtocol
from .model import T


class Repository[T]:
    """Binds a Model to the generic Datahub client. The model owns
    serialization; this only scopes the 3 ops to `model.collection`."""

    def __init__(self, client: DatahubClientProtocol, model: type[T]) -> None:
        self._client = client
        self._model = model
        self._collection = model.collection

    def create(self, obj: T) -> T:
        data = self._client.create_item(self._collection, obj.to_item())
        # Some Directus instances/configs respond 204 (no body) on create.
        return self._model.from_item(data) if data else obj

    def update(self, obj: T) -> T:
        if obj.id is None:
            raise ValueError("cannot update an object without an id")
        data = self._client.update_item(self._collection, obj.id, obj.to_item())
        return self._model.from_item(data) if data else obj

    def list(self, filter_: dict | None = None, limit: int = -1) -> list[T]:
        data = self._client.list_items(self._collection, filter_ or {}, limit)
        return [self._model.from_item(d) for d in data]
