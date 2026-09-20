import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.books.model import Book
from src.core.books.schema import BookCreate, BookUpdate


def create_book(db: Session, data: BookCreate) -> Book:
    book = Book(**data.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def get_book(db: Session, book_id: uuid.UUID) -> Book | None:
    return db.get(Book, book_id)


def list_books(db: Session, skip: int = 0, limit: int = 100) -> list[Book]:
    stmt = select(Book).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_book_by_slug(db: Session, slug: str) -> Book | None:
    stmt = select(Book).where(Book.slug == slug)
    return db.scalars(stmt).first()


def update_book(db: Session, book: Book, data: BookUpdate) -> Book:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return book
