from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/speakers",
    tags=["Speakers"],
)


@router.post("/", response_model=schemas.SpeakerResponse)
def create_speaker(
    speaker: schemas.SpeakerCreate,
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