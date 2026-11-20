from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Chapter, ClassGroup, EducationalCycle, Grade, StudentProfile, Subject, Track, User
from app.schemas import (
    ChapterCreate, ChapterRead, ClassCreate, ClassRead, CycleCreate, CycleRead,
    EnrollmentDecision, EnrollmentRead, GradeCreate, GradeRead, SubjectCreate, SubjectRead,
    TrackCreate, TrackRead,
)

router = APIRouter(prefix="/admin", tags=["administration"], dependencies=[Depends(require_admin)])


def _save(db: Session, item):
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Un élément avec ces identifiants existe déjà") from None
    db.refresh(item)
    return item


@router.get("/cycles", response_model=list[CycleRead])
def list_cycles(db: Session = Depends(get_db)):
    return list(db.scalars(select(EducationalCycle).order_by(EducationalCycle.name)))


@router.post("/cycles", response_model=CycleRead, status_code=status.HTTP_201_CREATED)
def create_cycle(payload: CycleCreate, db: Session = Depends(get_db)):
    return _save(db, EducationalCycle(**payload.model_dump()))


@router.get("/grades", response_model=list[GradeRead])
def list_grades(db: Session = Depends(get_db)):
    return list(db.scalars(select(Grade).order_by(Grade.sort_order, Grade.name)))


@router.post("/grades", response_model=GradeRead, status_code=status.HTTP_201_CREATED)
def create_grade(payload: GradeCreate, db: Session = Depends(get_db)):
    if payload.cycle_id is not None and db.get(EducationalCycle, payload.cycle_id) is None:
        raise HTTPException(status_code=404, detail="Cycle éducatif introuvable")
    return _save(db, Grade(**payload.model_dump()))


@router.get("/tracks", response_model=list[TrackRead])
def list_tracks(db: Session = Depends(get_db)):
    return list(db.scalars(select(Track).order_by(Track.grade_id, Track.sort_order, Track.name)))


@router.post("/tracks", response_model=TrackRead, status_code=status.HTTP_201_CREATED)
def create_track(payload: TrackCreate, db: Session = Depends(get_db)):
    if db.get(Grade, payload.grade_id) is None:
        raise HTTPException(status_code=404, detail="Niveau introuvable")
    return _save(db, Track(**payload.model_dump()))


@router.get("/classes", response_model=list[ClassRead])
def list_classes(db: Session = Depends(get_db)):
    return list(db.scalars(select(ClassGroup).order_by(ClassGroup.academic_year, ClassGroup.name)))


@router.post("/classes", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    if db.get(Grade, payload.grade_id) is None:
        raise HTTPException(status_code=404, detail="Niveau introuvable")
    return _save(db, ClassGroup(**payload.model_dump()))


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(db: Session = Depends(get_db)):
    return list(db.scalars(select(Subject).order_by(Subject.name)))


@router.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db)):
    return _save(db, Subject(**payload.model_dump()))


@router.get("/chapters", response_model=list[ChapterRead])
def list_chapters(db: Session = Depends(get_db)):
    return list(db.scalars(select(Chapter).order_by(Chapter.grade_id, Chapter.subject_id, Chapter.sort_order)))


@router.post("/chapters", response_model=ChapterRead, status_code=status.HTTP_201_CREATED)
def create_chapter(payload: ChapterCreate, db: Session = Depends(get_db)):
    if db.get(Grade, payload.grade_id) is None:
        raise HTTPException(status_code=404, detail="Niveau introuvable")
    if db.get(Subject, payload.subject_id) is None:
        raise HTTPException(status_code=404, detail="Matière introuvable")
    return _save(db, Chapter(**payload.model_dump()))


@router.get("/enrollments", response_model=list[EnrollmentRead])
def list_enrollments(
    enrollment_status: Literal["pending", "approved", "rejected"] | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    query = select(StudentProfile).where(StudentProfile.enrollment_status != "none")
    if enrollment_status is not None:
        query = query.where(StudentProfile.enrollment_status == enrollment_status)
    return list(db.scalars(query.order_by(StudentProfile.enrollment_requested_at, StudentProfile.user_id)))


@router.post("/enrollments/{user_id}/decision", response_model=EnrollmentRead)
def decide_enrollment(
    user_id: int,
    payload: EnrollmentDecision,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Valide ou refuse l'affectation demandée par l'élève (cahier §13)."""
    profile = db.get(StudentProfile, user_id)
    if profile is None or profile.enrollment_status == "none":
        raise HTTPException(status_code=404, detail="Demande de parcours introuvable")
    if profile.enrollment_status != "pending":
        raise HTTPException(status_code=409, detail="Cette demande a déjà été traitée")
    profile.enrollment_status = "approved" if payload.decision == "approve" else "rejected"
    profile.enrollment_reviewed_at = datetime.now(UTC)
    profile.enrollment_reviewed_by = admin.id
    db.commit()
    db.refresh(profile)
    return profile
