"""Sélection des exercices, un par un, sur la page du document.

Décisions de l'utilisateur (2026-11-20) : « ouvre le contenu du document et sélectionne les exercices au lieu de
faire de la loterie », « il faut sélectionner des exercices et non des cours », « arrête de travailler avec le
modèle local, il faut tout faire toi-même ».

Le découpage automatique proposait comme « exercice » tout bloc titré (activités de découverte suivies de leur
réponse, pages de cours, fiches de préparation du professeur, corrigés, tableaux déjà cochés, deux exercices dans
une même capture…). Désormais un exercice n'est montré aux élèves que s'il a été examiné sur la page rendue du
document et retenu :

- c'est un exercice : une consigne que l'élève doit traiter seul (pas un cours, un résumé « Récapitulons », une
  fiche de préparation, un exemple résolu ni un corrigé) ;
- aucune réponse n'est visible (cases cochées, réponses imprimées en couleur, tableau rempli) ;
- l'énoncé est complet (données, figures, tableaux) ;
- la capture montre cet exercice et lui seul : la zone exacte (page, haut, bas, gauche, droite en fractions de
  la page) est enregistrée avec la décision et sert à découper l'image montrée à l'élève.

Chaque décision est inscrite au journal (action « select_exercise ») avec sa raison ; la plus récente fait foi.
Un exercice écarté n'est pas supprimé : il reste consultable par l'administrateur.
"""

import io
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import extraction, storage
from app.audit import record
from app.models import AuditLog, Document, Exercise

ACTION = "select_exercise"
KEPT, DROPPED = "retenu", "écarté"
NOT_SELECTED = "pas encore sélectionné (chaque exercice est vérifié sur la page du document)"
ZONE_DPI = 150
MAX_WIDTH = 1100


@dataclass(frozen=True)
class Zone:
    page: int
    top: float
    bottom: float
    left: float = 0.0
    right: float = 1.0

    @classmethod
    def parse(cls, value: dict) -> "Zone":
        zone = cls(int(value["page"]), float(value["top"]), float(value["bottom"]),
                   float(value.get("left", 0.0)), float(value.get("right", 1.0)))
        if not (0 <= zone.top < zone.bottom <= 1 and 0 <= zone.left < zone.right <= 1):
            raise ValueError(f"zone invalide : {value}")
        return zone

    def as_dict(self) -> dict:
        return {"page": self.page, "top": self.top, "bottom": self.bottom, "left": self.left, "right": self.right}


def decisions(db: Session, ids: list[int] | None = None) -> dict[int, AuditLog]:
    """Dernière décision de sélection de chaque exercice."""
    query = select(AuditLog).where(AuditLog.action == ACTION, AuditLog.entity_type == "exercise")
    if ids is not None:
        query = query.where(AuditLog.entity_id.in_(ids))
    latest: dict[int, AuditLog] = {}
    for entry in db.scalars(query.order_by(AuditLog.id)):
        latest[entry.entity_id] = entry
    return latest


def kept_ids(db: Session) -> set[int]:
    return {i for i, entry in decisions(db).items() if entry.details.get("verdict") == KEPT}


def is_kept(db: Session, exercise: Exercise, cache: dict | None = None) -> bool:
    if cache is None:
        entry = decisions(db, [exercise.id]).get(exercise.id)
        return bool(entry and entry.details.get("verdict") == KEPT)
    if "kept" not in cache:
        cache["kept"] = kept_ids(db)
    return exercise.id in cache["kept"]


def zones_of(db: Session, exercise_id: int) -> tuple[list[Zone], int | None]:
    """Zones retenues pour la capture (et numéro de la décision, pour le cache d'image)."""
    entry = decisions(db, [exercise_id]).get(exercise_id)
    if not entry or entry.details.get("verdict") != KEPT or not entry.details.get("zones"):
        return [], None
    return [Zone.parse(z) for z in entry.details["zones"]], entry.id


def zone_image(document: Document, zones: list[Zone]) -> bytes | None:
    """Capture de l'exercice : chaque zone découpée dans sa page, empilées."""
    from PIL import Image

    path = storage.resolve(document.storage_key)
    if document.mime_type != "application/pdf" or not path.exists() or not zones:
        return None
    parts = []
    for zone in zones:
        page = Image.open(io.BytesIO(extraction.render_pdf_page(path, zone.page, dpi=ZONE_DPI))).convert("RGB")
        w, h = page.size
        parts.append(page.crop((int(zone.left * w), int(zone.top * h), int(zone.right * w), int(zone.bottom * h))))
    width = max(p.width for p in parts)
    canvas = Image.new("RGB", (width, sum(p.height for p in parts)), "white")
    y = 0
    for part in parts:
        canvas.paste(part, (0, y))
        y += part.height
    if canvas.width > MAX_WIDTH:
        canvas = canvas.resize((MAX_WIDTH, int(canvas.height * MAX_WIDTH / canvas.width)))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def decide(db: Session, exercise: Exercise, keep: bool, reason: str, zones: list[Zone] | None = None,
           title: str | None = None, actor_id: int | None = None) -> str:
    """Enregistre la décision et publie (ou retire) l'exercice en conséquence. Renvoie l'issue."""
    from app.publication import publish

    if keep and not zones and exercise.document.mime_type == "application/pdf":
        raise ValueError(f"exercice {exercise.id} : la zone de la capture est obligatoire")
    details = {"verdict": KEPT if keep else DROPPED, "raison": reason,
               "par": "Claude (examen de la page du document)"}
    if zones:
        details["zones"] = [z.as_dict() for z in zones]
    if title and title.strip() and title.strip() != exercise.title:
        details["titre_avant"] = exercise.title
        exercise.title = title.strip()[:200]
    record(db, actor_id, ACTION, "exercise", exercise.id, **details)
    db.flush()
    if not keep:
        exercise.is_published = False
        return DROPPED
    outcome = publish(db, exercise, datetime.now(UTC), {"kept": {exercise.id}})
    return outcome or "publié"


