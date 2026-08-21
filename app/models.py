from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(
        String(320),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    listening_progress = relationship(
        "ListeningProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    saved_lectures = relationship(
        "SavedLecture",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_codes = relationship(
        "PasswordResetCode",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    push_tokens = relationship(
        "PushToken", back_populates="user", cascade="all, delete-orphan"
    )
    followed_speakers = relationship("FollowedSpeaker", cascade="all, delete-orphan")
    followed_categories = relationship("FollowedCategory", cascade="all, delete-orphan")
    bookmarks = relationship("LectureBookmark", cascade="all, delete-orphan")
    notes = relationship("LectureNote", cascade="all, delete-orphan")
    listening_activity = relationship("ListeningActivity", cascade="all, delete-orphan")


class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="password_reset_codes")


class PushToken(Base):
    __tablename__ = "push_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(255), nullable=False, unique=True, index=True)
    platform = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="push_tokens")


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    bio = Column(Text, nullable=True)

    lectures = relationship(
        "Lecture",
        back_populates="speaker",
    )


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    lectures = relationship(
        "Lecture",
        back_populates="category",
    )


class Lecture(Base):
    __tablename__ = "lectures"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    media_type = Column(
        String(20),
        nullable=False,
        default="audio",
        server_default="audio",
    )
    audio_url = Column(String(500), nullable=True)
    youtube_url = Column(String(500), nullable=True)

    duration_seconds = Column(Integer, nullable=True)

    speaker_id = Column(
        Integer,
        ForeignKey("speakers.id"),
        nullable=False,
    )

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        nullable=False,
    )

    speaker = relationship(
        "Speaker",
        back_populates="lectures",
    )

    category = relationship(
        "Category",
        back_populates="lectures",
    )

    listening_progress = relationship(
        "ListeningProgress",
        back_populates="lecture",
        cascade="all, delete-orphan",
    )
    saved_by_users = relationship(
        "SavedLecture",
        back_populates="lecture",
        cascade="all, delete-orphan",
    )
    series_memberships = relationship("SeriesLecture", back_populates="lecture", cascade="all, delete-orphan")
    topic_memberships = relationship("LectureTopic", cascade="all, delete-orphan")
    transcript_segments = relationship(
        "LectureTranscriptSegment",
        cascade="all, delete-orphan",
        order_by="LectureTranscriptSegment.start_seconds",
    )


class ListeningProgress(Base):
    __tablename__ = "listening_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lecture_id",
            name="uq_listening_progress_user_lecture",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lecture_id = Column(
        Integer,
        ForeignKey("lectures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position_seconds = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    duration_seconds = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    completed = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship(
        "User",
        back_populates="listening_progress",
    )
    lecture = relationship(
        "Lecture",
        back_populates="listening_progress",
    )


class SavedLecture(Base):
    __tablename__ = "saved_lectures"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lecture_id",
            name="uq_saved_lectures_user_lecture",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lecture_id = Column(
        Integer,
        ForeignKey("lectures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    user = relationship(
        "User",
        back_populates="saved_lectures",
    )
    lecture = relationship(
        "Lecture",
        back_populates="saved_by_users",
    )


class FollowedSpeaker(Base):
    __tablename__ = "followed_speakers"
    __table_args__ = (UniqueConstraint("user_id", "speaker_id", name="uq_followed_speaker"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_id = Column(Integer, ForeignKey("speakers.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    speaker = relationship("Speaker")


class FollowedCategory(Base):
    __tablename__ = "followed_categories"
    __table_args__ = (UniqueConstraint("user_id", "category_id", name="uq_followed_category"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    category = relationship("Category")


class Series(Base):
    __tablename__ = "series"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cover_image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    lectures = relationship(
        "SeriesLecture",
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="SeriesLecture.order_index",
    )


class SeriesLecture(Base):
    __tablename__ = "series_lectures"
    __table_args__ = (
        UniqueConstraint("series_id", "lecture_id", name="uq_series_lecture"),
        UniqueConstraint("series_id", "order_index", name="uq_series_order"),
        Index("ix_series_lectures_series_order", "series_id", "order_index"),
    )

    id = Column(Integer, primary_key=True)
    series_id = Column(Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True)
    lecture_id = Column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    series = relationship("Series", back_populates="lectures")
    lecture = relationship("Lecture", back_populates="series_memberships")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, unique=True)
    slug = Column(String(140), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    lecture_memberships = relationship("LectureTopic", back_populates="topic", cascade="all, delete-orphan")


class LectureTopic(Base):
    __tablename__ = "lecture_topics"
    __table_args__ = (
        UniqueConstraint("lecture_id", "topic_id", name="uq_lecture_topic"),
        Index("ix_lecture_topics_topic_lecture", "topic_id", "lecture_id"),
    )

    id = Column(Integer, primary_key=True)
    lecture_id = Column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lecture = relationship("Lecture", back_populates="topic_memberships")
    topic = relationship("Topic", back_populates="lecture_memberships")


class LectureTranscriptSegment(Base):
    __tablename__ = "lecture_transcript_segments"
    __table_args__ = (
        Index("ix_transcript_lecture_start", "lecture_id", "start_seconds"),
    )

    id = Column(Integer, primary_key=True)
    lecture_id = Column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    start_seconds = Column(Integer, nullable=False)
    end_seconds = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lecture = relationship("Lecture", back_populates="transcript_segments")


class LectureBookmark(Base):
    __tablename__ = "lecture_bookmarks"
    __table_args__ = (Index("ix_bookmarks_user_lecture", "user_id", "lecture_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lecture_id = Column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    position_seconds = Column(Integer, nullable=False)
    label = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    lecture = relationship("Lecture")


class LectureNote(Base):
    __tablename__ = "lecture_notes"
    __table_args__ = (Index("ix_notes_user_lecture", "user_id", "lecture_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lecture_id = Column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    position_seconds = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    lecture = relationship("Lecture")


class ListeningActivity(Base):
    __tablename__ = "listening_activity"
    __table_args__ = (
        UniqueConstraint("user_id", "lecture_id", "activity_date", name="uq_listening_activity_day"),
        Index("ix_listening_activity_user_date", "user_id", "activity_date"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lecture_id = Column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_date = Column(Date, nullable=False)
    seconds_listened = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
