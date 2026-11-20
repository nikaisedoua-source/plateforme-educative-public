"""Répétition espacée (cahier §7.3) : les notions mal maîtrisées reviennent plus souvent, les révisions des
notions bien mémorisées s'espacent progressivement. Les paramètres sont réglables par l'administrateur
(réglage « spaced_repetition ») et chaque révision est conservée dans `revision_reviews`.

Notes : 0 = à revoir, 1 = difficile, 2 = bien, 3 = facile.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting, RevisionReview, RevisionSchedule

DEFAULT_PARAMS = {
    "learning_steps_days": [1, 3],   # premiers intervalles après une bonne réponse
    "relearn_minutes": 10,           # une carte ratée revient dans la même séance
    "min_ease": 1.3,
    "max_interval_days": 180,
    "mastery_interval_days": 21,     # au-delà, la notion est considérée comme maîtrisée
    "new_cards_per_day": 20,
}
RATINGS = {0: "À revoir", 1: "Difficile", 2: "Bien", 3: "Facile"}


def params(db: Session) -> dict:
    setting = db.get(AppSetting, "spaced_repetition")
    value = setting.value if setting and isinstance(setting.value, dict) else {}
    return DEFAULT_PARAMS | value


def schedule_for(db: Session, user_id: int, item_type: str, item_id: int) -> RevisionSchedule | None:
    return db.scalar(select(RevisionSchedule).where(
        RevisionSchedule.user_id == user_id, RevisionSchedule.item_type == item_type,
        RevisionSchedule.item_id == item_id))


def next_state(schedule: RevisionSchedule, rating: int, settings: dict, *, relearn: bool = True) -> dict:
    """Calcule le nouvel état sans l'appliquer (fonction pure, testable)."""
    ease, interval, reps = schedule.ease, schedule.interval_days, schedule.repetitions
    steps = [float(s) for s in settings["learning_steps_days"]] or [1.0]
    lapses = schedule.lapses
    if rating == 0:
        lapses += 1
        reps = 0
        ease = max(settings["min_ease"], ease - 0.2)
        interval = 0.0
        delay = timedelta(minutes=settings["relearn_minutes"]) if relearn else timedelta(days=1)
    else:
        base = steps[reps] if reps < len(steps) else interval * ease
        if rating == 1:
            ease = max(settings["min_ease"], ease - 0.15)
            new = max(1.0, (interval or 1.0) * 1.2) if reps >= len(steps) else max(1.0, steps[0])
        elif rating == 2:
            new = base
            reps += 1
        else:
            ease += 0.15
            new = base * 1.5
            reps += 1
        if rating >= 2 and interval:
            new = max(new, interval + 1)
        interval = round(min(float(settings["max_interval_days"]), new), 2)
        delay = timedelta(days=interval)
    if rating == 0:
        mastery = "a_revoir"
    elif interval >= settings["mastery_interval_days"]:
        mastery = "maitrise"
    else:
        mastery = "en_cours"
    return {"ease": round(ease, 3), "interval_days": interval, "repetitions": reps, "lapses": lapses,
            "mastery": mastery, "delay": delay}


def review(db: Session, user_id: int, item_type: str, item_id: int, rating: int, *, graded_by: str,
           result: str | None = None, answer_text: str | None = None, relearn: bool = True,
           now: datetime | None = None) -> RevisionSchedule:
    """Enregistre une révision et reprogramme l'élément."""
    now = now or datetime.now(UTC)
    schedule = schedule_for(db, user_id, item_type, item_id)
    if schedule is None:
        schedule = RevisionSchedule(user_id=user_id, item_type=item_type, item_id=item_id, ease=2.5,
                                    interval_days=0.0, repetitions=0, lapses=0, mastery="nouveau", due_at=now)
        db.add(schedule)
    before = schedule.interval_days
    state = next_state(schedule, rating, params(db), relearn=relearn)
    delay = state.pop("delay")
    for key, value in state.items():
        setattr(schedule, key, value)
    schedule.due_at = now + delay
    schedule.last_rating = rating
    schedule.last_reviewed_at = now
    db.add(RevisionReview(
        user_id=user_id, item_type=item_type, item_id=item_id, rating=rating, graded_by=graded_by, result=result,
        answer_text=answer_text, interval_before=before, interval_after=schedule.interval_days,
        ease_after=schedule.ease, due_after=schedule.due_at,
    ))
    return schedule


def exercise_rating(result: str, after_correction: bool) -> int | None:
    """Traduit le résultat d'un exercice en note. Une bonne réponse donnée après avoir vu le corrigé ne vaut
    que « difficile » : consulter une correction n'est jamais une preuve de maîtrise."""
    if result == "incorrect":
        return 0
    if result == "partial":
        return 1
    if result == "correct":
        return 1 if after_correction else 2
    return None


def record_exercise_result(db: Session, user_id: int, exercise_id: int, result: str, after_correction: bool) -> None:
    """Un exercice échoué entre dans le planning ; il en sort progressivement quand il est réussi."""
    rating = exercise_rating(result, after_correction)
    if rating is None:
        return
    if rating == 2 and schedule_for(db, user_id, "exercise", exercise_id) is None:
        return  # réussi du premier coup : rien à revoir
    review(db, user_id, "exercise", exercise_id, rating, graded_by="server", result=result, relearn=False)
