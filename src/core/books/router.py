import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.core.books import service
from src.core.books.schema import BookCreate, BookResponse, BookUpdate

router = APIRouter(prefix="/books", tags=["Books"])


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
def create_book(data: BookCreate, db: Session = Depends(get_db)):
    return service.create_book(db, data)


@router.get("", response_model=list[BookResponse])
def list_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.list_books(db, skip=skip, limit=limit)


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.get_book(db, book_id)


@router.patch("/{book_id}", response_model=BookResponse)
def update_book(book_id: uuid.UUID, data: BookUpdate, db: Session = Depends(get_db)):
    return service.update_book(db, book_id, data)
