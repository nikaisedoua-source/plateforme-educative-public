"""Vérification de chaque exercice publié et de l'exploitation de chaque document.

Pour chaque exercice publié :
- contrôle qualité (`publication.quality_problem`) : énoncé lisible, ni coupé, ni fusionné, ni sommaire ;
- classement : niveau et matière présents ; en 2nde, 1ère et Terminale, au moins une série, et toutes les
  séries de l'exercice appartiennent à son niveau (aucun mélange) ;
- doublons : le même énoncé publié deux fois pour un même niveau n'est gardé qu'une fois (le plus ancien).
Un exercice qui échoue est retiré de la publication (jamais supprimé) ; la raison est notée dans le journal.
Un exercice déjà travaillé par un élève reste publié et est seulement signalé dans le rapport.

Pour chaque document : pages extraites, exercices trouvés, exercices publiés, raison s'il n'apporte rien.
"""

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record
from app.classification import grade_has_tracks
from app.models import Document, Exercise, ExerciseAttempt
from app.publication import fingerprint, quality_problem


@dataclass
class VerificationReport:
    exercises: list[dict] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)
    totals: Counter = field(default_factory=Counter)




def exercise_problem(db: Session, exercise: Exercise, cache: dict) -> str | None:
    problem = quality_problem(exercise)
    if problem:
        return problem
    if exercise.grade_id is None:
        return "niveau non reconnu"
    if exercise.subject_id is None:
        return "matière non reconnue"
    if exercise.grade_id not in cache:
        cache[exercise.grade_id] = grade_has_tracks(db, exercise.grade_id)
    if cache[exercise.grade_id] and not exercise.tracks:
        return "série non reconnue (séries jamais mélangées)"
    if any(track.grade_id != exercise.grade_id for track in exercise.tracks):
        return "série d'un autre niveau (mélange interdit)"
    return None


def verify(db: Session, *, apply: bool = True, log=print) -> VerificationReport:
    report = VerificationReport()
    cache: dict = {}
    seen: dict[tuple, int] = {}
    answered = set(db.scalars(select(ExerciseAttempt.exercise_id).distinct()))
    published = db.scalars(select(Exercise).where(Exercise.is_published.is_(True)).order_by(Exercise.id))
    for exercise in published:
        problem = exercise_problem(db, exercise, cache)
        if problem is None:
            key = (exercise.grade_id, fingerprint(exercise.statement or ""))
            if key in seen:
                problem = f"doublon de l'exercice n° {seen[key]}"
            else:
                seen[key] = exercise.id
        if problem is None:
            report.totals["exercices vérifiés : conformes"] += 1
            continue
        kept = exercise.id in answered
        report.totals[f"retirés : {problem.split(' n° ')[0]}" if not kept else "signalés (déjà travaillés)"] += 1
        report.exercises.append({"id": exercise.id, "document_id": exercise.document_id, "title": exercise.title,
                                 "problem": problem, "action": "signalé" if kept else "retiré"})
        if apply and not kept:
            exercise.is_published = False
            record(db, None, "verify", "exercise", exercise.id, problem=problem, decision="retiré de la publication")
    if apply:
        db.commit()

    counts = dict(db.execute(select(Exercise.document_id, func.count()).group_by(Exercise.document_id)).all())
    shown = dict(db.execute(select(Exercise.document_id, func.count()).where(Exercise.is_published.is_(True))
                            .group_by(Exercise.document_id)).all())
    for document in db.scalars(select(Document).order_by(Document.id)):
        total, visible = counts.get(document.id, 0), shown.get(document.id, 0)
        if document.status != "extracted":
            reason = f"extraction : {document.status} {document.extraction_error or ''}".strip()
        elif document.kind == "corrige":
            reason = "livre de corrigés : sert aux corrections des exercices associés"
        elif total == 0:
            reason = "aucun exercice repéré (cours, lecture ou ouvrage de référence)"
        elif visible == 0:
            reason = "exercices non publiés (voir la liste des exercices)"
        else:
            reason = ""
        report.documents.append({
            "id": document.id, "title": document.title, "file": document.original_filename, "kind": document.kind,
            "status": document.status, "pages": document.page_count, "pages_extracted": len(document.pages),
            "exercises": total, "published": visible, "note": reason,
        })
        report.totals["documents"] += 1
        if visible:
            report.totals["documents avec exercices publiés"] += 1
    for key, value in sorted(report.totals.items()):
        log(f"{key} : {value}")
    return report
