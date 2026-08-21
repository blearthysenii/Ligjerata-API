import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.core.admin import require_admin
from app.database import get_db
from app.services.transcription import TranscriptionError, get_transcription_provider


router = APIRouter(
    prefix="/admin",
    tags=["Administration: content structure"],
    dependencies=[Depends(require_admin)],
)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "topic"


def series_or_404(series_id: int, db: Session) -> models.Series:
    item = db.query(models.Series).filter(models.Series.id == series_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Series not found")
    return item


def series_payload(item: models.Series) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "cover_image_url": item.cover_image_url,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "lecture_count": len(item.lectures),
    }


def apply_series(item: models.Series, payload: schemas.SeriesBase) -> None:
    item.title = payload.title.strip()
    item.description = payload.description.strip() if payload.description else None
    item.cover_image_url = payload.cover_image_url.strip() if payload.cover_image_url else None
    item.is_active = payload.is_active


@router.get("/series", response_model=list[schemas.SeriesResponse])
def admin_series(db: Session = Depends(get_db)):
    return [series_payload(item) for item in db.query(models.Series).order_by(models.Series.updated_at.desc()).all()]


@router.post("/series", response_model=schemas.SeriesResponse, status_code=201)
def create_series(payload: schemas.SeriesCreate, db: Session = Depends(get_db)):
    item = models.Series()
    apply_series(item, payload)
    db.add(item); db.commit(); db.refresh(item)
    return series_payload(item)


@router.put("/series/{series_id}", response_model=schemas.SeriesResponse)
def update_series(series_id: int, payload: schemas.SeriesUpdate, db: Session = Depends(get_db)):
    item = series_or_404(series_id, db)
    apply_series(item, payload)
    db.commit(); db.refresh(item)
    return series_payload(item)


@router.delete("/series/{series_id}", response_model=schemas.SeriesResponse)
def archive_series(series_id: int, db: Session = Depends(get_db)):
    item = series_or_404(series_id, db)
    item.is_active = False
    db.commit(); db.refresh(item)
    return series_payload(item)


@router.get("/series/{series_id}/lectures", response_model=list[schemas.SeriesLectureItem])
def admin_series_lectures(series_id: int, db: Session = Depends(get_db)):
    series_or_404(series_id, db)
    return db.query(models.SeriesLecture).options(
        joinedload(models.SeriesLecture.lecture).joinedload(models.Lecture.speaker),
        joinedload(models.SeriesLecture.lecture).joinedload(models.Lecture.category),
    ).filter(models.SeriesLecture.series_id == series_id).order_by(models.SeriesLecture.order_index).all()


@router.put("/series/{series_id}/lectures", response_model=list[schemas.SeriesLectureItem])
def set_series_lectures(series_id: int, payload: schemas.SeriesMembershipUpdate, db: Session = Depends(get_db)):
    series_or_404(series_id, db)
    if len(payload.lecture_ids) != len(set(payload.lecture_ids)):
        raise HTTPException(status_code=422, detail="A lecture cannot appear twice in the same series")
    found = {row.id for row in db.query(models.Lecture.id).filter(models.Lecture.id.in_(payload.lecture_ids)).all()}
    if found != set(payload.lecture_ids):
        raise HTTPException(status_code=404, detail="One or more lectures were not found")
    existing = {item.lecture_id: item for item in db.query(models.SeriesLecture).filter_by(series_id=series_id).all()}
    for index, item in enumerate(existing.values()):
        item.order_index = -(index + 1)
    db.flush()
    requested = set(payload.lecture_ids)
    for lecture_id, item in existing.items():
        if lecture_id not in requested:
            db.delete(item)
    db.flush()
    for index, lecture_id in enumerate(payload.lecture_ids):
        item = existing.get(lecture_id)
        if item:
            item.order_index = index
        else:
            db.add(models.SeriesLecture(series_id=series_id, lecture_id=lecture_id, order_index=index))
    db.commit()
    return admin_series_lectures(series_id, db)


