"""Mémorisation (Phase 4), côté administrateur : cartes mémoire, méthodes, paramètres de répétition espacée.

Une carte garde sa source (document, page, exercice) et suit le même circuit que les exercices :
extrait → transformé → en attente → validé → publié. Rien n'est montré aux élèves sans validation.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import record
from app.classification import check_classification, check_tracks, grade_has_tracks
from app.database import get_db
from app.dependencies import require_admin
from app.flashcards import create_proposals
from app.grading import parse_number
from app.methods_catalog import ensure_catalog
from app.publication import auto_enabled, publish, publish_document
from app.models import (
    AppSetting, Document, Exercise, Flashcard, FlashcardReveal, MemoryMethod, MethodExample, RevisionSchedule, User,
)
from app.schemas import (
    ExerciseAction, FlashcardCreate, FlashcardRead, FlashcardUpdate, MethodAction, MethodExampleIn, MethodExampleRead,
    MethodRead, MethodUpdate, ProposalReport, SpacedRepetitionSettings,
)
from app.spaced import params

router = APIRouter(prefix="/memory", tags=["mémorisation"], dependencies=[Depends(require_admin)])

CONTENT_FIELDS = ("question", "answer", "card_type", "numeric_tolerance", "grade_id", "subject_id", "chapter_id")


def _card(db: Session, card_id: int) -> Flashcard:
    card = db.get(Flashcard, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Carte introuvable")
    return card


def source_label(db: Session, document_id: int, page: int | None, exercise_id: int | None = None) -> str:
    document = db.get(Document, document_id)
    label = document.title if document else f"document {document_id}"
    if page:
        label += f", p. {page}"
    if exercise_id:
        exercise = db.get(Exercise, exercise_id)
        if exercise is not None and exercise.source_number:
            label += f", exercice {exercise.source_number}"
    return label


# --------------------------------------------------------------------------- cartes mémoire

@router.get("/flashcards", response_model=list[FlashcardRead])
def list_flashcards(
    document_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    subject_id: int | None = None,
    chapter_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Flashcard)
    if document_id:
        query = query.where(Flashcard.document_id == document_id)
    if status_filter:
        query = query.where(Flashcard.status == status_filter)
    if subject_id:
        query = query.where(Flashcard.subject_id == subject_id)
    if chapter_id:
        query = query.where(Flashcard.chapter_id == chapter_id)
    return list(db.scalars(query.order_by(Flashcard.document_id, Flashcard.page_number, Flashcard.id)
                           .offset(offset).limit(limit)))


@router.post("/flashcards", response_model=FlashcardRead, status_code=status.HTTP_201_CREATED)
def create_flashcard(payload: FlashcardCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    data = payload.model_dump()
    exercise = db.get(Exercise, data["exercise_id"]) if data["exercise_id"] else None
    if data["exercise_id"] and exercise is None:
        raise HTTPException(status_code=404, detail="Exercice introuvable")
    document_id = data["document_id"] or exercise.document_id
    if exercise is not None and exercise.document_id != document_id:
        raise HTTPException(status_code=422, detail="L'exercice ne vient pas de ce document")
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable")
    page = data["page_number"] or (exercise.page_start if exercise else None)
    if page and document.page_count and page > document.page_count:
        raise HTTPException(status_code=422, detail="Page hors du document")
    origin = exercise or document
    classification = check_classification(
        db, data["grade_id"] or origin.grade_id, data["subject_id"] or origin.subject_id,
        data["chapter_id"] or getattr(origin, "chapter_id", None),
    )
    tracks = check_tracks(db, classification["grade_id"],
                          origin.track_ids if data["track_ids"] is None else data["track_ids"])
    card = Flashcard(
        document_id=document_id, page_number=page, exercise_id=data["exercise_id"], card_type=data["card_type"],
        question=data["question"], answer=data["answer"], hint=data["hint"],
        original_text=data["original_text"] or data["answer"], numeric_tolerance=data["numeric_tolerance"],
        difficulty=data["difficulty"], status="transformed", **classification,
    )
    card.tracks = tracks
    db.add(card)
    db.flush()
    record(db, admin.id, "create", "flashcard", card.id, document_id=document_id, exercise_id=data["exercise_id"])
    db.commit()
    db.refresh(card)
    return card


@router.post("/documents/{document_id}/propose-flashcards", response_model=ProposalReport)
def propose_flashcards(document_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Repère définitions, théorèmes, propriétés, règles, formules et « On appelle … » dans le document."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable")
    if document.status != "extracted":
        raise HTTPException(status_code=409, detail="Extraire le document avant de proposer des cartes")
    found, created = create_proposals(db, document)
    record(db, admin.id, "propose_flashcards", "document", document_id, found=found, created=created)
    db.commit()
    publish_document(db, document)
    db.commit()
    return {"document_id": document_id, "found": found, "created": created, "already_present": found - created}


@router.get("/flashcards/{card_id}", response_model=FlashcardRead)
def get_flashcard(card_id: int, db: Session = Depends(get_db)):
    return _card(db, card_id)


@router.patch("/flashcards/{card_id}", response_model=FlashcardRead)
def update_flashcard(card_id: int, payload: FlashcardUpdate, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    card = _card(db, card_id)
    changes = payload.model_dump(exclude_unset=True)
    track_ids = changes.pop("track_ids", None)
    keys = ("grade_id", "subject_id", "chapter_id")
    tracks_before = card.track_ids
    if any(k in changes for k in keys) or track_ids is not None:
        merged = {k: changes.get(k, getattr(card, k)) for k in keys}
        changes.update(check_classification(db, **merged))
        card.tracks = check_tracks(db, changes["grade_id"], tracks_before if track_ids is None else track_ids)
    document = db.get(Document, card.document_id)
    if changes.get("page_number") and document.page_count and changes["page_number"] > document.page_count:
        raise HTTPException(status_code=422, detail="Page hors du document")
    before = {k: getattr(card, k) for k in changes}
    changed = any(k in changes and changes[k] != before[k] for k in CONTENT_FIELDS) or card.track_ids != tracks_before
    for key, value in changes.items():
        setattr(card, key, value)
    if card.track_ids != tracks_before:
        before["track_ids"], changes["track_ids"] = tracks_before, card.track_ids
    if changed:  # toute modification du contenu impose une nouvelle validation
        card.status = "transformed"
        card.is_published = False
        card.validated_at = None
        if auto_enabled(db):
            db.flush()
            if publish(db, card, datetime.now(UTC)) is None:
                card.validated_by = admin.id
    record(db, admin.id, "update", "flashcard", card_id, before=before, after=changes)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/flashcards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flashcard(card_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Supprime une proposition inutile. Une carte validée ou déjà publiée s'archive (historique des élèves)."""
    card = _card(db, card_id)
    if card.status == "validated" or card.published_at is not None:
        raise HTTPException(status_code=409, detail="Carte validée ou déjà publiée : utiliser l'archivage")
    record(db, admin.id, "delete", "flashcard", card_id, question=card.question, document_id=card.document_id)
    db.execute(delete(RevisionSchedule).where(RevisionSchedule.item_type == "flashcard",
                                              RevisionSchedule.item_id == card_id))
    db.execute(delete(FlashcardReveal).where(FlashcardReveal.flashcard_id == card_id))
    db.delete(card)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/flashcards/{card_id}/action", response_model=FlashcardRead)
