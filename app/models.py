from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
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
