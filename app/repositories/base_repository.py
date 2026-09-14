from __future__ import annotations

from typing import Generic, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository. Keeps raw database access out of services."""

    model: Type[ModelT]

    def __init__(self, session: Session):
        self.session = session

    def get(self, id_: int) -> ModelT | None:
        return self.session.get(self.model, id_)

    def list(self, limit: int = 200, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        return instance

    def delete(self, instance: ModelT) -> None:
        self.session.delete(instance)
        self.session.flush()
