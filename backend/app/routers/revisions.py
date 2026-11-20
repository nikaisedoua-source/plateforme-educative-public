"""Révisions flash et mémorisation, côté élève (Phase 4).

- Programme du jour : éléments arrivés à échéance (cartes et exercices échoués), puis nouvelles cartes.
- Séance libre : cartes d'une matière ou d'un chapitre, les moins bien maîtrisées d'abord.
- Les cartes vrai/faux, à compléter ou numériques sont corrigées par le serveur ; les autres sont
  auto-évaluées après affichage de la réponse (l'affichage est enregistré).
- L'élève ne voit que les cartes publiées de son niveau et de sa série (jamais celles d'une autre série).
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.grading import check_text
from app.models import (
    Exercise, Flashcard, FlashcardReveal, MemoryMethod, RevisionReview, RevisionSchedule, Track, User,
)
from app.routers.memory import source_label
from app.routers.student import require_student, visible_exercises
from app.schemas import (
    FlashcardAnswer, FlashcardReviewIn, FlashcardReviewResult, RevisionItem, RevisionProgram, RevisionStats,
    StudentMethod,
)
from app.spaced import RATINGS, params, review, schedule_for

router = APIRouter(prefix="/student", tags=["révisions"])

SERVER_GRADED = {"vrai_faux", "a_completer", "numerique"}
MASTERY_ORDER = {"a_revoir": 0, "nouveau": 1, "en_cours": 2, "maitrise": 3}


def visible_flashcards(user: User):
    profile = user.profile
    track_rule = ~Flashcard.tracks.any()
    if profile.track_id is not None:
        track_rule = or_(track_rule, Flashcard.tracks.any(Track.id == profile.track_id))
    return select(Flashcard).where(
        Flashcard.is_published.is_(True), Flashcard.is_archived.is_(False), Flashcard.status == "validated",
        Flashcard.grade_id == profile.grade_id, track_rule,
    )


def _flashcard(db: Session, user: User, card_id: int) -> Flashcard:
    card = db.scalar(visible_flashcards(user).where(Flashcard.id == card_id))
    if card is None:
        raise HTTPException(status_code=404, detail="Carte introuvable")
    return card


def _card_item(card: Flashcard, schedule: RevisionSchedule | None) -> dict:
    return {
        "item_type": "flashcard", "item_id": card.id, "title": card.question, "card_type": card.card_type,
        "hint": card.hint, "subject_id": card.subject_id, "chapter_id": card.chapter_id,
        "mastery": schedule.mastery if schedule else "nouveau", "due_at": schedule.due_at if schedule else None,
        "self_graded": card.card_type not in SERVER_GRADED,
    }


def _exercise_item(exercise: Exercise, schedule: RevisionSchedule) -> dict:
    return {
        "item_type": "exercise", "item_id": exercise.id, "title": exercise.title, "card_type": None, "hint": None,
        "subject_id": exercise.subject_id, "chapter_id": exercise.chapter_id, "mastery": schedule.mastery,
        "due_at": schedule.due_at, "self_graded": False,
    }


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _schedules(db: Session, user: User) -> list[RevisionSchedule]:
    return list(db.scalars(select(RevisionSchedule).where(RevisionSchedule.user_id == user.id)))


def _items(db: Session, user: User, schedules: list[RevisionSchedule]) -> list[tuple[RevisionSchedule, dict]]:
    """Éléments planifiés encore visibles par l'élève (un contenu dépublié sort du programme)."""
    card_ids = [s.item_id for s in schedules if s.item_type == "flashcard"]
    exercise_ids = [s.item_id for s in schedules if s.item_type == "exercise"]
    cards = {c.id: c for c in db.scalars(visible_flashcards(user).where(Flashcard.id.in_(card_ids)))} if card_ids else {}
    exercises = {e.id: e for e in db.scalars(visible_exercises(user).where(Exercise.id.in_(exercise_ids)))} \
        if exercise_ids else {}
    items = []
    for schedule in schedules:
        if schedule.item_type == "flashcard" and schedule.item_id in cards:
            items.append((schedule, _card_item(cards[schedule.item_id], schedule)))
        elif schedule.item_type == "exercise" and schedule.item_id in exercises:
            items.append((schedule, _exercise_item(exercises[schedule.item_id], schedule)))
    return items


