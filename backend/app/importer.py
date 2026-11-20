"""Import en lot d'un dossier rangé « Matière/Niveau/fichier » (ex. documents_organisés).

- Le classement (matière, niveau) vient du chemin du dossier.
- Les fichiers sans nom parlant (ex. « 4_5951744891707984739.pdf », « file (1).pdf ») ou rangés dans
  « Divers » sont identifiés d'après leur contenu : titre, niveau, matière et type sont proposés,
  et la source de chaque proposition est notée dans le journal. L'administrateur valide toujours
  chaque exercice avant publication.
- Les originaux sont copiés dans le stockage (le dossier source n'est jamais modifié).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import extraction, programmes, storage
from app.audit import record
from app.models import Document, Grade, Subject, Track
from app.processing import run_extraction, segment_document

GRADE_CODES = {
    "cp": ("CP", -4), "ce1": ("CE1", -3), "ce2": ("CE2", -2), "cm1": ("CM1", -1), "cm2": ("CM2", 0),
    "6eme": ("6E", 1), "5eme": ("5E", 2), "4eme": ("4E", 3), "3eme": ("3E", 4),
    "2nde": ("2NDE", 5), "seconde": ("2NDE", 5), "1ere": ("1RE", 6), "premiere": ("1RE", 6),
    "terminale": ("TLE", 7), "bts": ("BTS", 8),
}
SERIES_GRADES = {"2NDE", "1RE", "TLE"}
UNNAMED = re.compile(
    r"^(\d+_\d+|file|document|doc|scan\w*|img\w*|image\w*|sans titre|untitled|cori?g[ée]e?|correction)"
    r"\s*(\(\d+\)|\d+)?$",
    re.IGNORECASE,
)


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def is_unnamed(stem: str) -> bool:
    return bool(UNNAMED.match(stem.strip()))


@dataclass
class ImportReport:
    imported: list[dict] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


class Referentials:
    """Retrouve (ou crée sur demande) niveaux et matières à partir des noms de dossiers."""

    def __init__(self, db: Session, create: bool):
        self.db, self.create = db, create

    def grade(self, label: str | None) -> Grade | None:
        if not label:
            return None
        key = norm(label)
        code, order = GRADE_CODES.get(key, (label.upper()[:30], 99))
        for grade in self.db.scalars(select(Grade)):
            if norm(grade.name) == key or norm(grade.code) in (key, norm(code)):
                return grade
        if not self.create:
            return None
        grade = Grade(code=code, name=label, sort_order=order)
        self.db.add(grade)
        self.db.flush()
        return grade

    def track(self, grade: Grade | None, letter: str) -> Track | None:
        """Série d'un niveau (ex. Tle C) ; créée si besoin, uniquement pour 2nde, 1ère et Terminale."""
        if grade is None or grade.code not in SERIES_GRADES:
            return None
        # seules les séries du programme ivoirien (2nde A/C ; 1ère et Tle A/C/D/E) : « 2nde G… » n'en est pas une
        if letter[:1] not in programmes.SERIES_BY_GRADE.get(grade.code, []):
            return None
        code = f"{grade.code}-{letter}"
        track = self.db.scalar(select(Track).where(Track.code == code))
        if track is None and self.create:
            track = Track(grade_id=grade.id, code=code, name=f"{grade.name} {letter}", kind="serie",
                          sort_order=ord(letter[0]) * 10 + (int(letter[1:]) if letter[1:].isdigit() else 0))
            self.db.add(track)
            self.db.flush()
        return track

    def subject(self, label: str | None) -> Subject | None:
        if not label:
            return None
        key = norm(label)
        for subject in self.db.scalars(select(Subject)):
            if norm(subject.name) == key or norm(subject.code) == key or (len(key) > 3 and norm(subject.name).startswith(key)):
                return subject
        if not self.create:
            return None
        subject = Subject(code=re.sub(r"[^A-Z0-9]+", "-", unicodedata.normalize("NFKD", label)
                                      .encode("ascii", "ignore").decode().upper()).strip("-")[:40], name=label)
        self.db.add(subject)
        self.db.flush()
        return subject


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.name.startswith(".") and not path.name.startswith("._"):
            yield path


