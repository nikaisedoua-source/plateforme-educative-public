"""Règles communes du parcours élève (niveau → série/spécialité → classe)."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import ClassGroup, Grade, Track


def check_parcours(db: Session, grade_id: int | None, track_id: int | None, class_id: int | None) -> None:
    """Refuse un parcours incohérent : la série et la classe doivent appartenir au niveau choisi."""
    if grade_id is None:
        return
    if db.get(Grade, grade_id) is None:
        raise HTTPException(status_code=404, detail="Niveau introuvable")
    if track_id is not None:
        track = db.get(Track, track_id)
        if track is None or track.grade_id != grade_id:
            raise HTTPException(status_code=422, detail="La série ou spécialité ne correspond pas au niveau choisi")
    if class_id is not None:
        class_group = db.get(ClassGroup, class_id)
        if class_group is None or class_group.grade_id != grade_id:
            raise HTTPException(status_code=422, detail="La classe ne correspond pas au niveau choisi")
