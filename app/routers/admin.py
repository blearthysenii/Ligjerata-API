import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_
from fastapi import Query
from app.core.admin import is_admin_email
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.core.admin import require_admin
from app.database import get_db
from app.services.media import (
    DOWNLOAD_CHUNK_SIZE,
    MAX_MEDIA_BYTES,
    MediaProcessingError,
    ingest_uploaded_path,
    ingest_url,
    validate_upload_metadata,
)
from app.services.notifications import send_new_lecture_notifications


router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
    dependencies=[Depends(require_admin)],
)


@router.get("/dashboard", response_model=schemas.AdminDashboardResponse)
def dashboard(db: Session = Depends(get_db)):
    listened = (
        db.query(
            models.Lecture.id,
            models.Lecture.title,
            func.count(models.ListeningProgress.id).label("count"),
        )
        .join(models.ListeningProgress, models.ListeningProgress.lecture_id == models.Lecture.id)
        .group_by(models.Lecture.id, models.Lecture.title)
        .order_by(func.count(models.ListeningProgress.id).desc())
        .limit(5)
        .all()
    )
    saved = (
        db.query(
            models.Lecture.id,
            models.Lecture.title,
            func.count(models.SavedLecture.id).label("count"),
        )
        .join(models.SavedLecture, models.SavedLecture.lecture_id == models.Lecture.id)
        .group_by(models.Lecture.id, models.Lecture.title)
        .order_by(func.count(models.SavedLecture.id).desc())
        .limit(5)
        .all()
    )
    feedback_count = db.query(models.LectureFeedback).count()
    helpful_feedback_count = db.query(models.LectureFeedback).filter_by(value="helpful").count()
    helpful = (
        db.query(models.Lecture.id, models.Lecture.title, func.count(models.LectureFeedback.id).label("count"))
        .join(models.LectureFeedback, models.LectureFeedback.lecture_id == models.Lecture.id)
        .filter(models.LectureFeedback.value == "helpful")
        .group_by(models.Lecture.id, models.Lecture.title)
        .order_by(func.count(models.LectureFeedback.id).desc())
        .limit(5)
        .all()
    )
    return {
        "total_users": db.query(models.User).count(),
        "total_lectures": db.query(models.Lecture).count(),
        "total_speakers": db.query(models.Speaker).count(),
        "total_categories": db.query(models.Category).count(),
        "total_saved_lectures": db.query(models.SavedLecture).count(),
        "listening_activity": db.query(models.ListeningProgress).count(),
        "most_listened": [
            {"lecture_id": row.id, "title": row.title, "count": row.count}
            for row in listened
        ],
        "most_saved": [
            {"lecture_id": row.id, "title": row.title, "count": row.count}
            for row in saved
        ],
        "feedback_count": feedback_count,
        "helpful_feedback_count": helpful_feedback_count,
        "helpful_feedback_rate": round((helpful_feedback_count / feedback_count * 100) if feedback_count else 0, 1),
        "most_helpful": [{"lecture_id": row.id, "title": row.title, "count": row.count} for row in helpful],
    }


def admin_user_response(user: models.User) -> dict:
    return {
        "id": user.id, "full_name": user.full_name, "email": user.email,
        "is_active": user.is_active, "is_admin": is_admin_email(user.email),
        "created_at": user.created_at,
    }


@router.get("/users", response_model=list[schemas.AdminUserResponse])
def list_users(q: str | None = Query(default=None, max_length=100), db: Session = Depends(get_db)):
    query = db.query(models.User)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(models.User.full_name.ilike(pattern), models.User.email.ilike(pattern)))
    return [admin_user_response(user) for user in query.order_by(models.User.created_at.desc()).limit(100).all()]


