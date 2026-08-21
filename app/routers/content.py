from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db


router = APIRouter(tags=["Series, topics and transcripts"])


def series_response(item: models.Series, count: int) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "cover_image_url": item.cover_image_url,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "lecture_count": count,
    }


def active_series_or_404(series_id: int, db: Session) -> models.Series:
    item = db.query(models.Series).filter(
        models.Series.id == series_id,
        models.Series.is_active.is_(True),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Series not found")
    return item


@router.get("/series", response_model=list[schemas.SeriesResponse])
def list_series(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Series)
        .filter(models.Series.is_active.is_(True))
        .order_by(models.Series.updated_at.desc())
        .all()
    )
    return [series_response(item, len(item.lectures)) for item in rows]


@router.get("/series/{series_id}", response_model=schemas.SeriesResponse)
def get_series(series_id: int, db: Session = Depends(get_db)):
    item = active_series_or_404(series_id, db)
    return series_response(item, len(item.lectures))


@router.get("/series/{series_id}/lectures", response_model=list[schemas.SeriesLectureItem])
def get_series_lectures(series_id: int, db: Session = Depends(get_db)):
    active_series_or_404(series_id, db)
    return (
        db.query(models.SeriesLecture)
        .join(models.SeriesLecture.lecture)
        .options(
            joinedload(models.SeriesLecture.lecture).joinedload(models.Lecture.speaker),
            joinedload(models.SeriesLecture.lecture).joinedload(models.Lecture.category),
        )
        .filter(
            models.SeriesLecture.series_id == series_id,
            models.Lecture.media_type == "audio",
            models.Lecture.audio_url.isnot(None),
        )
        .order_by(models.SeriesLecture.order_index)
        .all()
    )


@router.get("/topics", response_model=list[schemas.TopicResponse])
def list_topics(db: Session = Depends(get_db)):
    return db.query(models.Topic).filter(models.Topic.is_active.is_(True)).order_by(models.Topic.name).all()


@router.get("/topics/{topic_id}", response_model=schemas.TopicResponse)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(models.Topic).filter(models.Topic.id == topic_id, models.Topic.is_active.is_(True)).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.get("/topics/{topic_id}/lectures", response_model=list[schemas.LectureResponse])
def get_topic_lectures(topic_id: int, db: Session = Depends(get_db)):
    get_topic(topic_id, db)
    return (
        db.query(models.Lecture)
        .join(models.LectureTopic, models.LectureTopic.lecture_id == models.Lecture.id)
        .options(joinedload(models.Lecture.speaker), joinedload(models.Lecture.category))
        .filter(
            models.LectureTopic.topic_id == topic_id,
            models.Lecture.media_type == "audio",
            models.Lecture.audio_url.isnot(None),
        )
        .order_by(models.Lecture.id.desc())
        .all()
    )


@router.get("/lectures/{lecture_id}/topics", response_model=list[schemas.TopicResponse])
def get_lecture_topics(lecture_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Topic)
        .join(models.LectureTopic, models.LectureTopic.topic_id == models.Topic.id)
        .filter(models.LectureTopic.lecture_id == lecture_id, models.Topic.is_active.is_(True))
        .order_by(models.Topic.name)
        .all()
    )


@router.get("/lectures/{lecture_id}/transcript", response_model=list[schemas.TranscriptSegmentResponse])
def get_transcript(lecture_id: int, db: Session = Depends(get_db)):
    exists = db.query(models.Lecture.id).filter(models.Lecture.id == lecture_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return db.query(models.LectureTranscriptSegment).filter(
        models.LectureTranscriptSegment.lecture_id == lecture_id
    ).order_by(models.LectureTranscriptSegment.start_seconds).all()


@router.get("/search", response_model=list[schemas.TranscriptSearchResult])
def search_content(q: str = Query(min_length=2, max_length=100), db: Session = Depends(get_db)):
    pattern = f"%{q.strip()}%"
    base = (
        db.query(models.Lecture)
        .options(joinedload(models.Lecture.speaker), joinedload(models.Lecture.category))
        .filter(models.Lecture.media_type == "audio", models.Lecture.audio_url.isnot(None))
    )
    metadata = (
        base.outerjoin(models.LectureTopic, models.LectureTopic.lecture_id == models.Lecture.id)
        .outerjoin(models.Topic, models.Topic.id == models.LectureTopic.topic_id)
        .join(models.Lecture.speaker)
        .join(models.Lecture.category)
        .filter(or_(
            models.Lecture.title.ilike(pattern),
            models.Speaker.name.ilike(pattern),
            models.Category.name.ilike(pattern),
            models.Topic.name.ilike(pattern),
        ))
        .distinct()
        .limit(30)
        .all()
    )
    results = [{"lecture": lecture, "snippet": lecture.description or lecture.title, "timestamp_seconds": 0} for lecture in metadata]
    seen = {(lecture.id, 0) for lecture in metadata}
    transcript_rows = (
        db.query(models.LectureTranscriptSegment)
        .join(models.LectureTranscriptSegment.lecture)
        .options(
            joinedload(models.LectureTranscriptSegment.lecture).joinedload(models.Lecture.speaker),
            joinedload(models.LectureTranscriptSegment.lecture).joinedload(models.Lecture.category),
        )
        .filter(
            models.LectureTranscriptSegment.text.ilike(pattern),
            models.Lecture.media_type == "audio",
            models.Lecture.audio_url.isnot(None),
        )
        .order_by(models.LectureTranscriptSegment.lecture_id, models.LectureTranscriptSegment.start_seconds)
        .limit(50)
        .all()
    )
    for segment in transcript_rows:
        key = (segment.lecture_id, segment.start_seconds)
        if key not in seen:
            results.append({"lecture": segment.lecture, "snippet": segment.text, "timestamp_seconds": segment.start_seconds})
            seen.add(key)
    return results[:60]
