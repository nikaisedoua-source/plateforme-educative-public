"""Espace d'exercices de l'élève (phase 3).

Un élève ne voit que les exercices **publiés** de son niveau validé et de **sa série** : un exercice
« Tle C » n'est jamais proposé à un élève de Tle A. Les réponses sont corrigées par le serveur ; la bonne
réponse et le corrigé ne sont envoyés que lorsque la règle d'accès au corrigé l'autorise.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from fastapi.responses import FileResponse

from app import storage
from app.answers import equivalent
from app.assets import asset_response
from app.database import get_db
from app.dependencies import get_current_user
from app.grading import AUTO_TYPES, grade
from app.spaced import record_exercise_result
from app.models import (
    AppSetting, Chapter, CorrectionView, Document, Exercise, ExerciseAsset, ExerciseAttempt, ExerciseQuestion,
    QuestionAttempt, Subject, Track, User,
)
from app.schemas import (
    AttemptIn, AttemptResult, QuestionAttemptIn, QuestionAttemptResult, StudentCorrection, StudentExercise,
    StudentExerciseSummary, StudentSubject,
)

router = APIRouter(prefix="/student", tags=["student"])

DEFAULT_ACCESS = {"mode": "after_attempt", "attempts": 2}
ACCESS_LABELS = {
    "always": "Corrigé disponible à tout moment",
    "after_attempt": "Corrigé disponible après une première réponse",
    "after_success_or_attempts": "Corrigé disponible après une bonne réponse ou {n} essais",
    "never": "Corrigé réservé à l'enseignant",
}


def correction_settings(db: Session) -> dict:
    setting = db.get(AppSetting, "correction_access")
    value = setting.value if setting and isinstance(setting.value, dict) else {}
    return DEFAULT_ACCESS | value


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Espace réservé aux élèves")
    profile = user.profile
    if profile is None or profile.enrollment_status != "approved" or profile.grade_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre niveau et votre série doivent d'abord être validés par l'administration",
        )
    return user


def visible_exercises(user: User):
    """Exercices publiés du niveau de l'élève ; ceux qui visent des séries exigent la sienne."""
    profile = user.profile
    track_rule = ~Exercise.tracks.any()
    if profile.track_id is not None:
        track_rule = or_(track_rule, Exercise.tracks.any(Track.id == profile.track_id))
    return select(Exercise).where(
        Exercise.is_published.is_(True), Exercise.is_archived.is_(False), Exercise.status == "validated",
        Exercise.grade_id == profile.grade_id, track_rule,
    )


def _exercise(db: Session, user: User, exercise_id: int) -> Exercise:
    exercise = db.scalar(visible_exercises(user).where(Exercise.id == exercise_id))
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercice introuvable")
    return exercise


def _attempts(db: Session, user: User, exercise_id: int) -> list[ExerciseAttempt]:
    return list(db.scalars(
        select(ExerciseAttempt).where(ExerciseAttempt.user_id == user.id, ExerciseAttempt.exercise_id == exercise_id)
        .order_by(ExerciseAttempt.id)
    ))


def _question_attempts(db: Session, user: User, exercise: Exercise) -> list[QuestionAttempt]:
    ids = [q.id for q in exercise.questions]
    if not ids:
        return []
    return list(db.scalars(select(QuestionAttempt).where(
        QuestionAttempt.user_id == user.id, QuestionAttempt.question_id.in_(ids)).order_by(QuestionAttempt.id)))


def correction_state(db: Session, exercise: Exercise, attempts: list[ExerciseAttempt],
                     question_attempts: list[QuestionAttempt] | None = None) -> tuple[bool, str]:
    """(corrigé consultable maintenant ?, explication pour l'élève). Répondre à une seule question compte
    comme une tentative : l'élève n'est jamais obligé de rédiger les démonstrations."""
    settings = correction_settings(db)
    mode = exercise.correction_access or settings["mode"]
    needed = int(settings.get("attempts") or 2)
    answered = [a for a in question_attempts or [] if a.result in ("correct", "incorrect", "submitted")]
    has_answer_key = (exercise.exercise_type in AUTO_TYPES and (
        any(o.is_correct for o in exercise.options) or bool(exercise.expected_answer)
    )) or any(q.expected_answer for q in exercise.questions)
    validated = exercise.correction is not None and exercise.correction.status == "validated"
    if not validated and not has_answer_key:
        return False, "Pas encore de corrigé validé pour cet exercice"
    label = ACCESS_LABELS[mode].format(n=needed)
    if mode == "always":
        return True, label
    if mode == "never":
        return False, label
    if mode == "after_attempt":
        return bool(attempts) or bool(answered), label
    succeeded = any(a.result == "correct" for a in [*attempts, *answered])
    return succeeded or len(attempts) + len(answered) >= needed, label


