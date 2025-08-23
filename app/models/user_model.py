from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId

class User(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id")
    name: str
    phone: str
    email: Optional[str] = None
    profile_photo: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            ObjectId: lambda oid: str(oid),
        }
