from pydantic import BaseModel, Field, validator
from typing import Optional, List
import re

USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    expiry_days: Optional[int] = Field(None, gt=0)
    data_cap_gb: Optional[float] = Field(None, gt=0)
    max_devices: Optional[int] = Field(None, ge=1)
    note: Optional[str] = None

    @validator('username')
    def validate_username(cls, v):
        if not USERNAME_REGEX.match(v):
            raise ValueError('Invalid username')
        return v

class UserUpdate(BaseModel):
    expiry_days: Optional[int] = Field(None, gt=0)
    data_cap_gb: Optional[float] = Field(None, gt=0)
    max_devices: Optional[int] = Field(None, ge=1)
    note: Optional[str] = None
    reset_usage: bool = False

class UserExtend(BaseModel):
    days: int = Field(..., gt=0)

class BulkUserCreate(BaseModel):
    users: List[UserCreate]

class UserResponse(BaseModel):
    id: int
    username: str
    uuid: str
    status: str
    created_at: str
    expiry_at: Optional[str]
    data_cap_bytes: Optional[int]
    bytes_used: int
    max_devices: Optional[int]
    vless_uri: str
    note: Optional[str] = None

    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    total: int
    users: List[UserResponse]
