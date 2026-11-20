from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ClassGroup, Grade, StudentProfile, User
from app.schemas import LoginRequest, RegisterRequest, TokenRead, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentification"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="Cette adresse e-mail est dj utilise")
    if db.scalar(select(StudentProfile.user_id).where(StudentProfile.pseudo == payload.pseudo)) is not None:
        raise HTTPException(status_code=409, detail="Ce pseudo est dj utilis")
    if payload.grade_id is not None and db.get(Grade, payload.grade_id) is None:
        raise HTTPException(status_code=404, detail="Niveau introuvable")
    if payload.class_id is not None:
        class_group = db.get(ClassGroup, payload.class_id)
        if class_group is None or class_group.grade_id != payload.grade_id:
            raise HTTPException(status_code=422, detail="La classe ne correspond pas au niveau fourni")

    user = User(email=email, password_hash=hash_password(payload.password), role="student", is_active=True)
    user.profile = StudentProfile(pseudo=payload.pseudo, grade_id=payload.grade_id, class_id=payload.class_id)
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
        raise HTTPException(status_code=403, detail="Compte dsactiv")
    token, expires_in = create_access_token(user.id)
    return TokenRead(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user
