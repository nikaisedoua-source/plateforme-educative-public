from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import StudentProfile, User
from app.parcours import check_parcours
from app.schemas import EnrollmentRequest, LoginRequest, ProfileRead, RegisterRequest, TokenRead, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentification"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="Cette adresse e-mail est déjà utilisée")
    if db.scalar(select(StudentProfile.user_id).where(StudentProfile.pseudo == payload.pseudo)) is not None:
        raise HTTPException(status_code=409, detail="Ce pseudo est déjà utilisé")
    check_parcours(db, payload.grade_id, payload.track_id, payload.class_id)

    user = User(email=email, password_hash=hash_password(payload.password), role="student", is_active=True)
    requested = payload.grade_id is not None
    user.profile = StudentProfile(
        pseudo=payload.pseudo,
        grade_id=payload.grade_id,
        track_id=payload.track_id,
        class_id=payload.class_id,
        # Le parcours choisi à l'inscription attend la validation d'un administrateur.
        enrollment_status="pending" if requested else "none",
        enrollment_requested_at=datetime.now(UTC) if requested else None,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email ou pseudo indisponible") from None
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenRead)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Identifiants incorrects", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    token, expires_in = create_access_token(user.id)
    return TokenRead(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/me/enrollment", response_model=ProfileRead)
def request_enrollment(
    payload: EnrollmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """L'élève demande à rejoindre (ou changer) de parcours ; la demande repasse en attente de validation."""
    profile = user.profile
    if user.role != "student" or profile is None:
        raise HTTPException(status_code=403, detail="Réservé aux comptes élèves")
    check_parcours(db, payload.grade_id, payload.track_id, payload.class_id)
    profile.grade_id = payload.grade_id
    profile.track_id = payload.track_id
    profile.class_id = payload.class_id
    profile.enrollment_status = "pending"
    profile.enrollment_requested_at = datetime.now(UTC)
    profile.enrollment_reviewed_at = None
    profile.enrollment_reviewed_by = None
    db.commit()
    db.refresh(profile)
    return profile