def unpublish_unselected(db: Session) -> int:
    """Retire de la publication tout exercice qui n'a pas été retenu."""
    kept = kept_ids(db)
    count = 0
    for exercise in db.scalars(select(Exercise).where(Exercise.is_published.is_(True))):
        if exercise.id not in kept:
            exercise.is_published = False
            count += 1
    return count


def preview_page(document: Document, page: int, dpi: int = 90) -> bytes:
    """Page rendue avec une règle (traits tous les 5 %, repères de gauche à droite) pour relever les zones."""
    from PIL import Image, ImageDraw

    path = storage.resolve(document.storage_key)
    image = Image.open(io.BytesIO(extraction.render_pdf_page(path, page, dpi=dpi))).convert("RGB")
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for step in range(1, 20):
        y = int(h * step / 20)
        draw.line([(0, y), (w, y)], fill=(0, 160, 255) if step % 2 else (255, 0, 160), width=1)
        draw.text((2, y - 11), f"{step * 5}", fill=(255, 0, 160))
    for step in (1, 2, 3):
        x = int(w * step / 4)
        draw.line([(x, 0), (x, h)], fill=(0, 200, 120), width=1)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def apply_file(db: Session, path: str, log=print) -> dict:
    """Applique un fichier de décisions : [{"id", "garder", "raison", "zones": [...], "titre"?}, …]."""
    import json

    totals: dict = {}
    items = json.loads(open(path, encoding="utf-8").read())
    for item in items:
        if "id" not in item:  # exercice présent sur la page mais manqué par le découpage automatique
            item["id"] = create_exercise(db, int(item["document"]), item["titre"],
                                         [Zone.parse(z) for z in item["zones"]]).id
            log(f"exercice {item['id']} créé d'après la page ({item['titre']})")
            db.commit()
            with open(path, "w", encoding="utf-8") as handle:  # rejouer le fichier ne recrée pas l'exercice
                json.dump(items, handle, ensure_ascii=False, indent=1)
        exercise = db.get(Exercise, int(item["id"]))
        if exercise is None:
            log(f"exercice {item['id']} introuvable")
            continue
        zones = [Zone.parse(z) for z in item.get("zones", [])]
        outcome = decide(db, exercise, bool(item["garder"]), item["raison"], zones, item.get("titre"))
        db.commit()
        totals[outcome] = totals.get(outcome, 0) + 1
        log(f"exercice {exercise.id} ({exercise.title}) : {outcome}")
    return totals


def zone_text(document: Document, zones: list[Zone]) -> str:
    """Texte du document à l'intérieur des zones (couche texte du PDF ; vide pour une page scannée)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(storage.resolve(document.storage_key)))
    try:
        parts = []
        for zone in zones:
            page = pdf[zone.page - 1]
            width, height = page.get_size()
            parts.append(page.get_textpage().get_text_bounded(
                left=zone.left * width, bottom=(1 - zone.bottom) * height,
                right=zone.right * width, top=(1 - zone.top) * height).strip())
        return "\n".join(p for p in parts if p)
    finally:
        pdf.close()


def create_exercise(db: Session, document_id: int, title: str, zones: list[Zone]) -> Exercise:
    """Crée l'exercice qu'on voit sur la page mais que le découpage automatique a manqué. Le texte vient de la
    zone du document ; l'élève voit la capture de cette zone."""
    from app.publication import _inherit

    document = db.get(Document, document_id)
    text = zone_text(document, zones) or title
    exercise = Exercise(document_id=document.id, page_start=min(z.page for z in zones),
                        page_end=max(z.page for z in zones), title=title[:200], original_text=text,
                        statement=text, exercise_type="libre", difficulty=2, status="extracted",
                        sort_order=1000 + min(z.page for z in zones))
    db.add(exercise)
    _inherit(exercise, document)
    db.flush()
    record(db, None, "create_exercise", "exercise", exercise.id, document=document.id,
           raison="exercice visible sur la page, manqué par le découpage automatique")
    return exercise


def classify_document(db: Session, document_id: int, subject: str, grade: str, tracks: list[str], proof: str) -> int:
    """Classe un document d'après ce qui est écrit dedans (`proof`), et ses exercices encore sans classement."""
    from app.models import Grade, Subject, Track

    document = db.get(Document, document_id)
    subject_row = db.scalar(select(Subject).where(Subject.name == subject))
    grade_row = db.scalar(select(Grade).where(Grade.name == grade))
    track_rows = [db.scalar(select(Track).where(Track.name == t, Track.grade_id == grade_row.id)) for t in tracks]
    if subject_row is None or grade_row is None or None in track_rows:
        raise ValueError(f"classement inconnu : {subject} / {grade} / {tracks}")
    before = {"matiere": document.subject_id, "niveau": document.grade_id, "series": [t.name for t in document.tracks]}
    document.subject_id, document.grade_id, document.tracks = subject_row.id, grade_row.id, track_rows
    count = 0
    for exercise in db.scalars(select(Exercise).where(Exercise.document_id == document.id)):
        exercise.subject_id, exercise.grade_id, exercise.tracks = subject_row.id, grade_row.id, list(track_rows)
        count += 1
    record(db, None, "classify_document", "document", document.id, avant=before,
           apres={"matiere": subject, "niveau": grade, "series": tracks}, preuve=proof)
    return count
