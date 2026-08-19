from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
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

    audio_url = Column(String(500), nullable=False)

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
