# datahub/model.py
from typing import ClassVar, Protocol, TypeVar


class Model(Protocol):
    collection: ClassVar[str]

    def to_item(self) -> dict: ...
    @classmethod
    def from_item(cls, data: dict) -> "Model": ...


T = TypeVar("T", bound=Model)