def _summary(db: Session, user: User, exercise: Exercise) -> dict:
    attempts = _attempts(db, user, exercise.id)
    counted = [a for a in attempts if not a.after_correction]
    best = max((a.score for a in counted), default=None)
    return {
        "id": exercise.id, "title": exercise.title, "exercise_type": exercise.exercise_type,
        "difficulty": exercise.difficulty, "points": exercise.points, "subject_id": exercise.subject_id,
        "chapter_id": exercise.chapter_id, "attempts": len(attempts),
        "best_score": best, "solved": any(a.result == "correct" for a in counted),
    }


@router.get("/subjects", response_model=list[StudentSubject])
def my_subjects(db: Session = Depends(get_db), user: User = Depends(require_student)):
    """Matières et chapitres où l'élève a des exercices publiés."""
    visible = visible_exercises(user).subquery()
    rows = db.execute(
        select(visible.c.subject_id, visible.c.chapter_id, func.count()).group_by(visible.c.subject_id, visible.c.chapter_id)
    ).all()
    subjects: dict[int, dict] = {}
    for subject_id, chapter_id, count in rows:
        if subject_id is None:
            continue
        subject = subjects.setdefault(subject_id, {"id": subject_id, "name": db.get(Subject, subject_id).name,
                                                   "exercise_count": 0, "chapters": []})
        subject["exercise_count"] += count
        if chapter_id is not None:
            chapter = db.get(Chapter, chapter_id)
            subject["chapters"].append({"id": chapter_id, "title": chapter.title, "exercise_count": count,
                                        "sort_order": chapter.sort_order})
    for subject in subjects.values():
        subject["chapters"].sort(key=lambda c: (c["sort_order"], c["title"]))
    return sorted(subjects.values(), key=lambda s: s["name"])


@router.get("/exercises", response_model=list[StudentExerciseSummary])
def my_exercises(
    subject_id: int | None = None, chapter_id: int | None = None,
    db: Session = Depends(get_db), user: User = Depends(require_student),
):
    query = visible_exercises(user)
    if subject_id:
        query = query.where(Exercise.subject_id == subject_id)
    if chapter_id:
        query = query.where(Exercise.chapter_id == chapter_id)
    exercises = db.scalars(query.order_by(Exercise.chapter_id, Exercise.sort_order, Exercise.id))
    return [_summary(db, user, e) for e in exercises]


