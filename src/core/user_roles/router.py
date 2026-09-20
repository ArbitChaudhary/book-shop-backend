from fastapi import APIRouter, status, Depends
from .schema import UserRoleResponse, UserRoleBase
from .model import UserRole
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.core.user_roles import service

router = APIRouter(prefix="/user-roles", tags=["user-roles"])


@router.post("", response_model=UserRoleResponse, status_code=status.HTTP_201_CREATED)
def create_user_role(data: UserRoleBase, db: Session = Depends(get_db)):
    return service.create_user_role(db, data)
