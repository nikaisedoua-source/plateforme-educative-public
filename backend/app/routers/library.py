"""Bibliothèque documentaire (Phase 2) — réservée aux administrateurs.

Import → extraction (texte/OCR) → découpage en exercices → relecture/correction → validation → publication.
Rien n'est publié automatiquement ; chaque exercice garde sa référence (document, pages, numéro).
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import extraction, storage
from app.audit import record
from app.classification import check_classification, check_tracks, grade_has_tracks
from app.config import get_settings
from app.database import get_db, get_session_factory
from app.dependencies import require_admin
from app.models import AppSetting, AuditLog, Correction, Document, Exercise, ExerciseAsset, ExerciseOption, User
from app.processing import run_extraction, segment_document
from app.schemas import (
    AuditLogRead, CorrectionAccessSettings, CorrectionIn, CorrectionRead, DocumentKind, DocumentPageRead, DocumentRead, DocumentUpdate,
    ExerciseAction, ExerciseCreate, ExerciseRead, ExerciseUpdate, ExtractionReport, SegmentReport,
)

router = APIRouter(prefix="/library", tags=["bibliothèque"], dependencies=[Depends(require_admin)])

TEXT_FIELDS = ("statement", "expected_answer", "exercise_type", "numeric_tolerance", "options")


def _document(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return document


def _exercise(db: Session, exercise_id: int) -> Exercise:
    exercise = db.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercice introuvable")
    return exercise


# --------------------------------------------------------------------------- documents

@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    kind: DocumentKind = Form("autre"),
    grade_id: int | None = Form(None),
    track_ids: list[int] = Form([]),
    subject_id: int | None = Form(None),
    chapter_id: int | None = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    filename = file.filename or "document"
    mime = storage.mime_for(filename)
    if mime is None:
        raise HTTPException(status_code=415, detail="Format accepté : PDF, DOCX, DOC, TXT, PNG, JPG")
    classification = check_classification(db, grade_id, subject_id, chapter_id)
    tracks = check_tracks(db, classification["grade_id"], track_ids)
    try:
        key, size, sha = storage.save_stream(file.file, "originals", filename, get_settings().max_upload_mb * 1024 * 1024)
    except OverflowError:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux") from None
    duplicate = db.scalar(select(Document).where(Document.sha256 == sha))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail=f"Document déjà importé (n° {duplicate.id} : {duplicate.title})")
    document = Document(
        title=(title or filename.rsplit(".", 1)[0]).strip()[:255], original_filename=filename[:255],
        storage_key=key, mime_type=mime, size_bytes=size, sha256=sha, kind=kind,
        imported_by=admin.id, **classification,
    )
    document.tracks = tracks
    db.add(document)
    db.flush()
    record(db, admin.id, "import", "document", document.id, filename=filename, size=size)
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(
    status_filter: str | None = Query(default=None, alias="status"),
    subject_id: int | None = None,
    grade_id: int | None = None,
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    query = select(Document)
    if status_filter:
        query = query.where(Document.status == status_filter)
    if subject_id:
        query = query.where(Document.subject_id == subject_id)
    if grade_id:
        query = query.where(Document.grade_id == grade_id)
    if q:
        query = query.where(Document.title.ilike(f"%{q}%") | Document.original_filename.ilike(f"%{q}%"))
    return list(db.scalars(query.order_by(Document.imported_at.desc(), Document.id.desc())))


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, db: Session = Depends(get_db)):
    return _document(db, document_id)


@router.patch("/documents/{document_id}", response_model=DocumentRead)
def update_document(
    document_id: int, payload: DocumentUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    document = _document(db, document_id)
    changes = payload.model_dump(exclude_unset=True)
    track_ids = changes.pop("track_ids", None)
    merged = {k: changes.get(k, getattr(document, k)) for k in ("grade_id", "subject_id", "chapter_id")}
    changes.update(check_classification(db, **merged))
    tracks = check_tracks(db, changes["grade_id"], document.track_ids if track_ids is None else track_ids)
    before = {k: getattr(document, k) for k in changes} | {"track_ids": document.track_ids}
    for key, value in changes.items():
        setattr(document, key, value)
    document.tracks = tracks
    changes["track_ids"] = [t.id for t in tracks]
    record(db, admin.id, "update", "document", document_id, before=before, after=changes)
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents/{document_id}/identify")
def identify_document(document_id: int, db: Session = Depends(get_db)):
    """Propositions de titre, niveau, matière et type lues dans le document (à confirmer par l'admin)."""
    document = _document(db, document_id)
    text = "\n".join(p.text for p in document.pages[:3])
    return extraction.identify(text, document.original_filename)


@router.get("/documents/{document_id}/file")
def download_original(document_id: int, db: Session = Depends(get_db)):
    document = _document(db, document_id)
    return FileResponse(storage.resolve(document.storage_key), media_type=document.mime_type,
                        filename=document.original_filename)


@router.post("/documents/{document_id}/extract", response_model=ExtractionReport, status_code=status.HTTP_202_ACCEPTED)
def extract_document(
    document_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    factory: sessionmaker = Depends(get_session_factory),
    admin: User = Depends(require_admin),
):
    document = _document(db, document_id)
    if document.status == "processing":
        raise HTTPException(status_code=409, detail="Extraction déjà en cours")
    document.status = "processing"
    document.extraction_error = None
    db.commit()
    background.add_task(run_extraction, document_id, factory, admin.id)
    return ExtractionReport(document_id=document_id, status="processing", page_count=document.page_count)


@router.get("/documents/{document_id}/pages", response_model=list[DocumentPageRead])
def list_pages(document_id: int, db: Session = Depends(get_db)):
    return _document(db, document_id).pages


@router.get("/documents/{document_id}/pages/{page_number}/image")
def page_image(document_id: int, page_number: int, db: Session = Depends(get_db)):
    """Aperçu de la page originale, pour comparer avec le texte extrait (cahier §11.3)."""
    document = _document(db, document_id)
    cached = storage.cache_path("pages", str(document_id), f"{page_number}.png")
    if not cached.exists():
        try:
            png = extraction.render_page(storage.resolve(document.storage_key), document.mime_type, page_number)
        except extraction.ExtractionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        cached.write_bytes(png)
    return FileResponse(cached, media_type="image/png")


@router.post("/documents/{document_id}/segment", response_model=SegmentReport)
def segment(
    document_id: int,
    correction_document_id: int | None = None,
    replace: bool = False,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    document = _document(db, document_id)
    if document.status != "extracted":
        raise HTTPException(status_code=409, detail="Extraire le texte du document d'abord")
    correction_document = None
    if correction_document_id is not None:
        correction_document = _document(db, correction_document_id)
        if correction_document.status != "extracted":
            raise HTTPException(status_code=409, detail="Extraire d'abord le texte du corrigé")
    try:
        created, linked = segment_document(db, document, admin.id, correction_document, replace)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return SegmentReport(document_id=document_id, exercises_created=created, corrections_found=linked)


@router.post("/documents/{document_id}/archive", response_model=DocumentRead)
def archive_document(document_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    document = _document(db, document_id)
    document.status = "archived"
    for exercise in db.scalars(select(Exercise).where(Exercise.document_id == document_id)):
        exercise.is_published = False
        exercise.is_archived = True
    record(db, admin.id, "archive", "document", document_id)
    db.commit()
    db.refresh(document)
    return document


# --------------------------------------------------------------------------- exercices

@router.get("/exercises", response_model=list[ExerciseRead])
def list_exercises(
    document_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    chapter_id: int | None = None,
    subject_id: int | None = None,
    published: bool | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Exercise)
    if document_id:
        query = query.where(Exercise.document_id == document_id)
    if status_filter:
        query = query.where(Exercise.status == status_filter)
    if chapter_id:
        query = query.where(Exercise.chapter_id == chapter_id)
    if subject_id:
        query = query.where(Exercise.subject_id == subject_id)
    if published is not None:
        query = query.where(Exercise.is_published == published)
    query = query.order_by(Exercise.document_id, Exercise.sort_order, Exercise.id).offset(offset).limit(limit)
    return list(db.scalars(query))


@router.post("/exercises", response_model=ExerciseRead, status_code=status.HTTP_201_CREATED)
def create_exercise(payload: ExerciseCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Découpage manuel : l'administrateur copie un exercice depuis une page du document."""
    document = _document(db, payload.document_id)
    data = payload.model_dump()
    track_ids = data.pop("track_ids")
    classification = check_classification(db, data.pop("grade_id"), data.pop("subject_id"), data.pop("chapter_id"))
    if classification["grade_id"] is None:  # hérite du document
        classification = {"grade_id": document.grade_id, "subject_id": classification["subject_id"] or document.subject_id,
                          "chapter_id": classification["chapter_id"]}
    tracks = check_tracks(db, classification["grade_id"], document.track_ids if track_ids is None else track_ids)
    page_end = data.pop("page_end") or data["page_start"]
    if document.page_count and max(page_end, data["page_start"]) > document.page_count:
        raise HTTPException(status_code=422, detail="Page hors du document")
    statement = data.pop("statement")
    exercise = Exercise(
        **data, page_end=page_end, original_text=statement, statement=statement, status="extracted", **classification
    )
    exercise.tracks = tracks
    db.add(exercise)
    db.flush()
    record(db, admin.id, "create", "exercise", exercise.id, document_id=document.id)
    db.commit()
    db.refresh(exercise)
    return exercise


@router.get("/exercises/{exercise_id}", response_model=ExerciseRead)
def get_exercise(exercise_id: int, db: Session = Depends(get_db)):
    return _exercise(db, exercise_id)


@router.patch("/exercises/{exercise_id}", response_model=ExerciseRead)
def update_exercise(
    exercise_id: int, payload: ExerciseUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    exercise = _exercise(db, exercise_id)
    changes = payload.model_dump(exclude_unset=True)
    options = changes.pop("options", None)
    track_ids = changes.pop("track_ids", None)
    keys = ("grade_id", "subject_id", "chapter_id")
    tracks_before = exercise.track_ids
    if any(k in changes for k in keys) or track_ids is not None:
        merged = {k: changes.get(k, getattr(exercise, k)) for k in keys}
        changes.update(check_classification(db, **merged))
        exercise.tracks = check_tracks(db, changes["grade_id"], tracks_before if track_ids is None else track_ids)
    before = {k: getattr(exercise, k) for k in changes}
    content_changed = any(k in changes and changes[k] != before[k] for k in TEXT_FIELDS) or options is not None
    content_changed = content_changed or any(k in changes and changes[k] != before[k] for k in keys)
    tracks_changed = exercise.track_ids != tracks_before
    content_changed = content_changed or tracks_changed
    for key, value in changes.items():
        setattr(exercise, key, value)
    if tracks_changed:
        before["track_ids"], changes["track_ids"] = tracks_before, exercise.track_ids
    if exercise.page_end < exercise.page_start:
        raise HTTPException(status_code=422, detail="La page de fin précède la page de début")
    if options is not None:
        if exercise.exercise_type in ("qcm", "vrai_faux") and options and not any(o["is_correct"] for o in options):
            raise HTTPException(status_code=422, detail="Indiquer au moins une bonne réponse")
        exercise.options = [ExerciseOption(**o, sort_order=i) for i, o in enumerate(options)]
    if content_changed:
        # Toute modification du contenu impose une nouvelle validation (aucune modification silencieuse).
        exercise.status = "transformed"
        exercise.is_published = False
        exercise.validated_at = None
    record(db, admin.id, "update", "exercise", exercise_id, before=before, after=changes,
           options_changed=options is not None)
    db.commit()
    db.refresh(exercise)
    return exercise


@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(exercise_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Supprime un élément mal extrait. Un exercice validé ou publié s'archive au lieu d'être supprimé."""
    exercise = _exercise(db, exercise_id)
    if exercise.status == "validated" or exercise.published_at is not None:
        raise HTTPException(status_code=409, detail="Exercice validé ou déjà publié : utiliser l'archivage")
    record(db, admin.id, "delete", "exercise", exercise_id, title=exercise.title, document_id=exercise.document_id)
    db.delete(exercise)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/exercises/{exercise_id}/action", response_model=ExerciseRead)
def exercise_action(
    exercise_id: int, payload: ExerciseAction, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    exercise = _exercise(db, exercise_id)
    action = payload.action
    now = datetime.now(UTC)
    if action == "submit":
        if exercise.status not in ("extracted", "transformed", "rejected"):
            raise HTTPException(status_code=409, detail="Seul un contenu extrait ou transformé peut être soumis")
        exercise.status = "pending_validation"
    elif action == "validate":
        if exercise.status == "validated":
            raise HTTPException(status_code=409, detail="Déjà validé")
        if exercise.chapter_id is None:
            raise HTTPException(status_code=422, detail="Rattacher l'exercice à un chapitre avant de le valider")
        if not exercise.tracks and grade_has_tracks(db, exercise.grade_id):
            raise HTTPException(
                status_code=422,
                detail="Choisir la ou les séries visées avant de valider (les séries ne doivent pas être mélangées)",
            )
        if exercise.exercise_type in ("qcm", "vrai_faux") and not any(o.is_correct for o in exercise.options):
            raise HTTPException(status_code=422, detail="QCM/vrai-faux : indiquer la bonne réponse avant validation")
        exercise.status = "validated"
        exercise.validated_at = now
        exercise.validated_by = admin.id
    elif action == "reject":
        exercise.status = "rejected"
        exercise.is_published = False
    elif action == "publish":
        if exercise.status != "validated" or exercise.is_archived:
            raise HTTPException(status_code=409, detail="Seul un exercice validé et non archivé peut être publié")
        exercise.is_published = True
        exercise.published_at = exercise.published_at or now
    elif action == "unpublish":
        exercise.is_published = False
    elif action == "archive":
        exercise.is_published = False
        exercise.is_archived = True
    elif action == "restore":
        exercise.is_archived = False
    record(db, admin.id, action, "exercise", exercise_id, comment=payload.comment, status=exercise.status)
    db.commit()
    db.refresh(exercise)
    return exercise


# --------------------------------------------------------------------------- corrections

@router.put("/exercises/{exercise_id}/correction", response_model=CorrectionRead)
def save_correction(
    exercise_id: int, payload: CorrectionIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    exercise = _exercise(db, exercise_id)
    _document(db, payload.source_document_id)
    data = payload.model_dump()
    correction = exercise.correction
    if correction is None:
        correction = Correction(exercise_id=exercise_id, **data, status="extracted")
        if not correction.original_text:
            correction.original_text = "\n".join(filter(None, [data["final_answer"], data["steps"]]))
        db.add(correction)
    else:
        for key, value in data.items():
            if key == "original_text" and correction.original_text:
                continue  # le texte d'origine du corrigé n'est jamais réécrit
            setattr(correction, key, value)
        correction.status = "transformed"
        correction.validated_at = None
    record(db, admin.id, "save_correction", "exercise", exercise_id)
    db.commit()
    db.refresh(correction)
    return correction


@router.post("/exercises/{exercise_id}/correction/{decision}", response_model=CorrectionRead)
def decide_correction(
    exercise_id: int,
    decision: Literal["validate", "reject"],
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    correction = _exercise(db, exercise_id).correction
    if correction is None:
        raise HTTPException(status_code=404, detail="Aucune correction")
    correction.status = "validated" if decision == "validate" else "rejected"
    correction.validated_at = datetime.now(UTC) if decision == "validate" else None
    record(db, admin.id, f"correction_{decision}", "exercise", exercise_id)
    db.commit()
    db.refresh(correction)
    return correction


@router.delete("/exercises/{exercise_id}/correction", status_code=status.HTTP_204_NO_CONTENT)
def delete_correction(exercise_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    exercise = _exercise(db, exercise_id)
    if exercise.correction is not None:
        db.delete(exercise.correction)
        record(db, admin.id, "delete_correction", "exercise", exercise_id)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- pièces jointes

@router.post("/exercises/{exercise_id}/assets/page", response_model=ExerciseRead)
def add_page_capture(
    exercise_id: int, page_number: int = Query(gt=0), db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    exercise = _exercise(db, exercise_id)
    exercise.assets.append(ExerciseAsset(kind="page", page_number=page_number,
                                         caption=f"Capture de la page {page_number}", sort_order=len(exercise.assets)))
    record(db, admin.id, "add_asset", "exercise", exercise_id, page=page_number)
    db.commit()
    db.refresh(exercise)
    return exercise


@router.post("/exercises/{exercise_id}/assets/image", response_model=ExerciseRead)
def add_image(
    exercise_id: int, file: UploadFile = File(...), caption: str | None = Form(None),
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    exercise = _exercise(db, exercise_id)
    if storage.mime_for(file.filename or "") not in storage.IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Image PNG ou JPG attendue")
    key, _size, _sha = storage.save_stream(file.file, f"figures/{exercise.document_id}", file.filename or "image.png",
                                           20 * 1024 * 1024)
    exercise.assets.append(ExerciseAsset(kind="image", storage_key=key, caption=caption, sort_order=len(exercise.assets)))
    record(db, admin.id, "add_asset", "exercise", exercise_id, image=key)
    db.commit()
    db.refresh(exercise)
    return exercise


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    asset = db.get(ExerciseAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Pièce jointe introuvable")
    record(db, admin.id, "delete_asset", "exercise", asset.exercise_id, asset=asset_id)
    db.delete(asset)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/assets/{asset_id}")
def admin_asset_image(asset_id: int, db: Session = Depends(get_db)):
    from app.assets import asset_response

    asset = db.get(ExerciseAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Pièce jointe introuvable")
    return asset_response(db, asset)


# --------------------------------------------------------------------------- historique

@router.get("/audit", response_model=list[AuditLogRead])
def audit_log(
    entity_type: str | None = None, entity_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db),
):
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditLog.entity_id == entity_id)
    return list(db.scalars(query.order_by(AuditLog.id.desc()).limit(limit)))


# --------------------------------------------------------------------------- réglages


@router.get("/settings/correction-access", response_model=CorrectionAccessSettings)
def get_correction_access(db: Session = Depends(get_db)):
    from app.routers.student import correction_settings

    return correction_settings(db)


@router.put("/settings/correction-access", response_model=CorrectionAccessSettings)
def set_correction_access(
    payload: CorrectionAccessSettings, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    setting = db.get(AppSetting, "correction_access")
    before = setting.value if setting else None
    if setting is None:
        setting = AppSetting(key="correction_access")
        db.add(setting)
    setting.value = payload.model_dump()
    record(db, admin.id, "update", "setting", None, key="correction_access", before=before, after=setting.value)
    db.commit()
    return payload
