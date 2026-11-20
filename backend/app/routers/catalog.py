"""Référentiels publics : nécessaires pour choisir son parcours à l'inscription.

Ne contient que des intitulés configurés par l'administrateur, jamais de données élèves."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClassGroup, EducationalCycle, Grade, Track
from app.schemas import CatalogRead

router = APIRouter(prefix="/catalog", tags=["référentiels"])


@router.get("", response_model=CatalogRead)
def read_catalog(db: Session = Depends(get_db)):
    return CatalogRead(
        cycles=list(db.scalars(select(EducationalCycle).order_by(EducationalCycle.name))),
        grades=list(db.scalars(select(Grade).order_by(Grade.sort_order, Grade.name))),
        tracks=list(db.scalars(select(Track).order_by(Track.grade_id, Track.sort_order, Track.name))),
        classes=list(db.scalars(select(ClassGroup).order_by(ClassGroup.academic_year, ClassGroup.name))),
    )
