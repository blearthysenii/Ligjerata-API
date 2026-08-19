from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from urllib.parse import parse_qs, urlparse


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
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class SpeakerBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    bio: str | None = None


class SpeakerCreate(SpeakerBase):
    pass


class SpeakerUpdate(SpeakerBase):
    pass


class SpeakerResponse(SpeakerBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CategoryBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class LectureBase(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    media_type: Literal["audio", "youtube"] = "audio"
    audio_url: str | None = None
    youtube_url: str | None = None
    duration_seconds: int | None = None
    speaker_id: int
    category_id: int

    @model_validator(mode="after")
    def validate_media_url(self):
        if self.media_type == "audio":
            if not self.audio_url:
                raise ValueError("Audio URL is required for audio lectures")
            validate_http_url(self.audio_url, "audio")
            self.youtube_url = None
        else:
            if not self.youtube_url:
                raise ValueError("YouTube URL is required for YouTube lectures")
            validate_youtube_url(self.youtube_url)
            self.audio_url = None

        return self


class LectureCreate(LectureBase):
    pass


class LectureUpdate(LectureBase):
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


class MediaFromUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class MediaIngestResponse(BaseModel):
    audio_url: str
    duration_seconds: int
    filename: str


def validate_http_url(value: str, label: str) -> None:
    parsed = urlparse(value.strip())

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"A valid {label} URL is required")


def validate_youtube_url(value: str) -> None:
    validate_http_url(value, "YouTube")
    parsed = urlparse(value.strip())
    hostname = (parsed.hostname or "").lower()

    if hostname not in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
    }:
        raise ValueError("A valid YouTube URL is required")

    parts = [part for part in parsed.path.split("/") if part]
    has_video_id = (
        (hostname == "youtu.be" and bool(parts))
        or (parsed.path == "/watch" and bool(parse_qs(parsed.query).get("v")))
        or (bool(parts) and parts[0] in {"embed", "shorts", "live"} and len(parts) > 1)
    )

    if not has_video_id:
        raise ValueError("The YouTube URL must contain a video ID")
