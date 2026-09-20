import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.core.books import repository
from src.core.books.model import Book
from src.core.books.schema import BookCreate, BookUpdate


def create_book(db: Session, data: BookCreate) -> Book:
    if repository.get_book_by_slug(db, data.slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A book with slug '{data.slug}' already exists",
        )
    return repository.create_book(db, data)


def get_book(db: Session, book_id: uuid.UUID) -> Book:
    book = repository.get_book(db, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Book not found"
        )
    return book


def list_books(db: Session, skip: int = 0, limit: int = 100) -> list[Book]:
    return repository.list_books(db, skip=skip, limit=limit)


def update_book(db: Session, book_id: uuid.UUID, data: BookUpdate) -> Book:
    book = get_book(db, book_id)
    if data.slug and data.slug != book.slug:
        existing = repository.get_book_by_slug(db, data.slug)
        if existing and existing.id != book.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A book with slug '{data.slug}' already exists",
            )
    return repository.update_book(db, book, data)
