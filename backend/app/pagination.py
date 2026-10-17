"""List responses: {items, page, page_size, total?}. Default 20, maximum 100."""

from dataclasses import dataclass

from fastapi import Query
from pydantic import BaseModel


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def last_index(self) -> int:
        """Inclusive end index for Supabase `.range(offset, last_index)`."""
        return self.offset + self.page_size - 1


def page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int | None = None
