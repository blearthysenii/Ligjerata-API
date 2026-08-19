import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
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


router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
    dependencies=[Depends(require_admin)],
)


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
