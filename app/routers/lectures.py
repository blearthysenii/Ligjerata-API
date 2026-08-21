from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlparse

from app import models, schemas
from app.database import get_db
from app.core.admin import require_admin

router = APIRouter(
    prefix="/lectures",
    tags=["Lectures"],
)


@router.post("/", response_model=schemas.LectureResponse)
def create_lecture(
    lecture: schemas.LectureCreate,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    hostname = (urlparse(lecture.audio_url or "").hostname or "").lower()
    if (
        lecture.media_type != "audio"
        or not lecture.audio_url
        or not lecture.duration_seconds
        or lecture.duration_seconds <= 0
        or hostname in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
        }
    ):
        raise HTTPException(
            status_code=422,
            detail="Lecture media must be processed before publishing",
        )
    speaker = db.query(models.Speaker).filter(
        models.Speaker.id == lecture.speaker_id
    ).first()

    if not speaker:
        raise HTTPException(
            status_code=404,
            detail="Speaker not found",
        )

    category = db.query(models.Category).filter(
        models.Category.id == lecture.category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found",
        )

    db_lecture = models.Lecture(
        title=lecture.title,
        description=lecture.description,
        media_type=lecture.media_type,
        audio_url=lecture.audio_url,
        youtube_url=lecture.youtube_url,
        duration_seconds=lecture.duration_seconds,
        speaker_id=lecture.speaker_id,
        category_id=lecture.category_id,
    )

    db.add(db_lecture)
    db.commit()
    db.refresh(db_lecture)

    return db_lecture


@router.get("/", response_model=list[schemas.LectureResponse])
def get_lectures(db: Session = Depends(get_db)):
    return db.query(models.Lecture).filter(
        models.Lecture.media_type == "audio",
        models.Lecture.audio_url.isnot(None),
    ).all()


@router.get(
    "/search",
    response_model=list[schemas.LectureResponse],
)
def search_lectures(
    q: str = Query(min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    query = q.strip()

    if not query:
        return []

    escaped_query = (
        query.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    pattern = f"%{escaped_query}%"

    return (
        db.query(models.Lecture)
        .join(models.Lecture.speaker)
        .join(models.Lecture.category)
        .filter(
            models.Lecture.media_type == "audio",
            models.Lecture.audio_url.isnot(None),
            or_(
                models.Lecture.title.ilike(
                    pattern,
                    escape="\\",
                ),
                models.Speaker.name.ilike(
                    pattern,
                    escape="\\",
                ),
                models.Category.name.ilike(
                    pattern,
                    escape="\\",
                ),
            )
        )
        .order_by(models.Lecture.id.desc())
        .all()
    )


@router.get("/popular", response_model=list[schemas.LectureResponse])
def popular_lectures(db: Session = Depends(get_db)):
    activity = (
        db.query(
            models.ListeningProgress.lecture_id.label("lecture_id"),
            func.count(models.ListeningProgress.id).label("plays"),
        )
        .group_by(models.ListeningProgress.lecture_id)
        .subquery()
    )
    return (
        db.query(models.Lecture)
        .outerjoin(activity, activity.c.lecture_id == models.Lecture.id)
        .options(joinedload(models.Lecture.speaker), joinedload(models.Lecture.category))
        .filter(models.Lecture.media_type == "audio", models.Lecture.audio_url.isnot(None))
        .order_by(func.coalesce(activity.c.plays, 0).desc(), models.Lecture.id.desc())
        .limit(10)
        .all()
    )


@router.get("/{lecture_id}", response_model=schemas.LectureResponse)
def get_lecture(
    lecture_id: int,
    db: Session = Depends(get_db),
):
    lecture = db.query(models.Lecture).filter(
        models.Lecture.id == lecture_id,
        models.Lecture.media_type == "audio",
        models.Lecture.audio_url.isnot(None),
    ).first()

    if not lecture:
        raise HTTPException(
            status_code=404,
            detail="Lecture not found",
        )

    return lecture