def _stats(db: Session, user: User, items: list[tuple[RevisionSchedule, dict]], new_available: int) -> dict:
    now = datetime.now(UTC)
    by_mastery = {level: 0 for level in MASTERY_ORDER}
    for schedule, _ in items:
        by_mastery[schedule.mastery] += 1
    by_mastery["nouveau"] += new_available
    total = db.scalar(select(func.count()).select_from(RevisionReview).where(RevisionReview.user_id == user.id))
    recent = db.scalar(select(func.count()).select_from(RevisionReview).where(
        RevisionReview.user_id == user.id, RevisionReview.created_at >= now - timedelta(days=7)))
    future = [_aware(s.due_at) for s, _ in items if _aware(s.due_at) > now]
    return {
        "due_now": sum(1 for s, _ in items if _aware(s.due_at) <= now),
        "due_tomorrow": sum(1 for s, _ in items if now < _aware(s.due_at) <= now + timedelta(days=1)),
        "new_available": new_available, "by_mastery": by_mastery, "reviews_total": total or 0,
        "reviews_last_7_days": recent or 0, "next_due_at": min(future) if future else None,
    }


def _new_cards(db: Session, user: User, scheduled_ids: set[int], limit: int) -> list[Flashcard]:
    if limit <= 0:
        return []
    query = visible_flashcards(user)
    if scheduled_ids:
        query = query.where(Flashcard.id.not_in(scheduled_ids))
    return list(db.scalars(query.order_by(Flashcard.chapter_id, Flashcard.difficulty, Flashcard.id).limit(limit)))


@router.get("/revisions/today", response_model=RevisionProgram)
def today(db: Session = Depends(get_db), user: User = Depends(require_student)):
    """Programme du jour : d'abord ce qui est mal maîtrisé et arrivé à échéance, puis des cartes nouvelles."""
    now = datetime.now(UTC)
    settings = params(db)
    schedules = _schedules(db, user)
    items = _items(db, user, schedules)
    due = sorted(
        ((s, i) for s, i in items if _aware(s.due_at) <= now),
        key=lambda pair: (MASTERY_ORDER[pair[0].mastery], pair[0].ease, _aware(pair[0].due_at)),
    )
    started_today = sum(1 for s in schedules if s.item_type == "flashcard"
                        and _aware(s.created_at or now) >= now - timedelta(days=1))
    scheduled_cards = {s.item_id for s in schedules if s.item_type == "flashcard"}
    new_cards = _new_cards(db, user, scheduled_cards, int(settings["new_cards_per_day"]) - started_today)
    unseen = db.scalar(select(func.count()).select_from(
        visible_flashcards(user).where(Flashcard.id.not_in(scheduled_cards) if scheduled_cards else True).subquery()))
    return {"due": [i for _, i in due[:60]], "new": [_card_item(c, None) for c in new_cards],
            "stats": _stats(db, user, items, unseen or 0)}


@router.get("/revisions/session", response_model=list[RevisionItem])
def free_session(
    subject_id: int | None = None, chapter_id: int | None = None, limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(require_student),
):
    """Séance libre : toutes les cartes du périmètre choisi, les notions les moins maîtrisées d'abord."""
    query = visible_flashcards(user)
    if subject_id:
        query = query.where(Flashcard.subject_id == subject_id)
    if chapter_id:
        query = query.where(Flashcard.chapter_id == chapter_id)
    cards = list(db.scalars(query))
    schedules = {s.item_id: s for s in _schedules(db, user) if s.item_type == "flashcard"}
    cards.sort(key=lambda c: (MASTERY_ORDER[schedules[c.id].mastery] if c.id in schedules else 1,
                              schedules[c.id].ease if c.id in schedules else 2.5, c.id))
    return [_card_item(c, schedules.get(c.id)) for c in cards[:limit]]


@router.get("/revisions/stats", response_model=RevisionStats)
def stats(db: Session = Depends(get_db), user: User = Depends(require_student)):
    schedules = _schedules(db, user)
    scheduled_cards = {s.item_id for s in schedules if s.item_type == "flashcard"}
    unseen = db.scalar(select(func.count()).select_from(
        visible_flashcards(user).where(Flashcard.id.not_in(scheduled_cards) if scheduled_cards else True).subquery()))
    return _stats(db, user, _items(db, user, schedules), unseen or 0)


