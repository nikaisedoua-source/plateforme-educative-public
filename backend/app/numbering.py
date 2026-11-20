"""Numérotation des exercices vue par l'élève.

Décision de l'utilisateur (2026-11-20) : « chaque exercice doit être renommé selon l'ordre d'arrivée dans la
matière ; s'il y a 60 exercices de maths en seconde C, on ira de Exercice 1 à Exercice 60 ».

Pour un élève, les exercices visibles d'une matière (son niveau, sa série) sont numérotés 1, 2, 3… dans leur
ordre d'arrivée sur le site : la première décision « retenu » de la sélection (les décisions d'un document sont
prises dans l'ordre des pages, donc l'ordre du document est conservé), puis la date de publication. Un nouvel
exercice prend le numéro suivant : les numéros déjà vus par les élèves ne changent pas.
Le titre d'origine (thème, numéro dans le document) reste connu de l'administration et de la source.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Exercise
from app.selection import ACTION, KEPT

LAST = float("inf")


def arrivals(db: Session) -> dict[int, int]:
    """Exercice → numéro de sa première décision « retenu » (ordre d'arrivée)."""
    first: dict[int, int] = {}
    entries = db.execute(select(AuditLog.entity_id, AuditLog.id, AuditLog.details).where(
        AuditLog.action == ACTION, AuditLog.entity_type == "exercise").order_by(AuditLog.id))
    for exercise_id, entry_id, details in entries:
        if (details or {}).get("verdict") == KEPT:
            first.setdefault(exercise_id, entry_id)
    return first


def numbers(db: Session, visible) -> dict[int, int]:
    """Numéro de chaque exercice visible, par matière. `visible` : requête des exercices que voit l'élève."""
    order = arrivals(db)
    rows = db.execute(visible.with_only_columns(Exercise.id, Exercise.subject_id, Exercise.published_at)).all()
    by_subject: dict[int | None, list] = {}
    for exercise_id, subject_id, published_at in rows:
        by_subject.setdefault(subject_id, []).append(
            (order.get(exercise_id, LAST), published_at.timestamp() if published_at else LAST, exercise_id))
    result: dict[int, int] = {}
    for items in by_subject.values():
        for rank, (_, _, exercise_id) in enumerate(sorted(items), 1):
            result[exercise_id] = rank
    return result


def label(number: int | None, fallback: str) -> str:
    return f"Exercice {number}" if number else fallback
