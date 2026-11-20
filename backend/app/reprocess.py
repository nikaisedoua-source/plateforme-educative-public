"""Retraitement de toute la bibliothèque : chaque document est exploité jusqu'à la dernière page.

Pour chaque document non archivé :
1. ré-extraction si l'extraction a échoué, n'est pas allée jusqu'au bout ou si une page a une couche texte illisible ;
2. niveau et séries proposés d'après le nom de fichier et l'en-tête (jamais mélangés : Tle C ≠ Tle A ≠ 1ère C) ;
3. nouveau découpage en exercices (les exercices validés ou publiés ne sont jamais touchés) ;
4. un document qui ne contient que des corrigés est classé « corrigé » ;
5. chaque livre de corrigés est associé au cahier d'exercices correspondant (même matière, même niveau,
   titres proches, numéros d'exercices concordants) et les corrigés sont rattachés aux exercices.
Chaque décision automatique est notée dans le journal d'audit ; tout reste à valider par l'administrateur.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from collections import Counter

from app import extraction, programmes
from app.audit import record
from app.importer import Referentials, norm
from app.models import Document, Exercise, Grade, Subject
from app.processing import run_extraction, segment_document

STOPWORDS = {
    "corrige", "corriges", "correction", "corrections", "solution", "solutions", "pdf", "de", "du", "des", "la", "le",
    "les", "et", "en", "au", "aux", "maths", "math", "mathematiques", "livre", "cahier", "eleve", "professeur",
    "guide", "pedagogique", "habilete", "habiletes", "exercices", "exercice", "tome", "edition", "nouvelle",
}


def tokens(title: str) -> set[str]:
    words = re.split(r"[^a-z0-9]+", norm_spaces(title))
    return {w for w in words if len(w) > 1 and w not in STOPWORDS}


def norm_spaces(value: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()


@dataclass
class ReprocessReport:
    rows: list[dict] = field(default_factory=list)
    pairs: list[dict] = field(default_factory=list)


def _needs_extraction(document: Document) -> str | None:
    if document.status in ("failed", "imported", "processing"):
        return f"statut « {document.status} »"
    if document.page_count and len(document.pages) < document.page_count:
        return f"{len(document.pages)}/{document.page_count} pages extraites"
    if any(page.method == "text" and extraction.garbled(page.text) for page in document.pages):
        return "couche texte illisible"
    return None


def _identify(db: Session, document: Document) -> dict:
    """Niveau (si absent) et séries (si aucune) d'après le nom de fichier et les premières pages."""
    applied: dict = {}
    text = "\n".join(page.text for page in document.pages[:3])
    guess = extraction.identify(text, document.original_filename)
    refs = Referentials(db, create=True)
    if document.grade_id is None and guess.get("grade"):
        grade = refs.grade(guess["grade"])
        if grade:
            document.grade_id, applied["grade"] = grade.id, grade.name
    if not document.tracks and guess.get("series") and document.grade_id:
        grade = db.get(Grade, document.grade_id)
        tracks = [t for t in (refs.track(grade, letter) for letter in guess["series"]) if t]
        if tracks:
            document.tracks = tracks
            applied["series"] = [t.name for t in tracks]
    if applied:
        record(db, None, "identify", "document", document.id, applied=applied, source="retraitement (contenu)")
    inferred = infer_series(db, document)
    if inferred:
        applied["series"] = inferred
    return applied


MIN_MENTIONS = 5


def _mentions(text: str, grade_code: str) -> Counter:
    """Nombre de fois où « Tle D », « 1ère C et D »… apparaît dans tout le document, pour son niveau."""
    group = {"TLE": 1, "1RE": 2, "2NDE": 3}[grade_code]
    counts: Counter = Counter()
    for match in extraction.SERIES_GRADE.finditer(text):
        if match.group(group) is None:
            continue
        for letter in re.findall(extraction._SERIE, match.group(0)[match.end(group) - match.start():]):
            counts["A" if letter.startswith("A") else letter] += 1
    return counts