@router.get("/users/{user_id}", response_model=schemas.AdminUserResponse)
def user_detail(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return admin_user_response(user)


@router.patch("/users/{user_id}/status", response_model=schemas.AdminUserResponse)
def update_user_status(
    user_id: int,
    payload: schemas.UserStatusUpdate,
    current_admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_admin.id and not payload.is_active:
        raise HTTPException(status_code=409, detail="You cannot disable your own account")
    user.is_active = payload.is_active
    db.commit(); db.refresh(user)
    return admin_user_response(user)


def get_speaker_or_404(speaker_id: int, db: Session) -> models.Speaker:
    speaker = db.query(models.Speaker).filter(
        models.Speaker.id == speaker_id
    ).first()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return speaker


def get_category_or_404(category_id: int, db: Session) -> models.Category:
    category = db.query(models.Category).filter(
        models.Category.id == category_id
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def get_lecture_or_404(lecture_id: int, db: Session) -> models.Lecture:
    lecture = db.query(models.Lecture).filter(
        models.Lecture.id == lecture_id
    ).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return lecture


def apply_lecture_values(
    lecture: models.Lecture,
    payload: schemas.LectureBase,
) -> None:
    lecture.title = payload.title.strip()
    lecture.description = payload.description
    lecture.media_type = payload.media_type
    lecture.audio_url = payload.audio_url
    lecture.youtube_url = payload.youtube_url
    lecture.duration_seconds = payload.duration_seconds
    lecture.speaker_id = payload.speaker_id
    lecture.category_id = payload.category_id


def ensure_audio_lecture(payload: schemas.LectureBase) -> None:
    hostname = (
        urlparse(payload.audio_url or "").hostname or ""
    ).lower()
    if (
        payload.media_type != "audio"
        or not payload.audio_url
        or not payload.duration_seconds
        or payload.duration_seconds <= 0
        or hostname in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
        }
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Lecture media must be processed before publishing. "
                "A prepared audio URL and duration are required."
            ),
        )


def media_error(error: MediaProcessingError) -> HTTPException:
    code = (
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        if "250 MB" in str(error)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=code, detail=str(error))


@router.post("/media/from-url", response_model=schemas.MediaIngestResponse)
def prepare_media_from_url(payload: schemas.MediaFromUrlRequest):
    try:
        return ingest_url(payload.url)
    except MediaProcessingError as error:
        raise media_error(error)


@router.post("/media/upload", response_model=schemas.MediaIngestResponse)
async def prepare_uploaded_media(file: UploadFile = File(...)):
    filename = file.filename or "upload"
    try:
        extension = validate_upload_metadata(filename, file.content_type)
    except MediaProcessingError as error:
        raise media_error(error)

    with tempfile.TemporaryDirectory(prefix="ligjerata-upload-") as temp_name:
        source_path = Path(temp_name) / f"uploaded-source{extension}"
        total = 0
        try:
            with source_path.open("wb") as output:
                while chunk := await file.read(DOWNLOAD_CHUNK_SIZE):
                    total += len(chunk)
                    if total > MAX_MEDIA_BYTES:
                        raise MediaProcessingError(
                            "Skedari është më i madh se 250 MB."
                        )
                    output.write(chunk)
            return await run_in_threadpool(ingest_uploaded_path, source_path)
        except MediaProcessingError as error:
            raise media_error(error)
        finally:
            await file.close()


@router.get("/lectures", response_model=list[schemas.LectureResponse])
def list_lectures(db: Session = Depends(get_db)):
    return (
        db.query(models.Lecture)
        .options(
            joinedload(models.Lecture.speaker),
            joinedload(models.Lecture.category),
        )
        .order_by(models.Lecture.id.desc())
        .all()
    )


@router.post(
    "/lectures",
    response_model=schemas.LectureResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lecture(
    payload: schemas.LectureCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    ensure_audio_lecture(payload)
    get_speaker_or_404(payload.speaker_id, db)
    get_category_or_404(payload.category_id, db)
    lecture = models.Lecture()
    apply_lecture_values(lecture, payload)
    db.add(lecture)
    db.commit()
    db.refresh(lecture)
    speaker_followers = db.query(models.FollowedSpeaker.user_id.label("user_id")).outerjoin(
        models.NotificationPreference,
        models.NotificationPreference.user_id == models.FollowedSpeaker.user_id,
    ).filter(
        models.FollowedSpeaker.speaker_id == lecture.speaker_id,
        or_(models.NotificationPreference.id.is_(None), models.NotificationPreference.followed_speakers_enabled.is_(True)),
    )
    category_followers = db.query(models.FollowedCategory.user_id.label("user_id")).outerjoin(
        models.NotificationPreference,
        models.NotificationPreference.user_id == models.FollowedCategory.user_id,
    ).filter(
        models.FollowedCategory.category_id == lecture.category_id,
        or_(models.NotificationPreference.id.is_(None), models.NotificationPreference.followed_categories_enabled.is_(True)),
    )
    follower_ids = speaker_followers.union(
        category_followers
    ).subquery()
    tokens = [row.token for row in db.query(models.PushToken.token).filter(
        models.PushToken.user_id.in_(db.query(follower_ids.c.user_id))
    ).all()]
    background_tasks.add_task(
        send_new_lecture_notifications,
        tokens,
        lecture.id,
        lecture.title,
        lecture.speaker.name,
    )
    return lecture


@router.put(
    "/lectures/{lecture_id}",
    response_model=schemas.LectureResponse,
)
def update_lecture(
    lecture_id: int,
    payload: schemas.LectureUpdate,
    db: Session = Depends(get_db),
):
    ensure_audio_lecture(payload)
    lecture = get_lecture_or_404(lecture_id, db)
    get_speaker_or_404(payload.speaker_id, db)
    get_category_or_404(payload.category_id, db)
    apply_lecture_values(lecture, payload)
    db.commit()
    db.refresh(lecture)
    return lecture


@router.delete(
    "/lectures/{lecture_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_lecture(
    lecture_id: int,
    db: Session = Depends(get_db),
):
    lecture = get_lecture_or_404(lecture_id, db)
    has_user_data = (
        db.query(models.ListeningProgress).filter(
            models.ListeningProgress.lecture_id == lecture_id
        ).first()
        or db.query(models.SavedLecture).filter(
            models.SavedLecture.lecture_id == lecture_id
        ).first()
    )

    if has_user_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lecture cannot be deleted while it has user progress or saves",
        )

    db.delete(lecture)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/speakers", response_model=list[schemas.SpeakerResponse])
def list_speakers(db: Session = Depends(get_db)):
    return db.query(models.Speaker).order_by(models.Speaker.name).all()


@router.post(
    "/speakers",
    response_model=schemas.SpeakerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_speaker(
    payload: schemas.SpeakerCreate,
    db: Session = Depends(get_db),
):
    speaker = models.Speaker(name=payload.name.strip(), bio=payload.bio)
    db.add(speaker)
    db.commit()
    db.refresh(speaker)
    return speaker


@router.put(
    "/speakers/{speaker_id}",
    response_model=schemas.SpeakerResponse,
)
def update_speaker(
    speaker_id: int,
    payload: schemas.SpeakerUpdate,
    db: Session = Depends(get_db),
):
    speaker = get_speaker_or_404(speaker_id, db)
    speaker.name = payload.name.strip()
    speaker.bio = payload.bio
    db.commit()
    db.refresh(speaker)
    return speaker


@router.get("/categories", response_model=list[schemas.CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).order_by(models.Category.name).all()


@router.post(
    "/categories",
    response_model=schemas.CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
):
    category = models.Category(name=payload.name.strip())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Category already exists")
    db.refresh(category)
    return category


@router.put(
    "/categories/{category_id}",
    response_model=schemas.CategoryResponse,
)
def update_category(
    category_id: int,
    payload: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
):
    category = get_category_or_404(category_id, db)
    category.name = payload.name.strip()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Category already exists")
    db.refresh(category)
    return category
