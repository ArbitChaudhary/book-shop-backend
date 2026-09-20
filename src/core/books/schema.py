import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BookCreate(BaseModel):
    merchant_id: uuid.UUID
    title: str
    slug: str
    description: str
    isbn_10: str | None = None
    isbn_13: str | None = None
    author: str
    publisher: str | None = None
    publication_date: str | None = None
    language: str
    page_count: int | None = None
    media: list[str] = Field(..., min_length=1)
    categories: list[str] = Field(..., min_length=1)
    price: float
    status: str
    stock: int


class BookUpdate(BaseModel):
    title: str | None = None
    slug: str | None = None
    description: str | None = None
    isbn_10: str | None = None
    isbn_13: str | None = None
    author: str | None = None
    publisher: str | None = None
    publication_date: str | None = None
    language: str | None = None
    page_count: int | None = None
    media: list[str] | None = Field(default=None, min_length=1)
    categories: list[str] | None = Field(default=None, min_length=1)
    price: float | None = None
    status: str | None = None
    stock: int | None = None


class BookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    title: str
    slug: str
    description: str
    isbn_10: str | None
    isbn_13: str | None
    author: str | None
    publisher: str | None
    publication_date: str | None
    language: str
    page_count: int | None
    media: list[str]
    categories: list[str]
    price: float
    status: str
    stock: int
    created_at: datetime
    updated_at: datetime
