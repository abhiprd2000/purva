from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Document:
    url: str
    text: str
    meta: dict = field(default_factory=dict)


class Collector(ABC):
    name: str = "base"

    @abstractmethod
    def iter_documents(self) -> Iterator[Document]:
        raise NotImplementedError