def import_folder(
    factory: sessionmaker, root: Path, *, create_referentials: bool = False, extract: bool = False,
    segment: bool = False, dry_run: bool = False, log=print,
) -> ImportReport:
    report = ImportReport()
    root = root.resolve()
    max_bytes = 2000 * 1024 * 1024
    for path in iter_files(root):
        relative = Path(unicodedata.normalize("NFC", str(path.relative_to(root))))
        mime = storage.mime_for(path.name) or extraction.sniff_mime(path)  # extension trompeuse : on regarde le contenu
        if mime is None:
            report.skipped.append((str(relative), "format non pris en charge"))
            continue
        parts = relative.parts[:-1]
        folder_subject = parts[0] if parts and norm(parts[0]) != "divers" else None
        folder_grade = parts[1] if len(parts) > 1 else None
        with factory() as db:
            refs = Referentials(db, create_referentials and not dry_run)
            with path.open("rb") as source:
                if dry_run:
                    import hashlib

                    sha = hashlib.file_digest(source, "sha256").hexdigest()
                    key, size = None, path.stat().st_size
                else:
                    key, size, sha = storage.save_stream(source, "originals", path.name, max_bytes)
            existing = db.scalar(select(Document).where(Document.sha256 == sha))
            if existing is not None:
                report.skipped.append((str(relative), f"doublon du document n° {existing.id}"))
                continue
            subject, grade = refs.subject(folder_subject), refs.grade(folder_grade)
            entry = {"file": str(relative), "title": path.stem, "subject": folder_subject, "grade": folder_grade,
                     "kind": "autre", "source": "dossier"}
            if dry_run:
                report.imported.append(entry)
                continue
            document = Document(
                title=path.stem[:255], original_filename=path.name[:255], storage_key=key, mime_type=mime,
                size_bytes=size, sha256=sha, kind="autre",
                grade_id=grade.id if grade else None, subject_id=subject.id if subject else None,
            )
            db.add(document)
            db.flush()
            record(db, None, "import", "document", document.id, path=str(relative), source="import-folder")
            db.commit()
            document_id = document.id
        entry["id"] = document_id

        if extract or segment:
            run_extraction(document_id, factory, None)
        with factory() as db:
            document = db.get(Document, document_id)
            if document.status == "extracted":
                text = "\n".join(p.text for p in document.pages[:3])
                guess = extraction.identify(text, path.name)
                refs = Referentials(db, create_referentials)
                applied = {}
                if guess.get("kind"):
                    document.kind = applied["kind"] = guess["kind"]
                if is_unnamed(path.stem) and guess.get("title"):
                    document.title = applied["title"] = guess["title"][:255]
                if document.subject_id is None and guess.get("subject"):
                    found = refs.subject(guess["subject"])
                    if found:
                        document.subject_id, applied["subject"] = found.id, guess["subject"]
                if document.grade_id is None and guess.get("grade"):
                    found = refs.grade(guess["grade"])
                    if found:
                        document.grade_id, applied["grade"] = found.id, guess["grade"]
                if not document.tracks and guess.get("series"):
                    grade = db.get(Grade, document.grade_id) if document.grade_id else None
                    tracks = [t for t in (refs.track(grade, letter) for letter in guess["series"]) if t]
                    if tracks:
                        document.tracks = tracks
                        applied["series"] = [t.name for t in tracks]
                if applied:
                    record(db, None, "identify", "document", document_id, applied=applied, source="contenu du document")
                    entry.update(applied)
                    entry["source"] = "contenu" if {"title", "subject", "grade"} & applied.keys() else entry["source"]
                db.commit()
                if segment:
                    try:
                        created, linked = segment_document(db, document, None)
                        entry.update(exercises=created, corrections=linked)
                    except ValueError as exc:
                        entry["segment_error"] = str(exc)
            entry["status"] = document.status
            entry["pages"] = document.page_count
        report.imported.append(entry)
        log(f"[{len(report.imported)}] {relative} → {entry.get('title')} | {entry.get('subject')} | "
            f"{entry.get('grade')} {','.join(entry.get('series', []))} | {entry.get('kind')} | {entry.get('status', '')} | "
            f"exercices={entry.get('exercises', '-')}")
    return report