def flashcard_action(card_id: int, payload: ExerciseAction, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    card = _card(db, card_id)
    action = payload.action
    now = datetime.now(UTC)
    if action == "submit":
        if card.status not in ("extracted", "transformed", "rejected"):
            raise HTTPException(status_code=409, detail="Seul un contenu extrait ou transformé peut être soumis")
        card.status = "pending_validation"
    elif action == "validate":
        if card.status == "validated" and card.validated_by is not None:
            raise HTTPException(status_code=409, detail="Déjà validée")
        if card.chapter_id is None:
            raise HTTPException(status_code=422, detail="Rattacher la carte à un chapitre avant de la valider")
        if not card.tracks and grade_has_tracks(db, card.grade_id):
            raise HTTPException(
                status_code=422,
                detail="Choisir la ou les séries visées avant de valider (les séries ne doivent pas être mélangées)",
            )
        if card.card_type == "numerique" and parse_number(card.answer) is None:
            raise HTTPException(status_code=422, detail="Carte numérique : la réponse doit être un nombre")
        if card.card_type == "vrai_faux" and card.answer.strip().lower() not in ("vrai", "faux"):
            raise HTTPException(status_code=422, detail="Carte vrai/faux : la réponse doit être « vrai » ou « faux »")
        card.status = "validated"
        card.validated_at = now
        card.validated_by = admin.id
    elif action == "reject":
        card.status = "rejected"
        card.is_published = False
    elif action == "publish":
        if card.status != "validated" or card.is_archived:
            raise HTTPException(status_code=409, detail="Seule une carte validée et non archivée peut être publiée")
        card.is_published = True
        card.published_at = card.published_at or now
    elif action == "unpublish":
        card.is_published = False
    elif action == "archive":
        card.is_published = False
        card.is_archived = True
    elif action == "restore":
        card.is_archived = False
    record(db, admin.id, action, "flashcard", card_id, comment=payload.comment, status=card.status)
    db.commit()
    db.refresh(card)
    return card


# --------------------------------------------------------------------------- méthodes

def _method_read(db: Session, method: MemoryMethod) -> dict:
    data = MethodRead.model_validate(method).model_dump()
    data["examples"] = [
        MethodExampleRead.model_validate(e).model_dump()
        | {"source": source_label(db, e.document_id, e.page_number, e.exercise_id)}
        for e in method.examples
    ]
    return data


def _method(db: Session, method_id: int) -> MemoryMethod:
    method = db.get(MemoryMethod, method_id)
    if method is None:
        raise HTTPException(status_code=404, detail="Méthode introuvable")
    return method


@router.get("/methods", response_model=list[MethodRead])
def list_methods(db: Session = Depends(get_db)):
    ensure_catalog(db)
    methods = db.scalars(select(MemoryMethod).order_by(MemoryMethod.sort_order, MemoryMethod.id))
    return [_method_read(db, m) for m in methods]


@router.patch("/methods/{method_id}", response_model=MethodRead)
def update_method(method_id: int, payload: MethodUpdate, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    method = _method(db, method_id)
    changes = payload.model_dump(exclude_unset=True)
    if "steps" in changes:
        changes["steps"] = [s.strip() for s in changes["steps"] if s and s.strip()]
    before = {k: getattr(method, k) for k in changes}
    for key, value in changes.items():
        setattr(method, key, value)
    if any(before[k] != changes[k] for k in changes) and method.status == "validated":
        method.status = "draft"  # une méthode modifiée doit être approuvée à nouveau
        method.validated_at = None
    record(db, admin.id, "update", "memory_method", method_id, before=before, after=changes)
    db.commit()
    db.refresh(method)
    return _method_read(db, method)


@router.post("/methods/{method_id}/action", response_model=MethodRead)
def method_action(method_id: int, payload: MethodAction, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    method = _method(db, method_id)
    if payload.action == "validate":
        if not (method.principle or "").strip() or not method.steps:
            raise HTTPException(status_code=422, detail="Rédiger le principe et au moins une étape avant d'approuver")
        method.status = "validated"
        method.validated_at = datetime.now(UTC)
        method.validated_by = admin.id
    else:
        method.status = "draft"
        method.validated_at = None
    record(db, admin.id, payload.action, "memory_method", method_id)
    db.commit()
    db.refresh(method)
    return _method_read(db, method)


@router.post("/methods/{method_id}/examples", response_model=MethodRead, status_code=status.HTTP_201_CREATED)
def add_example(method_id: int, payload: MethodExampleIn, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    """Exemple tiré des ressources : une page de document, un exercice ou une carte mémoire."""
    method = _method(db, method_id)
    data = payload.model_dump()
    document_id, page = data["document_id"], data["page_number"]
    if data["flashcard_id"]:
        card = _card(db, data["flashcard_id"])
        document_id, page = document_id or card.document_id, page or card.page_number
    if data["exercise_id"]:
        exercise = db.get(Exercise, data["exercise_id"])
        if exercise is None:
            raise HTTPException(status_code=404, detail="Exercice introuvable")
        document_id, page = document_id or exercise.document_id, page or exercise.page_start
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="Document introuvable")
    example = MethodExample(method_id=method.id, document_id=document_id, page_number=page,
                            exercise_id=data["exercise_id"], flashcard_id=data["flashcard_id"], note=data["note"],
                            created_by=admin.id)
    db.add(example)
    db.flush()
    record(db, admin.id, "add_example", "memory_method", method_id, example_id=example.id, document_id=document_id)
    db.commit()
    db.refresh(method)
    return _method_read(db, method)


@router.delete("/examples/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_example(example_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    example = db.get(MethodExample, example_id)
    if example is None:
        raise HTTPException(status_code=404, detail="Exemple introuvable")
    record(db, admin.id, "delete_example", "memory_method", example.method_id, example_id=example_id,
           note=example.note)
    db.delete(example)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- paramètres

@router.get("/settings/spaced-repetition", response_model=SpacedRepetitionSettings)
def get_spaced_settings(db: Session = Depends(get_db)):
    return params(db)


@router.put("/settings/spaced-repetition", response_model=SpacedRepetitionSettings)
def set_spaced_settings(payload: SpacedRepetitionSettings, db: Session = Depends(get_db),
                        admin: User = Depends(require_admin)):
    setting = db.get(AppSetting, "spaced_repetition")
    before = setting.value if setting else None
    if setting is None:
        setting = AppSetting(key="spaced_repetition")
        db.add(setting)
    setting.value = payload.model_dump()
    record(db, admin.id, "update", "setting", None, key="spaced_repetition", before=before, after=setting.value)
    db.commit()
    return params(db)
