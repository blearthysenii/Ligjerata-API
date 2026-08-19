from datetime import datetime
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError("Full name must be at least 2 characters")

        return normalized


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class SpeakerBase(BaseModel):
    name: str
    bio: Optional[str] = None


class SpeakerCreate(SpeakerBase):
    pass


class SpeakerResponse(SpeakerBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CategoryBase(BaseModel):
    name: str


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class LectureBase(BaseModel):
    title: str
    description: Optional[str] = None
    audio_url: str
    duration_seconds: Optional[int] = None
    speaker_id: int
    category_id: int


class LectureCreate(LectureBase):
    pass


class LectureResponse(LectureBase):
    id: int
    speaker: SpeakerResponse
    category: CategoryResponse

    model_config = ConfigDict(from_attributes=True)


class ListeningProgressUpdate(BaseModel):
    position_seconds: int = Field(ge=0)
    duration_seconds: int = Field(ge=0)
    completed: bool = False


class ListeningProgressResponse(BaseModel):
    id: int
    position_seconds: int
    duration_seconds: int
    completed: bool
    updated_at: datetime
    lecture: LectureResponse

    model_config = ConfigDict(from_attributes=True)


class SavedLectureResponse(BaseModel):
    id: int
    created_at: datetime
    lecture: LectureResponse

    model_config = ConfigDict(from_attributes=True)
