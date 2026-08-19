from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.admin import require_admin

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)


@router.post("/", response_model=schemas.CategoryResponse)
def create_category(
    category: schemas.CategoryCreate,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db_category = models.Category(
        name=category.name,
    )

    db.add(db_category)
    db.commit()
    db.refresh(db_category)

    return db_category


@router.get("/", response_model=list[schemas.CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()


@router.get(
    "/{category_id}",
    response_model=schemas.CategoryResponse,
)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
):
    category = db.query(models.Category).filter(
        models.Category.id == category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found",
        )

    return category


@router.get(
    "/{category_id}/lectures",
    response_model=list[schemas.LectureResponse],
)
def get_category_lectures(
    category_id: int,
    db: Session = Depends(get_db),
):
    category = db.query(models.Category).filter(
        models.Category.id == category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found",
        )

    return db.query(models.Lecture).filter(
        models.Lecture.category_id == category_id,
        models.Lecture.media_type == "audio",
        models.Lecture.audio_url.isnot(None),
    ).all()
