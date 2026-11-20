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


# ---------------------------------------------------------------------------
# Phase 2 — Bibliothèque documentaire
# ---------------------------------------------------------------------------

DocumentKind = Literal["manuel", "fiche", "exercices", "devoir", "examen", "corrige", "revision", "methode", "autre"]
DocumentStatus = Literal["imported", "processing", "extracted", "failed", "archived"]
ContentStatus = Literal["extracted", "transformed", "pending_validation", "validated", "rejected"]
ExerciseType = Literal["libre", "qcm", "vrai_faux", "a_completer", "numerique", "probleme", "etude_de_cas"]


class Classification(StrictModel):
    """Rattachement au parcours : la cohérence niveau/série/matière/chapitre est vérifiée côté serveur."""

    grade_id: int | None = Field(default=None, gt=0)
    track_ids: list[int] | None = Field(default=None, max_length=20)  # séries visées (aucune = à préciser)
    subject_id: int | None = Field(default=None, gt=0)
    chapter_id: int | None = Field(default=None, gt=0)


class DocumentUpdate(Classification):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    kind: DocumentKind | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    original_filename: str
    mime_type: str
    size_bytes: int
    kind: DocumentKind
    status: DocumentStatus
    page_count: int
    pages_done: int
    extraction_error: str | None
    grade_id: int | None
    track_ids: list[int] = []
    subject_id: int | None
    chapter_id: int | None
    imported_at: datetime
    extracted_at: datetime | None


class DocumentPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    page_number: int
    text: str
    method: Literal["text", "ocr", "empty"]


class ExerciseOptionIn(StrictModel):
    label: str = Field(min_length=1, max_length=10)
    text: str = Field(min_length=1, max_length=2000)
    is_correct: bool = False


class ExerciseOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    text: str
    is_correct: bool


class ExerciseAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: Literal["page", "image"]
    page_number: int | None
    caption: str | None


class CorrectionIn(StrictModel):
    original_text: str = Field(default="", max_length=50000)
    final_answer: str | None = Field(default=None, max_length=20000)
    steps: str | None = Field(default=None, max_length=50000)
    rubric: str | None = Field(default=None, max_length=10000)
    source_document_id: int = Field(gt=0)
    source_page: int | None = Field(default=None, gt=0)


class CorrectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    exercise_id: int
    original_text: str
    final_answer: str | None
    steps: str | None
    rubric: str | None
    source_document_id: int
    source_page: int | None
    status: ContentStatus
    validated_at: datetime | None


class ExerciseCreate(Classification):
    document_id: int = Field(gt=0)
    page_start: int = Field(gt=0)
    page_end: int | None = Field(default=None, gt=0)
    source_number: str | None = Field(default=None, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=50000)
    exercise_type: ExerciseType = "libre"
    difficulty: int = Field(default=2, ge=1, le=3)


class ExerciseUpdate(Classification):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    statement: str | None = Field(default=None, min_length=1, max_length=50000)
    source_number: str | None = Field(default=None, max_length=50)
    page_start: int | None = Field(default=None, gt=0)
    page_end: int | None = Field(default=None, gt=0)
    exercise_type: ExerciseType | None = None
    difficulty: int | None = Field(default=None, ge=1, le=3)
    expected_answer: str | None = Field(default=None, max_length=5000)
    numeric_tolerance: float | None = Field(default=None, ge=0)
    points: int | None = Field(default=None, ge=1, le=100)
    sort_order: int | None = Field(default=None, ge=0)
    options: list[ExerciseOptionIn] | None = Field(default=None, max_length=12)


class ExerciseRead(BaseModel):
    """Vue administrateur complète (réponse attendue comprise)."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    page_start: int
    page_end: int
    source_number: str | None
    title: str
    original_text: str
    statement: str
    exercise_type: ExerciseType
    difficulty: int
    expected_answer: str | None
    numeric_tolerance: float | None
    points: int
    grade_id: int | None
    track_ids: list[int] = []
    subject_id: int | None
    chapter_id: int | None
    status: ContentStatus
    is_published: bool
    is_archived: bool
    sort_order: int
    created_at: datetime
    validated_at: datetime | None
    published_at: datetime | None
    options: list[ExerciseOptionRead] = []
    assets: list[ExerciseAssetRead] = []
    correction: CorrectionRead | None = None


class ExerciseAction(StrictModel):
    action: Literal["submit", "validate", "reject", "publish", "unpublish", "archive", "restore"]
    comment: str | None = Field(default=None, max_length=1000)


class ExtractionReport(BaseModel):
    document_id: int
    status: DocumentStatus
    page_count: int


class SegmentReport(BaseModel):
    document_id: int
    exercises_created: int
    corrections_found: int


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    details: dict
    created_at: datetime
