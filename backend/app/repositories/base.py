from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)


@dataclass
class PageParams:
    limit: int = 50
    offset: int = 0

    def clamp(self, *, max_limit: int = 500) -> PageParams:
        return PageParams(
            limit=min(max_limit, max(1, self.limit)),
            offset=max(0, self.offset),
        )


@dataclass
class SortParams:
    field: str = "timestamp"
    direction: str = "desc"  # asc | desc


@dataclass
class TimeRange:
    since: datetime | None = None
    until: datetime | None = None


@dataclass
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


@dataclass
class FilterSpec:
    """Generic equality / in / ilike filters applied by repositories."""

    equals: dict[str, Any] = field(default_factory=dict)
    any_of: dict[str, list[Any]] = field(default_factory=dict)
    ilike: dict[str, str] = field(default_factory=dict)
    time_field: str | None = "timestamp"
    time_range: TimeRange | None = None


class Repository(Generic[T]):
    """Base repository — all SQL stays here, never in route handlers or React."""

    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: Any) -> T | None:
        return await self.session.get(self.model, id_)

    async def add(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    def _apply_filters(self, stmt: Select[Any], filters: FilterSpec | None) -> Select[Any]:
        if not filters:
            return stmt
        model = self.model
        for col_name, value in filters.equals.items():
            if value is None:
                continue
            col = getattr(model, col_name, None)
            if col is not None:
                stmt = stmt.where(col == value)
        for col_name, values in filters.any_of.items():
            if not values:
                continue
            col = getattr(model, col_name, None)
            if col is not None:
                stmt = stmt.where(col.in_(values))
        for col_name, pattern in filters.ilike.items():
            if not pattern:
                continue
            col = getattr(model, col_name, None)
            if col is not None:
                stmt = stmt.where(col.ilike(f"%{pattern}%"))
        if filters.time_field and filters.time_range:
            col = getattr(model, filters.time_field, None)
            if col is not None:
                if filters.time_range.since is not None:
                    stmt = stmt.where(col >= filters.time_range.since)
                if filters.time_range.until is not None:
                    stmt = stmt.where(col <= filters.time_range.until)
        return stmt

    def _apply_sort(self, stmt: Select[Any], sort: SortParams | None, default_field: str) -> Select[Any]:
        field_name = (sort.field if sort else default_field) or default_field
        col = getattr(self.model, field_name, None) or getattr(self.model, default_field, None)
        if col is None:
            return stmt
        direction = (sort.direction if sort else "desc").lower()
        return stmt.order_by(asc(col) if direction == "asc" else desc(col))

    async def paginate(
        self,
        *,
        filters: FilterSpec | None = None,
        sort: SortParams | None = None,
        page: PageParams | None = None,
        default_sort_field: str = "timestamp",
    ) -> Page[T]:
        page = (page or PageParams()).clamp()
        base = select(self.model)
        base = self._apply_filters(base, filters)

        total = int(
            (
                await self.session.execute(select(func.count()).select_from(base.subquery()))
            ).scalar_one()
        )

        stmt = self._apply_sort(base, sort, default_sort_field)
        stmt = stmt.offset(page.offset).limit(page.limit)
        items = list((await self.session.execute(stmt)).scalars().all())
        return Page(items=items, total=total, limit=page.limit, offset=page.offset)
