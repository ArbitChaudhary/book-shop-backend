import uuid
from sqlalchemy.orm import Session
from src.core.user_roles.schema import UserRoleBase
from src.core.user_roles.model import UserRole
from src.core.user_roles import repository


def create_user_role(db: Session, data: UserRoleBase) -> UserRole:
    return repository.create_user_role(db, data)
