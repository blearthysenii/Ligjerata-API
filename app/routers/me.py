from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_user


router = APIRouter(
    prefix="/me",
    tags=["My Library"],
)


def get_lecture_or_404(
    lecture_id: int,
    db: Session,
) -> models.Lecture:
    lecture = db.query(models.Lecture).filter(
        models.Lecture.id == lecture_id,
        models.Lecture.media_type == "audio",
        models.Lecture.audio_url.isnot(None),
    ).first()

    if not lecture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture not found",
        )

    return lecture


@router.get(
    "/listening-progress",
    response_model=list[schemas.ListeningProgressResponse],
)
def get_listening_progress(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.ListeningProgress)
        .join(models.ListeningProgress.lecture)
        .options(
            joinedload(models.ListeningProgress.lecture)
            .joinedload(models.Lecture.speaker),
            joinedload(models.ListeningProgress.lecture)
            .joinedload(models.Lecture.category),
        )
        .filter(
            models.ListeningProgress.user_id == current_user.id,
            models.Lecture.media_type == "audio",
            models.Lecture.audio_url.isnot(None),
        )
        .order_by(models.ListeningProgress.updated_at.desc())
        .all()
    )


@router.get(
    "/listening-progress/{lecture_id}",
    response_model=schemas.ListeningProgressResponse,
)
def get_lecture_progress(
    lecture_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    progress = (
        db.query(models.ListeningProgress)
        .join(models.ListeningProgress.lecture)
        .options(
            joinedload(models.ListeningProgress.lecture)
            .joinedload(models.Lecture.speaker),
            joinedload(models.ListeningProgress.lecture)
            .joinedload(models.Lecture.category),
        )
        .filter(
            models.ListeningProgress.user_id == current_user.id,
            models.ListeningProgress.lecture_id == lecture_id,
            models.Lecture.media_type == "audio",
            models.Lecture.audio_url.isnot(None),
        )
        .first()
    )

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listening progress not found",
        )

    return progress


@router.put(
    "/listening-progress/{lecture_id}",
    response_model=schemas.ListeningProgressResponse,
)
def upsert_lecture_progress(
    lecture_id: int,
    payload: schemas.ListeningProgressUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_lecture_or_404(lecture_id, db)

    duration = payload.duration_seconds
    position = min(payload.position_seconds, duration) if duration else 0
    completed = payload.completed or (
        duration > 0 and position >= max(duration - 5, 0)
    )

    progress = db.query(models.ListeningProgress).filter(
        models.ListeningProgress.user_id == current_user.id,
        models.ListeningProgress.lecture_id == lecture_id,
    ).first()

    if progress:
        progress.position_seconds = position
        progress.duration_seconds = duration
        progress.completed = completed
    else:
        progress = models.ListeningProgress(
            user_id=current_user.id,
            lecture_id=lecture_id,
            position_seconds=position,
            duration_seconds=duration,
            completed=completed,
        )
        db.add(progress)

    db.commit()
    db.refresh(progress)

    return progress


@router.get(
    "/saved-lectures",
    response_model=list[schemas.SavedLectureResponse],
)
def get_saved_lectures(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.SavedLecture)
        .join(models.SavedLecture.lecture)
        .options(
            joinedload(models.SavedLecture.lecture)
            .joinedload(models.Lecture.speaker),
            joinedload(models.SavedLecture.lecture)
            .joinedload(models.Lecture.category),
        )
        .filter(models.SavedLecture.user_id == current_user.id)
        .filter(
            models.Lecture.media_type == "audio",
            models.Lecture.audio_url.isnot(None),
        )
        .order_by(models.SavedLecture.created_at.desc())
        .all()
    )


@router.post(
    "/saved-lectures/{lecture_id}",
    response_model=schemas.SavedLectureResponse,
)
def save_lecture(
    lecture_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_lecture_or_404(lecture_id, db)
    saved = db.query(models.SavedLecture).filter(
        models.SavedLecture.user_id == current_user.id,
        models.SavedLecture.lecture_id == lecture_id,
    ).first()

    if saved:
        return saved

    saved = models.SavedLecture(
        user_id=current_user.id,
        lecture_id=lecture_id,
    )
    db.add(saved)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.query(models.SavedLecture).filter(
            models.SavedLecture.user_id == current_user.id,
            models.SavedLecture.lecture_id == lecture_id,
        ).one()

    db.refresh(saved)

    return saved


@router.delete(
    "/saved-lectures/{lecture_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unsave_lecture(
    lecture_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved = db.query(models.SavedLecture).filter(
        models.SavedLecture.user_id == current_user.id,
        models.SavedLecture.lecture_id == lecture_id,
    ).first()

    if saved:
        db.delete(saved)
        db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
