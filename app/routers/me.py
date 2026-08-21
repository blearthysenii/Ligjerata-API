from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_user
from app.core.admin import is_admin_email
from app.core.security import hash_password, verify_password


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
    "/history",
    response_model=list[schemas.ListeningProgressResponse],
)
def get_listening_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated user's recently played lectures."""
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
        .limit(100)
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

    previous_position = progress.position_seconds if progress else 0

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

    listened_delta = min(max(position - previous_position, 0), 60)
    if listened_delta:
        activity = db.query(models.ListeningActivity).filter_by(
            user_id=current_user.id,
            lecture_id=lecture_id,
            activity_date=date.today(),
        ).first()
        if activity:
            activity.seconds_listened += listened_delta
        else:
            db.add(models.ListeningActivity(
                user_id=current_user.id,
                lecture_id=lecture_id,
                activity_date=date.today(),
                seconds_listened=listened_delta,
            ))

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


@router.post("/push-tokens", response_model=schemas.PushTokenResponse)
def register_push_token(
    payload: schemas.PushTokenCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(models.PushToken).filter(models.PushToken.token == payload.token).first()
    if device:
        device.user_id = current_user.id
        device.platform = payload.platform
    else:
        device = models.PushToken(user_id=current_user.id, **payload.model_dump())
        db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.delete("/push-tokens", status_code=status.HTTP_204_NO_CONTENT)
def unregister_push_token(
    payload: schemas.PushTokenCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.PushToken).filter(
        models.PushToken.user_id == current_user.id,
        models.PushToken.token == payload.token,
    ).delete()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/followed-speakers", response_model=list[schemas.FollowedSpeakerResponse])
def followed_speakers(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.FollowedSpeaker).options(joinedload(models.FollowedSpeaker.speaker)).filter(
        models.FollowedSpeaker.user_id == current_user.id
    ).order_by(models.FollowedSpeaker.created_at.desc()).all()


@router.post("/followed-speakers/{speaker_id}", response_model=schemas.FollowedSpeakerResponse)
def follow_speaker(speaker_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    speaker = db.query(models.Speaker).filter(models.Speaker.id == speaker_id).first()
    if not speaker: raise HTTPException(status_code=404, detail="Speaker not found")
    follow = db.query(models.FollowedSpeaker).filter_by(user_id=current_user.id, speaker_id=speaker_id).first()
    if not follow:
        follow = models.FollowedSpeaker(user_id=current_user.id, speaker_id=speaker_id)
        db.add(follow); db.commit(); db.refresh(follow)
    return follow


@router.delete("/followed-speakers/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_speaker(speaker_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.FollowedSpeaker).filter_by(user_id=current_user.id, speaker_id=speaker_id).delete()
    db.commit(); return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/followed-categories", response_model=list[schemas.FollowedCategoryResponse])
def followed_categories(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.FollowedCategory).options(joinedload(models.FollowedCategory.category)).filter(
        models.FollowedCategory.user_id == current_user.id
    ).order_by(models.FollowedCategory.created_at.desc()).all()


@router.post("/followed-categories/{category_id}", response_model=schemas.FollowedCategoryResponse)
def follow_category(category_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category: raise HTTPException(status_code=404, detail="Category not found")
    follow = db.query(models.FollowedCategory).filter_by(user_id=current_user.id, category_id=category_id).first()
    if not follow:
        follow = models.FollowedCategory(user_id=current_user.id, category_id=category_id)
        db.add(follow); db.commit(); db.refresh(follow)
    return follow


@router.delete("/followed-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_category(category_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.FollowedCategory).filter_by(user_id=current_user.id, category_id=category_id).delete()
    db.commit(); return Response(status_code=status.HTTP_204_NO_CONTENT)


def lecture_join_options(model):
    return (
        joinedload(model.lecture).joinedload(models.Lecture.speaker),
        joinedload(model.lecture).joinedload(models.Lecture.category),
    )


@router.get("/bookmarks", response_model=list[schemas.BookmarkResponse])
def get_bookmarks(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.LectureBookmark).options(*lecture_join_options(models.LectureBookmark)).filter(
        models.LectureBookmark.user_id == current_user.id
    ).order_by(models.LectureBookmark.created_at.desc()).all()


@router.get("/bookmarks/{lecture_id}", response_model=list[schemas.BookmarkResponse])
def get_lecture_bookmarks(lecture_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.LectureBookmark).options(*lecture_join_options(models.LectureBookmark)).filter(
        models.LectureBookmark.user_id == current_user.id,
        models.LectureBookmark.lecture_id == lecture_id,
    ).order_by(models.LectureBookmark.position_seconds).all()


@router.post("/bookmarks/{lecture_id}", response_model=schemas.BookmarkResponse, status_code=201)
def create_bookmark(lecture_id: int, payload: schemas.BookmarkCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    lecture = get_lecture_or_404(lecture_id, db)
    position = min(payload.position_seconds, lecture.duration_seconds or payload.position_seconds)
    item = models.LectureBookmark(
        user_id=current_user.id,
        lecture_id=lecture_id,
        position_seconds=position,
        label=payload.label.strip() if payload.label else None,
    )
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(bookmark_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.LectureBookmark).filter_by(id=bookmark_id, user_id=current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    db.delete(item); db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notes", response_model=list[schemas.NoteResponse])
def get_notes(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.LectureNote).options(*lecture_join_options(models.LectureNote)).filter(
        models.LectureNote.user_id == current_user.id
    ).order_by(models.LectureNote.created_at.desc()).all()


@router.get("/notes/{lecture_id}", response_model=list[schemas.NoteResponse])
def get_lecture_notes(lecture_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.LectureNote).options(*lecture_join_options(models.LectureNote)).filter(
        models.LectureNote.user_id == current_user.id,
        models.LectureNote.lecture_id == lecture_id,
    ).order_by(models.LectureNote.position_seconds).all()


@router.post("/notes/{lecture_id}", response_model=schemas.NoteResponse, status_code=201)
def create_note(lecture_id: int, payload: schemas.NoteCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    lecture = get_lecture_or_404(lecture_id, db)
    item = models.LectureNote(
        user_id=current_user.id,
        lecture_id=lecture_id,
        position_seconds=min(payload.position_seconds, lecture.duration_seconds or payload.position_seconds),
        text=payload.text.strip(),
    )
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/notes/{note_id}", response_model=schemas.NoteResponse)
def update_note(note_id: int, payload: schemas.NoteUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.LectureNote).filter_by(id=note_id, user_id=current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    item.text = payload.text.strip(); db.commit(); db.refresh(item)
    return item


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(models.LectureNote).filter_by(id=note_id, user_id=current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(item); db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/listening-stats", response_model=schemas.ListeningStatsResponse)
def listening_stats(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    rows = db.query(
        models.ListeningActivity.activity_date,
        func.sum(models.ListeningActivity.seconds_listened).label("seconds"),
    ).filter(models.ListeningActivity.user_id == current_user.id).group_by(
        models.ListeningActivity.activity_date
    ).order_by(models.ListeningActivity.activity_date).all()
    by_day = {row.activity_date: int(row.seconds or 0) for row in rows if int(row.seconds or 0) > 0}
    active_days = sorted(by_day)
    longest = current = 0
    previous = None
    for active_day in active_days:
        current = current + 1 if previous and active_day == previous + timedelta(days=1) else 1
        longest = max(longest, current); previous = active_day
    current_streak = 0
    cursor = today if today in by_day else today - timedelta(days=1)
    while cursor in by_day:
        current_streak += 1; cursor -= timedelta(days=1)
    completed = db.query(models.ListeningProgress).filter_by(user_id=current_user.id, completed=True).count()
    return {
        "today_minutes": by_day.get(today, 0) // 60,
        "week_minutes": sum(seconds for day, seconds in by_day.items() if week_start <= day <= today) // 60,
        "current_streak": current_streak,
        "longest_streak": longest,
        "completed_lectures": completed,
        "active_days_this_week": sum(1 for day in by_day if week_start <= day <= today),
    }


@router.put("/profile", response_model=schemas.UserResponse)
def update_profile(payload: schemas.ProfileUpdateRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.full_name = payload.full_name
    db.commit(); db.refresh(current_user)
    return schemas.UserResponse(
        id=current_user.id, full_name=current_user.full_name, email=current_user.email,
        is_active=current_user.is_active, is_admin=is_admin_email(current_user.email), created_at=current_user.created_at,
    )


@router.put("/password", response_model=schemas.MessageResponse)
def change_password(payload: schemas.ChangePasswordRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Fjalëkalimi aktual nuk është i saktë.")
    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Fjalëkalimi i ri duhet të jetë ndryshe.")
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return schemas.MessageResponse(message="Fjalëkalimi u ndryshua me sukses.")


@router.delete("/account", response_model=schemas.MessageResponse)
def delete_account(payload: schemas.DeleteAccountRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if is_admin_email(current_user.email):
        raise HTTPException(status_code=409, detail="Llogaria admin nuk mund të fshihet nga aplikacioni.")
    if payload.confirmation.strip().upper() != "FSHI LLOGARINE":
        raise HTTPException(status_code=400, detail="Shkruaj FSHI LLOGARINE për të konfirmuar.")
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Fjalëkalimi aktual nuk është i saktë.")
    db.delete(current_user); db.commit()
    return schemas.MessageResponse(message="Llogaria u fshi me sukses.")
