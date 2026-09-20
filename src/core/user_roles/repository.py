from sqlalchemy.orm import Session
from src.core.user_roles.schema import UserRoleBase, UserRoleResponse
from src.core.user_roles.model import UserRole


def create_user_role(db: Session, data: UserRoleBase) -> UserRole:
    user_role = UserRole(**data.model_dump())
    db.add(user_role)
    db.commit()
    db.refresh(user_role)
    return user_role