@router.get("/exercises/{exercise_id}", response_model=StudentExercise)
def my_exercise(exercise_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    exercise = _exercise(db, user, exercise_id)
    attempts = _attempts(db, user, exercise_id)
    question_attempts = _question_attempts(db, user, exercise)
    available, rule = correction_state(db, exercise, attempts, question_attempts)
    document = db.get(Document, exercise.document_id)
    rewritten = exercise.statement_latex if exercise.rewrite_status in ("ok", "doubtful") else None
    last: dict[int, QuestionAttempt] = {a.question_id: a for a in question_attempts}
    has_original = document.mime_type == "application/pdf" or document.mime_type.startswith("image/")
    return _summary(db, user, exercise) | {
        "statement": rewritten or exercise.statement,
        "rewrite_status": exercise.rewrite_status,
        "original_first": exercise.rewrite_status != "ok" and has_original,
        "original_pages": list(range(exercise.page_start, exercise.page_end + 1)) if has_original else [],
        "questions": [{
            "id": q.id, "label": q.label, "text": q.text, "kind": q.kind,
            "checkable": q.kind == "result" and bool(q.expected_answer),
            "last_result": last[q.id].result if q.id in last else None,
            "last_answer": last[q.id].answer_latex if q.id in last else None,
        # Questions de la réécriture seulement si elle est sûre : une réécriture douteuse pourrait différer
        # du document (l'élève lit alors la capture et répond dans le cadre général).
        } for q in (exercise.questions if exercise.rewrite_status == "ok" else [])],
        "options": [{"id": o.id, "label": o.label, "text": o.text} for o in exercise.options],
        # Une capture de page entière montrerait aussi les exercices voisins : quand la zone recadrée de
        # l'exercice est disponible (original.png), elle la remplace.
        "assets": [{"id": a.id, "kind": a.kind, "caption": a.caption} for a in exercise.assets
                   if not (has_original and a.kind == "page")],
        "source": f"{document.title}, p. {exercise.page_start}"
                  + (f", exercice {exercise.source_number}" if exercise.source_number else ""),
        "correction_available": available, "correction_rule": rule,
        "correction_viewed": db.scalar(select(CorrectionView.id).where(
            CorrectionView.user_id == user.id, CorrectionView.exercise_id == exercise_id)) is not None,
        "history": [{"result": a.result, "score": a.score, "created_at": a.created_at,
                     "after_correction": a.after_correction} for a in attempts],
    }


@router.post("/exercises/{exercise_id}/attempts", response_model=AttemptResult, status_code=201)
def answer(exercise_id: int, payload: AttemptIn, db: Session = Depends(get_db), user: User = Depends(require_student)):
    exercise = _exercise(db, user, exercise_id)
    valid_options = {o.id for o in exercise.options}
    if payload.option_ids and not set(payload.option_ids) <= valid_options:
        raise HTTPException(status_code=422, detail="Proposition inconnue")
    if exercise.exercise_type in ("qcm", "vrai_faux") and not payload.option_ids:
        raise HTTPException(status_code=422, detail="Choisir au moins une proposition")
    if exercise.exercise_type not in ("qcm", "vrai_faux") and not (payload.answer_text or "").strip():
        raise HTTPException(status_code=422, detail="Écrire une réponse")
    last = db.scalar(select(func.max(ExerciseAttempt.created_at)).where(
        ExerciseAttempt.user_id == user.id, ExerciseAttempt.exercise_id == exercise_id))
    if last is not None and (datetime.now(UTC) - last.replace(tzinfo=last.tzinfo or UTC)).total_seconds() < 3:
        raise HTTPException(status_code=429, detail="Patientez quelques secondes avant de répondre à nouveau")
    result, score = grade(exercise, payload.answer_text, payload.option_ids)
    seen = db.scalar(select(CorrectionView.id).where(
        CorrectionView.user_id == user.id, CorrectionView.exercise_id == exercise_id)) is not None
    attempt = ExerciseAttempt(
        user_id=user.id, exercise_id=exercise_id, answer_text=(payload.answer_text or None),
        selected_option_ids=sorted(payload.option_ids) if payload.option_ids else None,
        result=result, score=score, max_score=exercise.points, after_correction=seen,
    )
    db.add(attempt)
    record_exercise_result(db, user.id, exercise_id, result, seen)  # un exercice échoué revient en révision
    db.commit()
    available, rule = correction_state(db, exercise, _attempts(db, user, exercise_id))
    messages = {
        "correct": "Bonne réponse !", "incorrect": "Ce n'est pas la bonne réponse.",
        "partial": "Réponse incomplète.", "submitted": "Réponse enregistrée : comparez-la au corrigé.",
    }
    return {"result": result, "score": score, "max_score": exercise.points, "message": messages[result],
            "after_correction": seen, "correction_available": available, "correction_rule": rule}


@router.get("/exercises/{exercise_id}/correction", response_model=StudentCorrection)
def correction(exercise_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    exercise = _exercise(db, user, exercise_id)
    available, rule = correction_state(db, exercise, _attempts(db, user, exercise_id),
                                       _question_attempts(db, user, exercise))
    if not available:
        raise HTTPException(status_code=403, detail=rule)
    view = db.scalar(select(CorrectionView).where(
        CorrectionView.user_id == user.id, CorrectionView.exercise_id == exercise_id))
    if view is None:
        db.add(CorrectionView(user_id=user.id, exercise_id=exercise_id))
    else:
        view.views += 1
    db.commit()
    validated = exercise.correction if exercise.correction and exercise.correction.status == "validated" else None
    source = None
    if validated is not None:
        document = db.get(Document, validated.source_document_id)
        source = f"{document.title}" + (f", p. {validated.source_page}" if validated.source_page else "")
    return {
        "final_answer": validated.final_answer if validated else None,
        "steps": validated.steps if validated else None,
        "text_latex": validated.text_latex if validated and validated.rewrite_status in ("ok", "doubtful") else None,
        "source": source,
        "question_answers": {q.label: q.expected_answer for q in exercise.questions if q.expected_answer},
        "correct_option_ids": [o.id for o in exercise.options if o.is_correct],
        "expected_answer": exercise.expected_answer if exercise.exercise_type in AUTO_TYPES else None,
    }


@router.post("/questions/{question_id}/attempts", response_model=QuestionAttemptResult, status_code=201)
def answer_question(question_id: int, payload: QuestionAttemptIn, db: Session = Depends(get_db),
                    user: User = Depends(require_student)):
    """Réponse à une question. Résultat vérifié par le serveur (écritures équivalentes acceptées) ;
    démonstration : enregistrée puis auto-évaluée avec le corrigé ; jamais obligatoire."""
    question = db.get(ExerciseQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question introuvable")
    exercise = _exercise(db, user, question.exercise_id)
    seen = db.scalar(select(CorrectionView.id).where(
        CorrectionView.user_id == user.id, CorrectionView.exercise_id == exercise.id)) is not None
    if payload.self_check:
        if not seen:
            raise HTTPException(status_code=409, detail="Ouvrez d'abord la correction pour vous auto-évaluer")
        result, answer_text = payload.self_check, None
    else:
        answer_text = (payload.answer_latex or "").strip()
        if not answer_text:
            raise HTTPException(status_code=422, detail="Écrire une réponse")
        last = db.scalar(select(func.max(QuestionAttempt.created_at)).where(
            QuestionAttempt.user_id == user.id, QuestionAttempt.question_id == question_id))
        if last is not None and (datetime.now(UTC) - last.replace(tzinfo=last.tzinfo or UTC)).total_seconds() < 2:
            raise HTTPException(status_code=429, detail="Patientez quelques secondes avant de répondre à nouveau")
        verdict = equivalent(answer_text, question.expected_answer) if question.kind == "result" else None
        result = "submitted" if verdict is None else ("correct" if verdict else "incorrect")
    db.add(QuestionAttempt(user_id=user.id, question_id=question_id, answer_latex=answer_text or None,
                           result=result, after_correction=seen))
    if result in ("correct", "incorrect"):
        record_exercise_result(db, user.id, exercise.id, result, seen)  # une question ratée revient en révision
    db.commit()
    available, rule = correction_state(db, exercise, _attempts(db, user, exercise.id),
                                       _question_attempts(db, user, exercise))
    messages = {
        "correct": "Bonne réponse !", "incorrect": "Pas encore : vérifiez votre calcul.",
        "submitted": "Réponse enregistrée : comparez-la à la correction.",
        "self_ok": "Bravo, c'est noté.", "self_review": "Noté : cette question reviendra en révision.",
    }
    return {"result": result, "message": messages[result], "after_correction": seen,
            "correction_available": available, "correction_rule": rule}


@router.get("/exercises/{exercise_id}/original.png")
def original(exercise_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    """Image de la zone du document où se trouve l'exercice (fidèle à l'original)."""
    from app.rewrite import CROP_VERSION, _first_line, _siblings, region_image

    from app.selection import zone_image, zones_of

    exercise = _exercise(db, user, exercise_id)
    zones, decision_id = zones_of(db, exercise.id)
    if zones:  # zone exacte relevée sur la page lors de la sélection
        name = f"{exercise.id}-zone{decision_id}.png"
        cached = storage.cache_path("originals", str(exercise.document_id), name)
        if not cached.exists():
            png = zone_image(db.get(Document, exercise.document_id), zones)
            if png is None:
                raise HTTPException(status_code=404, detail="Pas d'image originale pour cet exercice")
            cached.write_bytes(png)
        return FileResponse(cached, media_type="image/png")
    name = f"{exercise.id}-p{exercise.page_start}-{exercise.page_end}-v{CROP_VERSION}.png"
    cached = storage.cache_path("originals", str(exercise.document_id), name)
    if not cached.exists():
        document = db.get(Document, exercise.document_id)
        try:
            png = region_image(document, exercise.page_start, exercise.page_end,
                               _first_line(exercise.original_text or exercise.statement),
                               _siblings(db, document.id))
        except Exception:
            png = None
        if png is None:
            raise HTTPException(status_code=404, detail="Pas d'image originale pour cet exercice")
        cached.write_bytes(png)
    return FileResponse(cached, media_type="image/png")


@router.get("/assets/{asset_id}")
def asset(asset_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    item = db.get(ExerciseAsset, asset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Image introuvable")
    _exercise(db, user, item.exercise_id)  # l'image n'est servie que si l'exercice est visible par l'élève
    return asset_response(db, item)


@router.get("/correction-rule")
def rule(db: Session = Depends(get_db), user: User = Depends(require_student)) -> dict:
    return correction_settings(db) | {"label": ACCESS_LABELS[correction_settings(db)["mode"]]}


