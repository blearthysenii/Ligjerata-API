from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.admin import require_admin

router = APIRouter(
    prefix="/speakers",
    tags=["Speakers"],
)


@router.post("/", response_model=schemas.SpeakerResponse)
def create_speaker(
    speaker: schemas.SpeakerCreate,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db_speaker = models.Speaker(
        name=speaker.name,
        bio=speaker.bio,
    )

    db.add(db_speaker)
    db.commit()
    db.refresh(db_speaker)

    return db_speaker


@router.get("/", response_model=list[schemas.SpeakerResponse])
def get_speakers(db: Session = Depends(get_db)):
    return db.query(models.Speaker).all()


@router.get(
    "/{speaker_id}",
    response_model=schemas.SpeakerResponse,
)
def get_speaker(
    speaker_id: int,
    db: Session = Depends(get_db),
):
    speaker = db.query(models.Speaker).filter(
        models.Speaker.id == speaker_id
    ).first()

    if not speaker:
        raise HTTPException(
            status_code=404,
            detail="Speaker not found",
        )

    return speaker


@router.get(
    "/{speaker_id}/lectures",
    response_model=list[schemas.LectureResponse],
)
def get_speaker_lectures(
    speaker_id: int,
    db: Session = Depends(get_db),
):
    speaker = db.query(models.Speaker).filter(
        models.Speaker.id == speaker_id
    ).first()

    if not speaker:
        raise HTTPException(
            status_code=404,
            detail="Speaker not found",
        )

    return db.query(models.Lecture).filter(
        models.Lecture.speaker_id == speaker_id,
        models.Lecture.media_type == "audio",
        models.Lecture.audio_url.isnot(None),
    ).all()
