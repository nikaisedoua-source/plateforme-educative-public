from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('student', 'admin')", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student", server_default="student")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False,
        foreign_keys="StudentProfile.user_id",
    )


ENROLLMENT_STATUSES = ("none", "pending", "approved", "rejected")


class StudentProfile(Base):
    """Profil élève. Le parcours demandé (niveau, série/spécialité, classe) n'est
    effectif qu'une fois validé par un administrateur (enrollment_status = approved)."""

    __tablename__ = "student_profiles"
    __table_args__ = (
        CheckConstraint(
            "enrollment_status IN ('none', 'pending', 'approved', 'rejected')",
            name="ck_student_profiles_enrollment_status",
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    pseudo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    grade_id: Mapped[int | None] = mapped_column(ForeignKey("grades.id", ondelete="SET NULL"), nullable=True)
    track_id: Mapped[int | None] = mapped_column(ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    enrollment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none", server_default="none")
    enrollment_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrollment_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrollment_reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user: Mapped[User] = relationship(back_populates="profile", foreign_keys=[user_id])


class EducationalCycle(Base):
    __tablename__ = "educational_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int | None] = mapped_column(ForeignKey("educational_cycles.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


TRACK_KINDS = ("serie", "specialite", "option", "filiere")


class Track(Base):
    """Série, spécialité, option ou filière rattachée à un niveau
    (ex. 1re STMG, BTS SIO option SLAM). Intitulés fournis par l'administrateur."""

    __tablename__ = "tracks"
    __table_args__ = (
        UniqueConstraint("grade_id", "name", name="uq_tracks_grade_name"),
        CheckConstraint("kind IN ('serie', 'specialite', 'option', 'filiere')", name="ck_tracks_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ClassGroup(Base):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("grade_id", "name", "academic_year", name="uq_classes_grade_name_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("grade_id", "subject_id", "title", name="uq_chapters_grade_subject_title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


# ---------------------------------------------------------------------------
# Phase 2 — Bibliothèque documentaire
# ---------------------------------------------------------------------------

DOCUMENT_KINDS = ("manuel", "fiche", "exercices", "devoir", "examen", "corrige", "revision", "methode", "autre")
DOCUMENT_STATUSES = ("imported", "processing", "extracted", "failed", "archived")
PAGE_METHODS = ("text", "ocr", "empty")
# Les cinq statuts du cahier (§2.3) : l'original est le document lui-même ;
# un contenu est ensuite extrait, éventuellement transformé, soumis puis validé (ou refusé).
CONTENT_STATUSES = ("extracted", "transformed", "pending_validation", "validated", "rejected")
EXERCISE_TYPES = ("libre", "qcm", "vrai_faux", "a_completer", "numerique", "probleme", "etude_de_cas")
REWRITE_STATUSES = ("none", "ok", "doubtful", "failed")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


# Séries visées (2nde A/C, 1ère A/C/D/E, Tle A/C/D/E…) : un contenu peut en viser plusieurs
# (« Terminales C, E ») mais n'est jamais proposé à une autre série.
document_tracks = Table(
    "document_tracks", Base.metadata,
    Column("document_id", ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
)
exercise_tracks = Table(
    "exercise_tracks", Base.metadata,
    Column("exercise_id", ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_exercise_tracks_track", "track_id"),
)


class Document(Base):
    """Document pédagogique importé par l'administrateur (le fichier original reste intact)."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(_in("kind", DOCUMENT_KINDS), name="ck_documents_kind"),
        CheckConstraint(_in("status", DOCUMENT_STATUSES), name="ck_documents_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)  # relatif à DOCUMENT_STORAGE_PATH
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="autre", server_default="autre")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="imported", server_default="imported")
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    pages_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade_id: Mapped[int | None] = mapped_column(ForeignKey("grades.id", ondelete="SET NULL"), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    imported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number"
    )
    tracks: Mapped[list["Track"]] = relationship(secondary=document_tracks, order_by="Track.sort_order, Track.name")

    @property
    def track_ids(self) -> list[int]:
        return [track.id for track in self.tracks]


class DocumentPage(Base):
    """Texte d'une page, avec la méthode d'obtention (texte natif ou OCR)."""

    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
        CheckConstraint(_in("method", PAGE_METHODS), name="ck_document_pages_method"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="text", server_default="text")

    document: Mapped[Document] = relationship(back_populates="pages")


class Exercise(Base):
    """Exercice extrait d'un document. `original_text` garde l'extraction brute (jamais modifiée) ;
    `statement` est la version relue par l'administrateur."""

    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint(_in("status", CONTENT_STATUSES), name="ck_exercises_status"),
        CheckConstraint(_in("exercise_type", EXERCISE_TYPES), name="ck_exercises_type"),
        CheckConstraint("difficulty BETWEEN 1 AND 3", name="ck_exercises_difficulty"),
        CheckConstraint(_in("rewrite_status", REWRITE_STATUSES), name="ck_exercises_rewrite_status"),
        Index("ix_exercises_chapter_published", "chapter_id", "is_published"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(20), nullable=False, default="libre", server_default="libre")
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    numeric_tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    grade_id: Mapped[int | None] = mapped_column(ForeignKey("grades.id", ondelete="SET NULL"), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="extracted", server_default="extracted")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Règle d'accès au corrigé propre à l'exercice (sinon : réglage général « correction_access »).
    correction_access: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Énoncé réécrit en LaTeX par le modèle local d'après l'image du document (`statement` reste l'extraction
    # brute) ; `rewrite_status` : none (pas encore relu), ok (contrôles réussis), doubtful (l'image originale
    # est alors montrée en premier), failed.
    statement_latex: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewrite_status: Mapped[str] = mapped_column(String(12), nullable=False, default="none", server_default="none")
    rewrite_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rewritten_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship()
    questions: Mapped[list["ExerciseQuestion"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan", order_by="ExerciseQuestion.sort_order"
    )
    tracks: Mapped[list["Track"]] = relationship(secondary=exercise_tracks, order_by="Track.sort_order, Track.name")
    options: Mapped[list["ExerciseOption"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan", order_by="ExerciseOption.sort_order"
    )
    correction: Mapped["Correction | None"] = relationship(
        back_populates="exercise", uselist=False, cascade="all, delete-orphan"
    )
    assets: Mapped[list["ExerciseAsset"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan", order_by="ExerciseAsset.sort_order"
    )

    @property
    def track_ids(self) -> list[int]:
        return [track.id for track in self.tracks]


class ExerciseQuestion(Base):
    """Question numérotée d'un exercice (1., 2.a…). `kind` : « result » (réponse courte vérifiée par le serveur
    quand le corrigé donne le résultat) ou « proof » (démonstration : réponse facultative, auto-évaluée).
    `expected_answer` n'est renseigné que si le résultat figure dans le corrigé fourni (jamais inventé)."""

    __tablename__ = "exercise_questions"
    __table_args__ = (CheckConstraint("kind IN ('result', 'proof')", name="ck_exercise_questions_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="result", server_default="result")
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    exercise: Mapped["Exercise"] = relationship(back_populates="questions")


class QuestionAttempt(Base):
    """Réponse d'un élève à une question. `result` : correct / incorrect (vérifié par le serveur), submitted
    (pas de résultat de référence), self_ok / self_review (auto-évaluation après lecture du corrigé)."""

    __tablename__ = "question_attempts"
    __table_args__ = (
        CheckConstraint("result IN ('correct', 'incorrect', 'submitted', 'self_ok', 'self_review')",
                        name="ck_question_attempts_result"),
        Index("ix_question_attempts_user_question", "user_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("exercise_questions.id", ondelete="CASCADE"), nullable=False)
    answer_latex: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(String(12), nullable=False)
    after_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ExerciseOption(Base):
    """Proposition de réponse (QCM, vrai/faux)."""

    __tablename__ = "exercise_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    exercise: Mapped[Exercise] = relationship(back_populates="options")


class ExerciseAsset(Base):
    """Pièce jointe d'un exercice : page du document source ou image ajoutée par l'administrateur."""

    __tablename__ = "exercise_assets"
    __table_args__ = (CheckConstraint("kind IN ('page', 'image')", name="ck_exercise_assets_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    exercise: Mapped[Exercise] = relationship(back_populates="assets")


class Correction(Base):
    """Correction d'un exercice. Elle n'est montrée aux élèves que validée ;
    `source_document_id`/`source_page` la rattachent au corrigé fourni."""

    __tablename__ = "corrections"
    __table_args__ = (CheckConstraint(_in("status", CONTENT_STATUSES), name="ck_corrections_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, unique=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="extracted", server_default="extracted")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    text_latex: Mapped[str | None] = mapped_column(Text, nullable=True)  # corrigé réécrit en LaTeX
    rewrite_status: Mapped[str] = mapped_column(String(12), nullable=False, default="none", server_default="none")

    exercise: Mapped[Exercise] = relationship(back_populates="correction")
    source_document: Mapped[Document] = relationship()


class AuditLog(Base):
    """Historique des actions administratives importantes (validations, modifications, publications)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


CORRECTION_ACCESS = ("always", "after_attempt", "after_success_or_attempts", "never")


class AppSetting(Base):
    """Réglages modifiables par l'administrateur sans toucher au code (ex. accès aux corrigés)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ExerciseAttempt(Base):
    """Réponse d'un élève, corrigée par le serveur (jamais par le navigateur).
    `after_correction` : réponse donnée après avoir vu le corrigé — elle ne compte ni pour la maîtrise
    ni pour les classements."""

    __tablename__ = "exercise_attempts"
    __table_args__ = (
        CheckConstraint("result IN ('correct', 'incorrect', 'partial', 'submitted')", name="ck_attempts_result"),
        Index("ix_attempts_user_exercise", "user_id", "exercise_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_option_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    max_score: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    after_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CorrectionView(Base):
    """Consultation d'un corrigé par un élève (voir un corrigé n'est jamais une preuve de maîtrise)."""

    __tablename__ = "correction_views"
    __table_args__ = (UniqueConstraint("user_id", "exercise_id", name="uq_correction_views_user_exercise"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    first_viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


# --------------------------------------------------------------------------- Phase 4 : mémorisation et révisions

FLASHCARD_TYPES = ("question", "definition", "formule", "vrai_faux", "a_completer", "numerique")

flashcard_tracks = Table(
    "flashcard_tracks", Base.metadata,
    Column("flashcard_id", ForeignKey("flashcards.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_flashcard_tracks_track", "track_id"),
)


class Flashcard(Base):
    """Carte mémoire (cahier §7.2) : question ou indice, réponse attendue, référence à la source, matière,
    chapitre, difficulté. `original_text` garde le passage source tel qu'extrait (jamais modifié)."""

    __tablename__ = "flashcards"
    __table_args__ = (
        CheckConstraint(_in("status", CONTENT_STATUSES), name="ck_flashcards_status"),
        CheckConstraint(_in("card_type", FLASHCARD_TYPES), name="ck_flashcards_type"),
        CheckConstraint("difficulty BETWEEN 1 AND 3", name="ck_flashcards_difficulty"),
        Index("ix_flashcards_grade_published", "grade_id", "is_published"),
        Index("ix_flashcards_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True)
    card_type: Mapped[str] = mapped_column(String(20), nullable=False, default="question", server_default="question")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    numeric_tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    grade_id: Mapped[int | None] = mapped_column(ForeignKey("grades.id", ondelete="SET NULL"), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="extracted", server_default="extracted")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship()
    tracks: Mapped[list["Track"]] = relationship(secondary=flashcard_tracks, order_by="Track.sort_order, Track.name")

    @property
    def track_ids(self) -> list[int]:
        return [track.id for track in self.tracks]


METHOD_CATEGORIES = ("rappel", "comprehension", "mnemotechnique", "organisation")
METHOD_STATUSES = ("draft", "validated")


class MemoryMethod(Base):
    """Méthode d'apprentissage (cahier §6). Bibliothèque méthodologique distincte des contenus scolaires :
    le principe et les étapes sont rédigés puis approuvés par l'administrateur ; les exemples viennent
    des documents fournis."""

    __tablename__ = "memory_methods"
    __table_args__ = (
        CheckConstraint(_in("category", METHOD_CATEGORIES), name="ck_memory_methods_category"),
        CheckConstraint(_in("status", METHOD_STATUSES), name="ck_memory_methods_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    principle: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    examples: Mapped[list["MethodExample"]] = relationship(
        back_populates="method", cascade="all, delete-orphan", order_by="MethodExample.id"
    )


class MethodExample(Base):
    """Exemple d'application d'une méthode, tiré d'un document (page, exercice ou carte mémoire)."""

    __tablename__ = "method_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    method_id: Mapped[int] = mapped_column(ForeignKey("memory_methods.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True)
    flashcard_id: Mapped[int | None] = mapped_column(ForeignKey("flashcards.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    method: Mapped[MemoryMethod] = relationship(back_populates="examples")
    document: Mapped[Document] = relationship()


REVIEW_ITEM_TYPES = ("flashcard", "exercise")
MASTERY_LEVELS = ("nouveau", "a_revoir", "en_cours", "maitrise")


class RevisionSchedule(Base):
    """Planning de répétition espacée d'un élève pour une carte ou un exercice échoué (cahier §7.3)."""

    __tablename__ = "revision_schedules"
    __table_args__ = (
        CheckConstraint(_in("item_type", REVIEW_ITEM_TYPES), name="ck_revision_schedules_item_type"),
        CheckConstraint(_in("mastery", MASTERY_LEVELS), name="ck_revision_schedules_mastery"),
        UniqueConstraint("user_id", "item_type", "item_id", name="uq_revision_schedules_item"),
        Index("ix_revision_schedules_due", "user_id", "due_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ease: Mapped[float] = mapped_column(Float, nullable=False, default=2.5, server_default="2.5")
    interval_days: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mastery: Mapped[str] = mapped_column(String(20), nullable=False, default="nouveau", server_default="nouveau")
    last_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RevisionReview(Base):
    """Historique des révisions (jamais effacé) : note, intervalle avant/après, mode de correction."""

    __tablename__ = "revision_reviews"
    __table_args__ = (
        CheckConstraint(_in("item_type", REVIEW_ITEM_TYPES), name="ck_revision_reviews_item_type"),
        CheckConstraint("rating BETWEEN 0 AND 3", name="ck_revision_reviews_rating"),
        CheckConstraint("graded_by IN ('server', 'self')", name="ck_revision_reviews_graded_by"),
        Index("ix_revision_reviews_user", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    graded_by: Mapped[str] = mapped_column(String(10), nullable=False)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval_before: Mapped[float] = mapped_column(Float, nullable=False)
    interval_after: Mapped[float] = mapped_column(Float, nullable=False)
    ease_after: Mapped[float] = mapped_column(Float, nullable=False)
    due_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FlashcardReveal(Base):
    """Réponse d'une carte affichée avant auto-évaluation (pour le suivi : voir n'est pas maîtriser)."""

    __tablename__ = "flashcard_reveals"
    __table_args__ = (Index("ix_flashcard_reveals_user", "user_id", "flashcard_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    flashcard_id: Mapped[int] = mapped_column(ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
