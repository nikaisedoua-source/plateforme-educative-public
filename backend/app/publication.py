"""Publication automatique (décision de l'utilisateur du 2026-11-20 : « l'admin n'a rien à valider, il faut tout
extraire des documents fournis pour chaque classe »).

Tout contenu extrait d'un document (exercice, corrigé associé, carte mémoire) est publié automatiquement pour
le niveau et la ou les séries du document. Garde-fous conservés :
- un contenu sans niveau ou sans matière reconnus n'est pas publié (on ne saurait pas à qui le montrer) ;
- en 2nde, 1ère et Terminale, un contenu sans série reconnue n'est pas publié : les séries ne sont jamais
  mélangées (un exercice de Tle C n'est jamais montré en Tle A) ;
- un contenu rejeté ou archivé par l'administrateur n'est jamais republié ;
- le réglage « publication » permet de revenir à la validation manuelle sans modifier le code.
"""

from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification import grade_has_tracks
from app.models import AppSetting, Document, Exercise, Flashcard


DEFAULT_AUTO = True  # décision utilisateur ; réglable par l'administrateur (réglage « publication »)


def auto_enabled(db: Session) -> bool:
    setting = db.get(AppSetting, "publication")
    value = setting.value if setting and isinstance(setting.value, dict) else {}
    return bool(value.get("auto", DEFAULT_AUTO))


def blocking_reason(db: Session, item: Exercise | Flashcard, cache: dict | None = None) -> str | None:
    if item.grade_id is None:
        return "niveau non reconnu"
    if item.subject_id is None:
        return "matière non reconnue"
    if not item.tracks:
        key = ("tracks", item.grade_id)
        if cache is None or key not in cache:
            value = grade_has_tracks(db, item.grade_id)
            if cache is not None:
                cache[key] = value
        else:
            value = cache[key]
        if value:
            return "série non reconnue (séries jamais mélangées)"
    text = item.statement if isinstance(item, Exercise) else item.question
    if not (text or "").strip():
        return "texte vide"
    return None


def _inherit(item: Exercise | Flashcard, document: Document) -> None:
    """Un contenu jamais retouché reprend le classement (niveau, matière, séries) de son document."""
    if item.grade_id is None and document.grade_id is not None:
        item.grade_id = document.grade_id
    if item.subject_id is None and document.subject_id is not None:
        item.subject_id = document.subject_id
    if not item.tracks and document.tracks and item.grade_id == document.grade_id:
        item.tracks = list(document.tracks)


def publish(db: Session, item: Exercise | Flashcard, now: datetime, cache: dict | None = None) -> str | None:
    """Publie un contenu s'il peut l'être ; renvoie la raison sinon."""
    if item.is_archived or item.status == "rejected":
        return "retiré par l'administrateur"
    reason = blocking_reason(db, item, cache)
    if reason:
        return reason
    if item.status != "validated":
        item.status = "validated"
        item.validated_at = now
    item.is_published = True
    item.published_at = item.published_at or now
    if isinstance(item, Exercise) and item.correction is not None and item.correction.status in ("extracted", "transformed", "pending_validation"):
        item.correction.status = "validated"
    return None


def publish_document(db: Session, document: Document) -> Counter:
    """Publie les contenus d'un document (appelé après chaque découpage si la publication est automatique)."""
    report: Counter = Counter()
    if not auto_enabled(db) or document.status == "archived":
        return report
    now, cache = datetime.now(UTC), {}
    exercises = db.scalars(select(Exercise).where(Exercise.document_id == document.id))
    cards = db.scalars(select(Flashcard).where(Flashcard.document_id == document.id))
    for kind, items in (("exercices", exercises), ("cartes", cards)):
        for item in items:
            if item.is_published:
                report[f"{kind} déjà publiés"] += 1
                continue
            if item.validated_by is None:
                _inherit(item, document)
            reason = publish(db, item, now, cache)
            report[f"{kind} publiés" if reason is None else f"{kind} non publiés : {reason}"] += 1
    return report


def publish_all(db: Session, log=print) -> Counter:
    total: Counter = Counter()
    for document in db.scalars(select(Document).where(Document.status == "extracted").order_by(Document.id)):
        report = publish_document(db, document)
        db.commit()
        total.update(report)
        blocked = {k: v for k, v in report.items() if "non publiés" in k}
        if blocked:
            log(f"[{document.id}] {document.title} : {dict(report)}")
    return total

