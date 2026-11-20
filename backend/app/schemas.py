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
CorrectionAccess = Literal["always", "after_attempt", "after_success_or_attempts", "never"]
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
    correction_access: CorrectionAccess | None = None


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
    correction_access: CorrectionAccess | None = None
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


# --------------------------------------------------------------------------- phase 3 : espace élève


class PublicationSettings(StrictModel):
    auto: bool


class CorrectionAccessSettings(StrictModel):
    """Règle générale d'accès aux corrigés (un exercice peut avoir sa propre règle)."""

    mode: CorrectionAccess = "after_attempt"
    attempts: int = Field(default=2, ge=1, le=10)


class StudentChapter(BaseModel):
    id: int
    title: str
    exercise_count: int


class StudentSubject(BaseModel):
    id: int
    name: str
    exercise_count: int
    chapters: list[StudentChapter]


class StudentExerciseSummary(BaseModel):
    id: int
    title: str
    exercise_type: ExerciseType
    difficulty: int
    points: int
    subject_id: int | None
    chapter_id: int | None
    attempts: int
    best_score: float | None
    solved: bool


class StudentOption(BaseModel):
    id: int
    label: str
    text: str


class StudentAsset(BaseModel):
    id: int
    kind: Literal["page", "image"]
    caption: str | None


class StudentAttemptHistory(BaseModel):
    result: str
    score: float
    created_at: datetime
    after_correction: bool


class StudentQuestion(BaseModel):
    """Question d'un exercice. `checkable` : le serveur peut vérifier un résultat (jamais envoyé ici)."""

    id: int
    label: str
    text: str
    kind: Literal["result", "proof"]
    checkable: bool
    last_result: str | None
    last_answer: str | None


class StudentExercise(StudentExerciseSummary):
    """Vue élève : jamais la bonne réponse ni le corrigé (servis à part, selon la règle d'accès).
    `statement` : énoncé réécrit en LaTeX quand il existe, sinon l'extraction ; `original_first` : la réécriture
    est absente ou douteuse, l'image originale du document est alors montrée en premier."""

    statement: str
    rewrite_status: str
    original_first: bool
    original_pages: list[int]
    questions: list[StudentQuestion]
    options: list[StudentOption]
    assets: list[StudentAsset]
    source: str
    correction_available: bool
    correction_rule: str
    history: list[StudentAttemptHistory]


class AttemptIn(StrictModel):
    answer_text: str | None = Field(default=None, max_length=5000)
    option_ids: list[int] | None = Field(default=None, max_length=12)


class AttemptResult(BaseModel):
    result: Literal["correct", "incorrect", "partial", "submitted"]
    score: float
    max_score: int
    message: str
    after_correction: bool
    correction_available: bool
    correction_rule: str


class StudentCorrection(BaseModel):
    final_answer: str | None
    steps: str | None
    text_latex: str | None = None
    source: str | None
    correct_option_ids: list[int]
    expected_answer: str | None
    question_answers: dict[str, str] = Field(default_factory=dict)


class QuestionAttemptIn(StrictModel):
    answer_latex: str | None = Field(default=None, max_length=5000)
    self_check: Literal["self_ok", "self_review"] | None = None


class QuestionAttemptResult(BaseModel):
    result: Literal["correct", "incorrect", "submitted", "self_ok", "self_review"]
    message: str
    after_correction: bool
    correction_available: bool
    correction_rule: str


# --------------------------------------------------------------------------- Phase 4 : mémorisation et révisions

FlashcardType = Literal["question", "definition", "formule", "vrai_faux", "a_completer", "numerique"]
MethodCategory = Literal["rappel", "comprehension", "mnemotechnique", "organisation"]


class FlashcardCreate(Classification):
    """Une carte garde toujours sa source : un document (et sa page) ou un exercice de ce document."""

    document_id: int | None = Field(default=None, gt=0)
    exercise_id: int | None = Field(default=None, gt=0)
    page_number: int | None = Field(default=None, gt=0)
    card_type: FlashcardType = "question"
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=8000)
    hint: str | None = Field(default=None, max_length=1000)
    original_text: str | None = Field(default=None, max_length=8000)
    numeric_tolerance: float | None = Field(default=None, ge=0)
    difficulty: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def _source(self):
        if self.document_id is None and self.exercise_id is None:
            raise ValueError("Indiquer le document source ou l'exercice source")
        return self


