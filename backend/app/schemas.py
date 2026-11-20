from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


EnrollmentStatus = Literal["none", "pending", "approved", "rejected"]
TrackKind = Literal["serie", "specialite", "option", "filiere"]


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pseudo: str
    grade_id: int | None
    track_id: int | None
    class_id: int | None
    enrollment_status: EnrollmentStatus


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime
    profile: ProfileRead | None = None


class ParcoursFields(StrictModel):
    """Parcours demandé par l'élève : niveau, puis série/spécialité et classe facultatives."""

    grade_id: int | None = Field(default=None, gt=0)
    track_id: int | None = Field(default=None, gt=0)
    class_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def details_require_grade(self):
        if (self.class_id is not None or self.track_id is not None) and self.grade_id is None:
            raise ValueError("grade_id est requis lorsque track_id ou class_id est fourni")
        return self


class RegisterRequest(ParcoursFields):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    pseudo: str = Field(min_length=2, max_length=40, pattern=r"^[\w .-]+$")


class EnrollmentRequest(ParcoursFields):
    grade_id: int = Field(gt=0)


class EnrollmentRead(BaseModel):
    """Vue administrateur d'une demande de parcours (collecte minimale)."""

    model_config = ConfigDict(from_attributes=True)
    user_id: int
    pseudo: str
    grade_id: int | None
    track_id: int | None
    class_id: int | None
    enrollment_status: EnrollmentStatus
    enrollment_requested_at: datetime | None
    enrollment_reviewed_at: datetime | None


class EnrollmentDecision(StrictModel):
    decision: Literal["approve", "reject"]


class TrackCreate(StrictModel):
    grade_id: int = Field(gt=0)
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    kind: TrackKind
    sort_order: int = Field(default=0, ge=0)


class TrackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grade_id: int
    code: str
    name: str
    kind: TrackKind
    sort_order: int


class LoginRequest(StrictModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CycleCreate(StrictModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=100)


class CycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str


class GradeCreate(StrictModel):
    cycle_id: int | None = Field(default=None, gt=0)
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0)


class GradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cycle_id: int | None
    code: str
    name: str
    sort_order: int


class ClassCreate(StrictModel):
    grade_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=80)
    academic_year: str = Field(pattern=r"^\d{4}-\d{4}$")


class ClassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grade_id: int
    name: str
    academic_year: str


class SubjectCreate(StrictModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    is_active: bool


class ChapterCreate(StrictModel):
    grade_id: int = Field(gt=0)
    subject_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=160)
    sort_order: int = Field(default=0, ge=0)


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grade_id: int
    subject_id: int
    title: str
    sort_order: int


class CatalogRead(BaseModel):
    """Référentiels publics nécessaires au choix du parcours (aucune donnée élève)."""

    cycles: list[CycleRead]
    grades: list[GradeRead]
    tracks: list[TrackRead]
    classes: list[ClassRead]
