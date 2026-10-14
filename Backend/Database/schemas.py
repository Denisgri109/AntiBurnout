from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime


class ReadingBase(BaseModel):
    sensor: str = Field(min_length=1, max_length=20)
    content: float
    
    
class ReadingCreate(ReadingBase):
    user_id: int


class ReadingResponse(ReadingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    date_timestamp: datetime
    author: UserResponse
    
    
class UserBase(BaseModel):
    username:str = Field(min_length=3, max_length=20)
    email: EmailStr = Field(max_length=320)
    
    
class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    