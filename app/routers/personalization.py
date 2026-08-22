from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.routers.auth import get_current_user

router = APIRouter(prefix="/me", tags=["Personalization"])


def preference(db: Session, user_id: int) -> models.UserPreference:
    row = db.query(models.UserPreference).filter_by(user_id=user_id).first()
    if not row:
        row = models.UserPreference(user_id=user_id)
        db.add(row); db.commit(); db.refresh(row)
    return row


@router.get("/onboarding", response_model=schemas.OnboardingResponse)
def get_onboarding(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return preference(db, user.id)


@router.put("/onboarding", response_model=schemas.OnboardingResponse)
def update_onboarding(payload: schemas.OnboardingUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = preference(db, user.id)
    row.listening_frequency = payload.listening_frequency
    row.onboarding_completed = payload.onboarding_completed
    db.query(models.FollowedCategory).filter_by(user_id=user.id).delete()
    db.query(models.FollowedSpeaker).filter_by(user_id=user.id).delete()
    db.query(models.FollowedTopic).filter_by(user_id=user.id).delete()
    valid_categories = {x[0] for x in db.query(models.Category.id).filter(models.Category.id.in_(payload.category_ids)).all()}
    valid_speakers = {x[0] for x in db.query(models.Speaker.id).filter(models.Speaker.id.in_(payload.speaker_ids)).all()}
    valid_topics = {x[0] for x in db.query(models.Topic.id).filter(models.Topic.id.in_(payload.topic_ids)).all()}
    db.add_all([models.FollowedCategory(user_id=user.id, category_id=x) for x in valid_categories])
    db.add_all([models.FollowedSpeaker(user_id=user.id, speaker_id=x) for x in valid_speakers])
    db.add_all([models.FollowedTopic(user_id=user.id, topic_id=x) for x in valid_topics])
    db.commit(); db.refresh(row)
    return row


def owned_playlist(db: Session, user_id: int, playlist_id: int) -> models.UserPlaylist:
    row = db.query(models.UserPlaylist).options(joinedload(models.UserPlaylist.lectures).joinedload(models.UserPlaylistLecture.lecture).joinedload(models.Lecture.speaker), joinedload(models.UserPlaylist.lectures).joinedload(models.UserPlaylistLecture.lecture).joinedload(models.Lecture.category)).filter_by(id=playlist_id, user_id=user_id).first()
    if not row: raise HTTPException(status_code=404, detail="Playlist-a nuk u gjet.")
    return row


@router.get("/playlists", response_model=list[schemas.PlaylistResponse])
def playlists(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.UserPlaylist).options(joinedload(models.UserPlaylist.lectures).joinedload(models.UserPlaylistLecture.lecture).joinedload(models.Lecture.speaker), joinedload(models.UserPlaylist.lectures).joinedload(models.UserPlaylistLecture.lecture).joinedload(models.Lecture.category)).filter_by(user_id=user.id).order_by(models.UserPlaylist.updated_at.desc()).all()


@router.post("/playlists", response_model=schemas.PlaylistResponse, status_code=201)
def create_playlist(payload: schemas.PlaylistCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = models.UserPlaylist(user_id=user.id, title=payload.title.strip(), description=payload.description.strip() if payload.description else None)
    db.add(row); db.commit(); db.refresh(row); return row


@router.get("/playlists/{playlist_id}", response_model=schemas.PlaylistResponse)
def playlist(playlist_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return owned_playlist(db, user.id, playlist_id)


@router.put("/playlists/{playlist_id}", response_model=schemas.PlaylistResponse)
def update_playlist(playlist_id: int, payload: schemas.PlaylistUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned_playlist(db, user.id, playlist_id); row.title = payload.title.strip(); row.description = payload.description.strip() if payload.description else None
    db.commit(); return owned_playlist(db, user.id, playlist_id)


@router.delete("/playlists/{playlist_id}", status_code=204)
def delete_playlist(playlist_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned_playlist(db, user.id, playlist_id); db.delete(row); db.commit(); return Response(status_code=204)


@router.post("/playlists/{playlist_id}/lectures/{lecture_id}", response_model=schemas.PlaylistResponse)
def add_playlist_lecture(playlist_id: int, lecture_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    owned_playlist(db, user.id, playlist_id)
    if not db.query(models.Lecture.id).filter_by(id=lecture_id).first(): raise HTTPException(status_code=404, detail="Ligjërata nuk u gjet.")
    exists = db.query(models.UserPlaylistLecture).filter_by(playlist_id=playlist_id, lecture_id=lecture_id).first()
    if not exists:
        order = db.query(func.coalesce(func.max(models.UserPlaylistLecture.order_index), -1)).filter_by(playlist_id=playlist_id).scalar() + 1
        db.add(models.UserPlaylistLecture(playlist_id=playlist_id, lecture_id=lecture_id, order_index=order)); db.commit()
    return owned_playlist(db, user.id, playlist_id)


@router.delete("/playlists/{playlist_id}/lectures/{lecture_id}", status_code=204)
def remove_playlist_lecture(playlist_id: int, lecture_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    owned_playlist(db, user.id, playlist_id)
    db.query(models.UserPlaylistLecture).filter_by(playlist_id=playlist_id, lecture_id=lecture_id).delete(); db.commit()
    rows = db.query(models.UserPlaylistLecture).filter_by(playlist_id=playlist_id).order_by(models.UserPlaylistLecture.order_index).all()
    for index, row in enumerate(rows): row.order_index = index
    db.commit(); return Response(status_code=204)


@router.put("/playlists/{playlist_id}/reorder", response_model=schemas.PlaylistResponse)
def reorder_playlist(playlist_id: int, payload: schemas.PlaylistReorder, user=Depends(get_current_user), db: Session = Depends(get_db)):
    owned_playlist(db, user.id, playlist_id)
    rows = db.query(models.UserPlaylistLecture).filter_by(playlist_id=playlist_id).all()
    if set(payload.lecture_ids) != {row.lecture_id for row in rows} or len(payload.lecture_ids) != len(set(payload.lecture_ids)):
        raise HTTPException(status_code=400, detail="Renditja duhet të përmbajë të gjitha ligjëratat një herë.")
    by_id = {row.lecture_id: row for row in rows}
    for index, lecture_id in enumerate(payload.lecture_ids): by_id[lecture_id].order_index = -(index + 1)
    db.flush()
    for index, lecture_id in enumerate(payload.lecture_ids): by_id[lecture_id].order_index = index
    db.commit(); return owned_playlist(db, user.id, playlist_id)


def notification_preference(db: Session, user_id: int):
    row = db.query(models.NotificationPreference).filter_by(user_id=user_id).first()
    if not row: row = models.NotificationPreference(user_id=user_id); db.add(row); db.commit(); db.refresh(row)
    return row


@router.get("/notification-preferences", response_model=schemas.NotificationPreferenceResponse)
def get_notification_preferences(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return notification_preference(db, user.id)


@router.put("/notification-preferences", response_model=schemas.NotificationPreferenceResponse)
def update_notification_preferences(payload: schemas.NotificationPreferenceUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = notification_preference(db, user.id)
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    db.commit(); db.refresh(row); return row


@router.get("/lecture-feedback/{lecture_id}", response_model=schemas.FeedbackResponse)
def get_feedback(lecture_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(models.LectureFeedback).filter_by(user_id=user.id, lecture_id=lecture_id).first()
    if not row: raise HTTPException(status_code=404, detail="Feedback-u nuk u gjet.")
    return row


@router.put("/lecture-feedback/{lecture_id}", response_model=schemas.FeedbackResponse)
def put_feedback(lecture_id: int, payload: schemas.FeedbackUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.query(models.Lecture.id).filter_by(id=lecture_id).first(): raise HTTPException(status_code=404, detail="Ligjërata nuk u gjet.")
    row = db.query(models.LectureFeedback).filter_by(user_id=user.id, lecture_id=lecture_id).first()
    if row: row.value = payload.value
    else: row = models.LectureFeedback(user_id=user.id, lecture_id=lecture_id, value=payload.value); db.add(row)
    db.commit(); db.refresh(row); return row


@router.delete("/lecture-feedback/{lecture_id}", status_code=204)
def delete_feedback(lecture_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.LectureFeedback).filter_by(user_id=user.id, lecture_id=lecture_id).delete(); db.commit(); return Response(status_code=204)


@router.get("/recommendations", response_model=list[schemas.LectureResponse])
def recommendations(limit: int = 15, user=Depends(get_current_user), db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 30)
    lectures = db.query(models.Lecture).options(joinedload(models.Lecture.speaker), joinedload(models.Lecture.category), joinedload(models.Lecture.topic_memberships)).filter(models.Lecture.media_type == "audio", models.Lecture.audio_url.isnot(None)).order_by(models.Lecture.id.desc()).limit(200).all()
    speaker_ids = {x[0] for x in db.query(models.FollowedSpeaker.speaker_id).filter_by(user_id=user.id)}
    category_ids = {x[0] for x in db.query(models.FollowedCategory.category_id).filter_by(user_id=user.id)}
    topic_ids = {x[0] for x in db.query(models.FollowedTopic.topic_id).filter_by(user_id=user.id)}
    saved_ids = {x[0] for x in db.query(models.SavedLecture.lecture_id).filter_by(user_id=user.id)}
    completed_ids = {x[0] for x in db.query(models.ListeningProgress.lecture_id).filter_by(user_id=user.id, completed=True)}
    feedback = {x.lecture_id: x.value for x in db.query(models.LectureFeedback).filter_by(user_id=user.id)}
    playlist_ids = {x[0] for x in db.query(models.UserPlaylistLecture.lecture_id).join(models.UserPlaylist).filter(models.UserPlaylist.user_id == user.id)}
    positive_source_ids = saved_ids | completed_ids | playlist_ids | {lecture_id for lecture_id, value in feedback.items() if value == "helpful"}
    negative_source_ids = {lecture_id for lecture_id, value in feedback.items() if value == "not_for_me"}
    affinity_rows = db.query(models.Lecture.id, models.Lecture.speaker_id, models.Lecture.category_id).filter(models.Lecture.id.in_(positive_source_ids)).all() if positive_source_ids else []
    negative_rows = db.query(models.Lecture.id, models.Lecture.speaker_id, models.Lecture.category_id).filter(models.Lecture.id.in_(negative_source_ids)).all() if negative_source_ids else []
    affinity_speakers = {row.speaker_id for row in affinity_rows}
    affinity_categories = {row.category_id for row in affinity_rows}
    negative_speakers = {row.speaker_id for row in negative_rows}
    negative_categories = {row.category_id for row in negative_rows}
    popular = dict(db.query(models.ListeningProgress.lecture_id, func.count(models.ListeningProgress.id)).group_by(models.ListeningProgress.lecture_id).all())
    scored = []
    for lecture in lectures:
        score = min(popular.get(lecture.id, 0), 20) + max(0, 20 - (lectures[0].id - lecture.id if lectures else 0))
        if lecture.speaker_id in speaker_ids: score += 50
        if lecture.category_id in category_ids: score += 40
        if any(x.topic_id in topic_ids for x in lecture.topic_memberships): score += 45
        if lecture.speaker_id in affinity_speakers: score += 16
        if lecture.category_id in affinity_categories: score += 12
        if lecture.speaker_id in negative_speakers: score -= 5
        if lecture.category_id in negative_categories: score -= 4
        if lecture.id in saved_ids: score += 8
        if lecture.id in playlist_ids: score += 7
        if lecture.id in completed_ids: score -= 35
        if feedback.get(lecture.id) == "helpful": score += 18
        if feedback.get(lecture.id) == "not_for_me": score -= 45
        scored.append((score, lecture))
    scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
    result = []
    speaker_counts = {}
    category_counts = {}
    for _, lecture in scored:
        if len(result) >= limit: break
        if len(result) >= 2 and result[-1].speaker_id == result[-2].speaker_id == lecture.speaker_id: continue
        if len(result) >= 2 and result[-1].category_id == result[-2].category_id == lecture.category_id: continue
        if speaker_counts.get(lecture.speaker_id, 0) >= max(2, limit // 3): continue
        if category_counts.get(lecture.category_id, 0) >= max(3, limit // 2): continue
        result.append(lecture)
        speaker_counts[lecture.speaker_id] = speaker_counts.get(lecture.speaker_id, 0) + 1
        category_counts[lecture.category_id] = category_counts.get(lecture.category_id, 0) + 1
    return result