def infer_series(db: Session, document: Document) -> list[str] | None:
    """Série d'un document de lycée qui n'en a pas (jamais devinée au hasard ; décision notée dans l'audit) :
    0. nom du fichier (« 1ère AB », « Tle SE », « TSM », « 2nde S ») ;
    1. mentions répétées du niveau et de la série dans le document (« Tle D » cité au moins 5 fois) ;
    2. sinon croisement avec le programme officiel (leçons propres à chaque série, programme commun).
    """
    if document.tracks or document.grade_id is None:
        return None
    grade = db.get(Grade, document.grade_id)
    allowed = programmes.SERIES_BY_GRADE.get(grade.code if grade else "")
    if not allowed:
        return None
    text = "\n".join(page.text or "" for page in document.pages)
    counts = {k: v for k, v in _mentions(text, grade.code).items() if k in allowed}
    letters: list[str] = extraction.identify_series("", document.original_filename or "")
    method, details = "nom du fichier", {}
    if letters:
        pass
    elif counts and max(counts.values()) >= MIN_MENTIONS:
        top = max(counts.values())
        letters = sorted(k for k, v in counts.items() if v >= max(MIN_MENTIONS, 0.3 * top))
        method, details = "mentions dans le document", counts
    else:
        subject = db.get(Subject, document.subject_id) if document.subject_id else None
        found = programmes.match_series(subject.name if subject else None, grade.code, text)
        if found:
            letters, method, details = [s for s in found.series if s in allowed], found.method, found.scores
    if not letters:
        return None
    subject = db.get(Subject, document.subject_id) if document.subject_id else None
    if "C" in letters and "E" in allowed and "E" not in letters and \
            programmes.subject_key(subject.name if subject else None) in programmes.E_FOLLOWS_C:
        letters = [*letters, "E"]  # en maths et physique-chimie, la série E suit le programme de la série C
    refs = Referentials(db, create=True)
    tracks = [t for t in (refs.track(grade, letter) for letter in letters) if t]
    if not tracks:
        return None
    document.tracks = tracks
    names = [t.name for t in tracks]
    record(db, None, "identify", "document", document.id, applied={"series": names}, method=method,
           details=details, source="séries déduites du contenu")
    return names


def _segments(document: Document, all_corrections: bool | None = None) -> list[extraction.Segment]:
    pages = [(p.page_number, p.text) for p in document.pages]
    return extraction.segment(pages, all_corrections=document.kind == "corrige" if all_corrections is None else all_corrections)


def _pair_score(exercise_doc: Document, corrige_doc: Document,
                exercise_keys: set, correction_keys: set) -> tuple[int, int]:
    common_words = len(tokens(exercise_doc.title) & tokens(corrige_doc.title))
    matching = len(exercise_keys & correction_keys)
    return common_words, matching