@router.get("/topics", response_model=list[schemas.TopicResponse])
def admin_topics(db: Session = Depends(get_db)):
    return db.query(models.Topic).order_by(models.Topic.name).all()


def topic_or_404(topic_id: int, db: Session) -> models.Topic:
    topic = db.query(models.Topic).filter(models.Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def apply_topic(topic: models.Topic, payload: schemas.TopicBase) -> None:
    topic.name = payload.name.strip()
    topic.slug = slugify(payload.slug or payload.name)
    topic.is_active = payload.is_active


@router.post("/topics", response_model=schemas.TopicResponse, status_code=201)
def create_topic(payload: schemas.TopicCreate, db: Session = Depends(get_db)):
    topic = models.Topic(); apply_topic(topic, payload); db.add(topic)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Topic name or slug already exists")
    db.refresh(topic); return topic


@router.put("/topics/{topic_id}", response_model=schemas.TopicResponse)
def update_topic(topic_id: int, payload: schemas.TopicUpdate, db: Session = Depends(get_db)):
    topic = topic_or_404(topic_id, db); apply_topic(topic, payload)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Topic name or slug already exists")
    db.refresh(topic); return topic


@router.delete("/topics/{topic_id}", response_model=schemas.TopicResponse)
def archive_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = topic_or_404(topic_id, db); topic.is_active = False
    db.commit(); db.refresh(topic); return topic


@router.put("/lectures/{lecture_id}/topics", response_model=list[schemas.TopicResponse])
def set_lecture_topics(lecture_id: int, payload: schemas.LectureTopicsUpdate, db: Session = Depends(get_db)):
    if not db.query(models.Lecture.id).filter(models.Lecture.id == lecture_id).first():
        raise HTTPException(status_code=404, detail="Lecture not found")
    if len(payload.topic_ids) != len(set(payload.topic_ids)):
        raise HTTPException(status_code=422, detail="Duplicate topics are not allowed")
    topics = db.query(models.Topic).filter(models.Topic.id.in_(payload.topic_ids)).all()
    if {topic.id for topic in topics} != set(payload.topic_ids):
        raise HTTPException(status_code=404, detail="One or more topics were not found")
    db.query(models.LectureTopic).filter(models.LectureTopic.lecture_id == lecture_id).delete()
    db.add_all([models.LectureTopic(lecture_id=lecture_id, topic_id=topic_id) for topic_id in payload.topic_ids])
    db.commit()
    return sorted(topics, key=lambda item: item.name)


@router.put("/lectures/{lecture_id}/transcript", response_model=list[schemas.TranscriptSegmentResponse])
def replace_transcript(lecture_id: int, payload: schemas.TranscriptReplaceRequest, db: Session = Depends(get_db)):
    if not db.query(models.Lecture.id).filter(models.Lecture.id == lecture_id).first():
        raise HTTPException(status_code=404, detail="Lecture not found")
    db.query(models.LectureTranscriptSegment).filter_by(lecture_id=lecture_id).delete()
    db.add_all([models.LectureTranscriptSegment(lecture_id=lecture_id, **segment.model_dump()) for segment in payload.segments])
    db.commit()
    return db.query(models.LectureTranscriptSegment).filter_by(lecture_id=lecture_id).order_by(models.LectureTranscriptSegment.start_seconds).all()


@router.post("/lectures/{lecture_id}/transcript/generate", response_model=list[schemas.TranscriptSegmentResponse])
def generate_transcript(lecture_id: int, payload: schemas.TranscriptGenerateRequest, db: Session = Depends(get_db)):
    lecture = db.query(models.Lecture).filter(models.Lecture.id == lecture_id).first()
    if not lecture or not lecture.audio_url:
        raise HTTPException(status_code=404, detail="Lecture audio not found")
    try:
        segments = get_transcription_provider().transcribe(lecture.audio_url, payload.language)
    except TranscriptionError as error:
        raise HTTPException(status_code=503, detail=str(error))
    if not segments:
        raise HTTPException(status_code=422, detail="No transcript segments were generated")
    return replace_transcript(lecture_id, schemas.TranscriptReplaceRequest(segments=segments), db)