class FlashcardUpdate(Classification):
    page_number: int | None = Field(default=None, gt=0)
    card_type: FlashcardType | None = None
    question: str | None = Field(default=None, min_length=1, max_length=4000)
    answer: str | None = Field(default=None, min_length=1, max_length=8000)
    hint: str | None = Field(default=None, max_length=1000)
    numeric_tolerance: float | None = Field(default=None, ge=0)
    difficulty: int | None = Field(default=None, ge=1, le=3)


class FlashcardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    page_number: int | None
    exercise_id: int | None
    card_type: str
    question: str
    answer: str
    hint: str | None
    original_text: str
    numeric_tolerance: float | None
    difficulty: int
    grade_id: int | None
    track_ids: list[int] = []
    subject_id: int | None
    chapter_id: int | None
    status: str
    is_published: bool
    is_archived: bool
    created_at: datetime
    validated_at: datetime | None


class ProposalReport(BaseModel):
    document_id: int
    found: int
    created: int
    already_present: int


class MethodExampleIn(StrictModel):
    document_id: int | None = Field(default=None, gt=0)
    page_number: int | None = Field(default=None, gt=0)
    exercise_id: int | None = Field(default=None, gt=0)
    flashcard_id: int | None = Field(default=None, gt=0)
    note: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def _source(self):
        if self.document_id is None and self.exercise_id is None and self.flashcard_id is None:
            raise ValueError("Un exemple doit venir d'un document, d'un exercice ou d'une carte mémoire")
        return self


class MethodExampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    page_number: int | None
    exercise_id: int | None
    flashcard_id: int | None
    note: str
    source: str = ""


class MethodUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=2000)
    principle: str | None = Field(default=None, max_length=8000)
    steps: list[str] | None = Field(default=None, max_length=20)


class MethodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    category: str
    summary: str
    principle: str | None
    steps: list[str]
    status: str
    sort_order: int
    examples: list[MethodExampleRead] = []


class MethodAction(StrictModel):
    action: Literal["validate", "unvalidate"]


class SpacedRepetitionSettings(StrictModel):
    learning_steps_days: list[float] = Field(min_length=1, max_length=6)
    relearn_minutes: int = Field(ge=1, le=1440)
    min_ease: float = Field(ge=1.1, le=2.5)
    max_interval_days: int = Field(ge=7, le=3650)
    mastery_interval_days: int = Field(ge=2, le=365)
    new_cards_per_day: int = Field(ge=0, le=200)

    @model_validator(mode="after")
    def _steps(self):
        if any(step <= 0 for step in self.learning_steps_days) or self.learning_steps_days != sorted(self.learning_steps_days):
            raise ValueError("Les premiers intervalles doivent être positifs et croissants")
        return self


class RevisionItem(BaseModel):
    item_type: Literal["flashcard", "exercise"]
    item_id: int
    title: str
    card_type: str | None = None
    hint: str | None = None
    subject_id: int | None
    chapter_id: int | None
    mastery: str
    due_at: datetime | None
    self_graded: bool  # True : l'élève s'auto-évalue après avoir vu la réponse


class RevisionStats(BaseModel):
    due_now: int
    due_tomorrow: int
    new_available: int
    by_mastery: dict[str, int]
    reviews_total: int
    reviews_last_7_days: int
    next_due_at: datetime | None


class RevisionProgram(BaseModel):
    due: list[RevisionItem]
    new: list[RevisionItem]
    stats: RevisionStats


class FlashcardReviewIn(StrictModel):
    """Carte à correction automatique : `answer_text` ; sinon : auto-évaluation `rating` (0 à 3)."""

    answer_text: str | None = Field(default=None, max_length=2000)
    rating: int | None = Field(default=None, ge=0, le=3)


class FlashcardAnswer(BaseModel):
    answer: str
    source: str


class FlashcardReviewResult(BaseModel):
    rating: int
    rating_label: str
    result: str | None
    answer: str
    source: str
    mastery: str
    next_due_at: datetime
    interval_days: float


class StudentMethod(BaseModel):
    id: int
    name: str
    category: str
    summary: str
    principle: str | None
    steps: list[str]
    examples: list[dict]
