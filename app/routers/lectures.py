from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/lectures",
    tags=["Lectures"],
)


@router.post("/", response_model=schemas.LectureResponse)
def create_lecture(
    lecture: schemas.LectureCreate,
    db: Session = Depends(get_db),
):
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
        audio_url=lecture.audio_url,
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
    return db.query(models.Lecture).all()


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


@router.get("/{lecture_id}", response_model=schemas.LectureResponse)
def get_lecture(
    lecture_id: int,
    db: Session = Depends(get_db),
):
    lecture = db.query(models.Lecture).filter(
        models.Lecture.id == lecture_id
    ).first()

    if not lecture:
        raise HTTPException(
            status_code=404,
            detail="Lecture not found",
        )

    return lecture
