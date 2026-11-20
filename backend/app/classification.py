"""Cohérence du rattachement niveau / série / matière / chapitre (cahier §19 : aucun mélange involontaire)."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Grade, Subject, Track


def check_tracks(db: Session, grade_id: int | None, track_ids: list[int] | None) -> list[Track]:
    """Séries visées : toutes doivent appartenir au niveau (une Tle C n'est pas une 1ère C)."""
    tracks: list[Track] = []
    for track_id in dict.fromkeys(track_ids or []):
        track = db.get(Track, track_id)
        if track is None:
            raise HTTPException(status_code=404, detail="Série ou spécialité introuvable")
        if grade_id is None or track.grade_id != grade_id:
            raise HTTPException(status_code=422, detail="La série ou spécialité ne correspond pas au niveau")
        tracks.append(track)
    return tracks


def grade_has_tracks(db: Session, grade_id: int | None) -> bool:
    return grade_id is not None and db.scalar(select(Track.id).where(Track.grade_id == grade_id).limit(1)) is not None


def check_classification(
    db: Session, grade_id: int | None, subject_id: int | None, chapter_id: int | None
) -> dict[str, int | None]:
    if chapter_id is not None:
        chapter = db.get(Chapter, chapter_id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="Chapitre introuvable")
        if grade_id is not None and grade_id != chapter.grade_id:
            raise HTTPException(status_code=422, detail="Le chapitre n'appartient pas au niveau choisi")
        if subject_id is not None and subject_id != chapter.subject_id:
            raise HTTPException(status_code=422, detail="Le chapitre n'appartient pas à la matière choisie")
        grade_id, subject_id = chapter.grade_id, chapter.subject_id
    if grade_id is not None and db.get(Grade, grade_id) is None:
        raise HTTPException(status_code=404, detail="Niveau introuvable")
    if subject_id is not None and db.get(Subject, subject_id) is None:
        raise HTTPException(status_code=404, detail="Matière introuvable")
    return {"grade_id": grade_id, "subject_id": subject_id, "chapter_id": chapter_id}
