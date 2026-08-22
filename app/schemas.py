from datetime import date, datetime
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
    date_of_birth: date

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError("Full name must be at least 2 characters")

        return normalized

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailLookupRequest(BaseModel):
    email: EmailStr


class EmailLookupResponse(BaseModel):
    exists: bool


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    is_admin: bool
    created_at: datetime
    date_of_birth: date | None = None

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


class PushTokenCreate(BaseModel):
    token: str = Field(min_length=20, max_length=255)
    platform: Literal["ios", "android"]


class PushTokenResponse(BaseModel):
    id: int
    token: str
    platform: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowedSpeakerResponse(BaseModel):
    id: int
    created_at: datetime
    speaker: SpeakerResponse
    model_config = ConfigDict(from_attributes=True)


class FollowedCategoryResponse(BaseModel):
    id: int
    created_at: datetime
    category: CategoryResponse
    model_config = ConfigDict(from_attributes=True)


class MediaFromUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class MediaIngestResponse(BaseModel):
    audio_url: str
    duration_seconds: int
    filename: str


class RankedLecture(BaseModel):
    lecture_id: int
    title: str
    count: int


class AdminDashboardResponse(BaseModel):
    total_users: int
    total_lectures: int
    total_speakers: int
    total_categories: int
    total_saved_lectures: int
    listening_activity: int
    most_listened: list[RankedLecture]
    most_saved: list[RankedLecture]
    feedback_count: int = 0
    helpful_feedback_count: int = 0
    helpful_feedback_rate: float = 0
    most_helpful: list[RankedLecture] = Field(default_factory=list)


class AdminUserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    is_admin: bool
    created_at: datetime


class UserStatusUpdate(BaseModel):
    is_active: bool


class SeriesBase(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    cover_image_url: str | None = None
    is_active: bool = True


class SeriesCreate(SeriesBase):
    pass


class SeriesUpdate(SeriesBase):
    pass


class SeriesResponse(SeriesBase):
    id: int
    created_at: datetime
    updated_at: datetime
    lecture_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class SeriesLectureItem(BaseModel):
    id: int
    order_index: int
    lecture: LectureResponse
    model_config = ConfigDict(from_attributes=True)


class SeriesDetailResponse(SeriesResponse):
    lectures: list[SeriesLectureItem] = Field(default_factory=list)


class SeriesMembershipUpdate(BaseModel):
    lecture_ids: list[int] = Field(default_factory=list, max_length=500)


class TopicBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, max_length=140)
    is_active: bool = True


class TopicCreate(TopicBase):
    pass


class TopicUpdate(TopicBase):
    pass


class TopicResponse(BaseModel):
    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LectureTopicsUpdate(BaseModel):
    topic_ids: list[int] = Field(default_factory=list, max_length=100)


class TranscriptSegmentBase(BaseModel):
    start_seconds: int = Field(ge=0)
    end_seconds: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be after start_seconds")
        return self


class TranscriptSegmentCreate(TranscriptSegmentBase):
    pass


class TranscriptSegmentResponse(TranscriptSegmentBase):
    id: int
    lecture_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TranscriptReplaceRequest(BaseModel):
    segments: list[TranscriptSegmentCreate] = Field(default_factory=list, max_length=10000)


class TranscriptGenerateRequest(BaseModel):
    language: str = Field(default="sq", min_length=2, max_length=10)


class TranscriptSearchResult(BaseModel):
    lecture: LectureResponse
    snippet: str
    timestamp_seconds: int


class BookmarkCreate(BaseModel):
    position_seconds: int = Field(ge=0)
    label: str | None = Field(default=None, max_length=200)


class BookmarkResponse(BaseModel):
    id: int
    position_seconds: int
    label: str | None
    created_at: datetime
    updated_at: datetime
    lecture: LectureResponse
    model_config = ConfigDict(from_attributes=True)


class NoteCreate(BaseModel):
    position_seconds: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=5000)


class NoteUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class NoteResponse(BaseModel):
    id: int
    position_seconds: int
    text: str
    created_at: datetime
    updated_at: datetime
    lecture: LectureResponse
    model_config = ConfigDict(from_attributes=True)


class ListeningStatsResponse(BaseModel):
    today_minutes: int
    week_minutes: int
    current_streak: int
    longest_streak: int
    completed_lectures: int
    active_days_this_week: int


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    confirmation: str = Field(min_length=1, max_length=50)


class OnboardingResponse(BaseModel):
    listening_frequency: Literal["daily", "weekly", "none"] = "none"
    onboarding_completed: bool = False


class OnboardingUpdate(OnboardingResponse):
    category_ids: list[int] = Field(default_factory=list, max_length=100)
    speaker_ids: list[int] = Field(default_factory=list, max_length=100)
    topic_ids: list[int] = Field(default_factory=list, max_length=100)


class PlaylistCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class PlaylistUpdate(PlaylistCreate):
    pass


class PlaylistLectureResponse(BaseModel):
    id: int
    order_index: int
    lecture: LectureResponse
    model_config = ConfigDict(from_attributes=True)


class PlaylistResponse(BaseModel):
    id: int
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    lectures: list[PlaylistLectureResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class PlaylistReorder(BaseModel):
    lecture_ids: list[int] = Field(max_length=500)


class NotificationPreferenceResponse(BaseModel):
    followed_speakers_enabled: bool = True
    followed_categories_enabled: bool = True
    new_series_enabled: bool = True
    recommendations_enabled: bool = True
    daily_reminder_enabled: bool = False
    daily_reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class NotificationPreferenceUpdate(NotificationPreferenceResponse):
    pass


class FeedbackUpdate(BaseModel):
    value: Literal["helpful", "not_for_me"]


class FeedbackResponse(FeedbackUpdate):
    id: int
    lecture_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


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