def reprocess(factory: sessionmaker, *, document_ids: list[int] | None = None, pair: bool = True,
              log=print) -> ReprocessReport:
    report = ReprocessReport()
    with factory() as db:
        query = select(Document.id).where(Document.status != "archived").order_by(Document.id)
        if document_ids:
            query = query.where(Document.id.in_(document_ids))
        ids = list(db.scalars(query))

    for document_id in ids:
        row: dict = {"id": document_id}
        with factory() as db:
            document = db.get(Document, document_id)
            row.update(title=document.title, file=document.original_filename)
            reason = _needs_extraction(document)
        if reason:
            row["reextract"] = reason
            run_extraction(document_id, factory, None)
        with factory() as db:
            document = db.get(Document, document_id)
            row["status"], row["pages"] = document.status, document.page_count
            if document.status != "extracted":
                row["error"] = document.extraction_error
                report.rows.append(row)
                log(f"[{document_id}] {document.title} → ÉCHEC : {document.extraction_error}")
                continue
            row.update(_identify(db, document))
            # Le nom du fichier dit s'il s'agit d'un livre de corrigés seul ou d'énoncés avec corrigés.
            named = extraction.kind_from_name(document.original_filename or document.title)
            if named and named != document.kind and (named == "corrige" or document.kind == "corrige"):
                record(db, None, "identify", "document", document_id, applied={"kind": named},
                       before=document.kind, source="retraitement (nom du fichier)")
                document.kind = row["kind"] = named
            # Un document fait uniquement de corrigés est un livre de corrigés.
            if document.kind != "corrige":
                found = _segments(document)
                exercises = sum(s.kind == "exercise" for s in found)
                corrections = sum(s.kind == "correction" for s in found)
                if exercises == 0 and corrections > 0:
                    record(db, None, "identify", "document", document_id, applied={"kind": "corrige"},
                           before=document.kind, source="retraitement (aucun énoncé, uniquement des corrigés)")
                    document.kind = row["kind"] = "corrige"
            db.commit()
            created, linked = segment_document(db, document, None, replace=True)
            row.update(exercises=created, corrections=linked, kind=document.kind,
                       series=", ".join(t.name for t in document.tracks))
        report.rows.append(row)
        log(f"[{document_id}] {row['title']} | {row.get('kind')} | séries : {row.get('series') or '—'} | "
            f"pages={row['pages']} | exercices={row['exercises']} | corrigés={row['corrections']}"
            + (f" | ré-extrait ({row['reextract']})" if reason else ""))

    if pair:
        report.pairs = pair_corrections(factory, log=log)
    return report


def pair_corrections(factory: sessionmaker, *, log=print) -> list[dict]:
    """Associe chaque livre de corrigés au cahier d'exercices qui lui correspond le mieux."""
    pairs: list[dict] = []
    with factory() as db:
        documents = list(db.scalars(select(Document).where(Document.status == "extracted")))
        corriges = [d for d in documents if d.kind == "corrige"]
        candidates = [d for d in documents if d.kind != "corrige"]
        keys: dict[int, set] = {}
        for document in candidates:
            keys[document.id] = {(s.section, s.number) for s in _segments(document) if s.kind == "exercise" and s.number}
        for corrige in corriges:
            correction_keys = {(s.section, s.number) for s in _segments(corrige, True) if s.number}
            best, best_score = None, (0, 0)
            for document in candidates:
                if document.subject_id != corrige.subject_id or document.grade_id != corrige.grade_id:
                    continue
                if corrige.tracks and document.tracks and not set(corrige.track_ids) & set(document.track_ids):
                    continue  # séries différentes : jamais associées
                score = _pair_score(document, corrige, keys.get(document.id, set()), correction_keys)
                if score > best_score:
                    best, best_score = document, score
            entry = {"corrige_id": corrige.id, "corrige": corrige.title}
            # Il faut au moins un mot du titre en commun ET des numéros d'exercices concordants.
            if best is None or best_score[0] == 0 or best_score[1] == 0:
                entry["result"] = "aucun cahier d'exercices correspondant"
                pairs.append(entry)
                log(f"Corrigé [{corrige.id}] {corrige.title} → aucun cahier correspondant")
                continue
            already = sum(
                1 for e in db.scalars(select(Exercise).where(Exercise.document_id == best.id)) if e.correction
            )
            created, linked = segment_document(db, best, None, correction_document=corrige, replace=True) \
                if best_score[1] > already else (None, already)
            entry.update(exercise_id=best.id, exercises=best.title, common_words=best_score[0],
                         matching_numbers=best_score[1], linked=linked,
                         result="associé" if created is not None else "déjà mieux associé")
            if created is not None:
                record(db, None, "pair_corrections", "document", best.id, correction_document_id=corrige.id,
                       linked=linked, source="retraitement")
                db.commit()
            pairs.append(entry)
            log(f"Corrigé [{corrige.id}] {corrige.title} → [{best.id}] {best.title} : {linked} corrigé(s) rattaché(s)")
    return pairs