@router.get("/flashcards/{card_id}", response_model=RevisionItem)
def flashcard(card_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    card = _flashcard(db, user, card_id)
    return _card_item(card, schedule_for(db, user.id, "flashcard", card_id))


@router.get("/flashcards/{card_id}/answer", response_model=FlashcardAnswer)
def reveal(card_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    """Réponse d'une carte auto-évaluée. Les cartes corrigées par le serveur exigent d'abord une réponse."""
    card = _flashcard(db, user, card_id)
    if card.card_type in SERVER_GRADED:
        raise HTTPException(status_code=409, detail="Répondez d'abord : la réponse s'affiche après la correction")
    db.add(FlashcardReveal(user_id=user.id, flashcard_id=card_id))
    db.commit()
    return {"answer": card.answer, "source": source_label(db, card.document_id, card.page_number, card.exercise_id)}


@router.post("/flashcards/{card_id}/review", response_model=FlashcardReviewResult)
def review_card(card_id: int, payload: FlashcardReviewIn, db: Session = Depends(get_db),
                user: User = Depends(require_student)):
    card = _flashcard(db, user, card_id)
    last = db.scalar(select(func.max(RevisionReview.created_at)).where(
        RevisionReview.user_id == user.id, RevisionReview.item_type == "flashcard", RevisionReview.item_id == card_id))
    if last is not None and (datetime.now(UTC) - _aware(last)).total_seconds() < 2:
        raise HTTPException(status_code=429, detail="Patientez un instant avant de réviser à nouveau cette carte")
    result = None
    if card.card_type in SERVER_GRADED:
        if not (payload.answer_text or "").strip():
            raise HTTPException(status_code=422, detail="Écrire une réponse")
        if payload.rating is not None:
            raise HTTPException(status_code=422, detail="Cette carte est corrigée par le serveur")
        verdict = check_text(card.card_type, card.answer, card.numeric_tolerance, payload.answer_text)
        result = "correct" if verdict else "incorrect"
        rating, graded_by = (2 if verdict else 0), "server"
    else:
        if payload.rating is None:
            raise HTTPException(status_code=422, detail="Indiquer si la réponse était connue (0 à 3)")
        revealed = db.scalar(select(FlashcardReveal.id).where(
            FlashcardReveal.user_id == user.id, FlashcardReveal.flashcard_id == card_id)) is not None
        if not revealed:
            raise HTTPException(status_code=409, detail="Afficher la réponse avant de s'auto-évaluer")
        rating, graded_by = payload.rating, "self"
    schedule = review(db, user.id, "flashcard", card_id, rating, graded_by=graded_by, result=result,
                      answer_text=payload.answer_text)
    db.commit()
    return {
        "rating": rating, "rating_label": RATINGS[rating], "result": result, "answer": card.answer,
        "source": source_label(db, card.document_id, card.page_number, card.exercise_id),
        "mastery": schedule.mastery, "next_due_at": schedule.due_at, "interval_days": schedule.interval_days,
    }


@router.get("/methods", response_model=list[StudentMethod])
def methods(db: Session = Depends(get_db), user: User = Depends(require_student)):
    """Méthodes approuvées ; seuls les exemples dont le contenu est visible par l'élève sont montrés."""
    visible_cards = set(db.scalars(visible_flashcards(user).with_only_columns(Flashcard.id)))
    visible_ex = set(db.scalars(visible_exercises(user).with_only_columns(Exercise.id)))
    result = []
    for method in db.scalars(select(MemoryMethod).where(MemoryMethod.status == "validated")
                             .order_by(MemoryMethod.sort_order)):
        examples = []
        for example in method.examples:
            if example.flashcard_id and example.flashcard_id not in visible_cards:
                continue
            if example.exercise_id and example.exercise_id not in visible_ex:
                continue
            if not example.flashcard_id and not example.exercise_id and \
                    example.document.grade_id not in (None, user.profile.grade_id):
                continue
            examples.append({"note": example.note, "exercise_id": example.exercise_id,
                             "flashcard_id": example.flashcard_id,
                             "source": source_label(db, example.document_id, example.page_number, example.exercise_id)})
        result.append({"id": method.id, "name": method.name, "category": method.category, "summary": method.summary,
                       "principle": method.principle, "steps": method.steps, "examples": examples})
    return result
