from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        pages = max(1, (total + page_size - 1) // page_size) if page_size else 1
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: str | None = None


class MessageResponse(BaseModel):
    message: str


class HealthStatus(BaseModel):
    status: str
    app: str
    version: str
    database: str
    redis: str
