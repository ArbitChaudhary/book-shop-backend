import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class RoleEnum(str, Enum):
    ADMIN = "admin"
    USER = "user"
    MERCHANT = "merchant"


class UserRoleBase(BaseModel):
    user_id: str
    role: RoleEnum
    createdAt: str
    updatedAt: str


class UserRoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: str
    role: RoleEnum
    createdAt: datetime
    updatedAt: datetime
