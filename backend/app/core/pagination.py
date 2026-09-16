"""Offset pagination shared by every collection endpoint."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class PageParams(BaseModel):
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(default=0, ge=0)


def page_params(
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum items to return.")
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Items to skip.")] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


class Page[T](BaseModel):
    """A single page of results plus the total number of matching rows."""

    items: list[T]
    total: int
    limit: int
    offset: int
