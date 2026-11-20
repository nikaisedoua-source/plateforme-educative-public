"""Traitements documentaires : extraction en arrière-plan, découpage, captures des figures."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app import extraction, storage
from app.audit import record
from app.models import Correction, Document, DocumentPage, Exercise, ExerciseAsset


def run_extraction(document_id: int, factory: sessionmaker, actor_id: int | None) -> None:
    """Extrait le texte page par page (OCR si besoin) ; met à jour la progression au fil de l'eau."""
    with factory() as db:
        document = db.get(Document, document_id)
        if document is None:
            return
        path = storage.resolve(document.storage_key)
        try:
            document.page_count = extraction.page_count(path, document.mime_type)
            document.pages_done = 0
            db.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
            db.commit()
            for number, text, method in extraction.extract_pages(path, document.mime_type):
                db.add(DocumentPage(document_id=document_id, page_number=number, text=text, method=method))
                document.pages_done = number
                db.commit()
            document.status = "extracted"
            document.extracted_at = datetime.now(UTC)
            document.extraction_error = None
            record(db, actor_id, "extract", "document", document_id, pages=document.pages_done)
        except Exception as exc:  # l'erreur est montrée à l'administrateur, rien n'est publié
            db.rollback()
            document = db.get(Document, document_id)
            document.status = "failed"
            document.extraction_error = str(exc)[:500]
        db.commit()


def _heading_positions(path: Path, page_number: int, headings: list[str]) -> list[float | None]:
    """Position verticale (fraction depuis le haut) de chaque titre d'exercice sur la page."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        page = pdf[page_number - 1]
        height = page.get_height()
        textpage = page.get_textpage()
        positions: list[float | None] = []
        for heading in headings:
            needle = heading.strip()[:30]
            searcher = textpage.search(needle, match_case=False) if needle else None
            found = searcher.get_next() if searcher else None
            if found:
                index, _count = found
                _left, _bottom, _right, top = textpage.get_charbox(index)
                positions.append(1 - top / height)
            else:
                positions.append(None)
        return positions
    finally:
        pdf.close()


def attach_visuals(db: Session, document: Document, exercises: list[tuple[Exercise, extraction.Segment]]) -> int:
    """Captures : figures recadrées si la page contient des images, page entière si elle est scannée
    ou contient un schéma vectoriel. Les pages purement textuelles ne reçoivent aucune capture."""
    if document.mime_type != "application/pdf" or not exercises:
        return 0
    path = storage.resolve(document.storage_key)
    pages = {p.page_number: p for p in document.pages}
    created = 0
    for page_number in sorted({n for _, s in exercises for n in range(s.page_start, s.page_end + 1)}):
        on_page = [(e, s) for e, s in exercises if s.page_start <= page_number <= s.page_end]
        visuals = extraction.page_visuals(path, page_number)
        if not visuals.has_visuals:
            continue
        page = pages.get(page_number)
        if visuals.figures and not visuals.scanned and (page is None or page.method == "text"):
            starting = [(e, s) for e, s in on_page if s.page_start == page_number]
            positions = _heading_positions(path, page_number, [s.lines[0] for _, s in starting])
            anchors = sorted(
                ((pos, e) for pos, (e, _) in zip(positions, starting) if pos is not None), key=lambda item: item[0]
            )
            carried = [e for e, s in on_page if s.page_start < page_number]
            png = extraction.render_pdf_page(path, page_number)
            for index, box in enumerate(visuals.figures, start=1):
                owner = carried[-1] if carried else (on_page[0][0] if on_page else None)
                for pos, exercise in anchors:
                    if pos <= box[1] + 0.02:
                        owner = exercise
                key = f"figures/{document.id}/p{page_number}_{index}.png"
                target = storage.resolve(key)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(extraction.crop_png(png, box))
                owner.assets.append(ExerciseAsset(
                    kind="image", storage_key=key, caption=f"Figure — page {page_number}",
                    sort_order=len(owner.assets),
                ))
                created += 1
        else:
            for exercise, _ in on_page:
                exercise.assets.append(ExerciseAsset(
                    kind="page", page_number=page_number, caption=f"Capture de la page {page_number}",
                    sort_order=len(exercise.assets),
                ))
                created += 1
    return created


def segment_document(
    db: Session, document: Document, actor_id: int, correction_document: Document | None = None, replace: bool = False
) -> tuple[int, int]:
    """Crée les exercices (statut « extracted ») et associe les corrections trouvées par numéro."""
    existing = list(db.scalars(select(Exercise).where(Exercise.document_id == document.id)))
    if existing and not replace:
        raise ValueError("Des exercices existent déjà pour ce document (utiliser replace=true)")
    kept_titles: set[str] = set()
    for exercise in existing:
        if exercise.status == "validated" or exercise.is_published or exercise.published_at is not None:
            kept_titles.add(exercise.title)  # on ne touche jamais à un contenu validé ou déjà publié
            continue
        db.delete(exercise)
    db.flush()

    pages = [(p.page_number, p.text) for p in document.pages]
    segments = extraction.segment(pages, all_corrections=document.kind == "corrige")
    exercise_segments = [s for s in segments if s.kind == "exercise" and s.label[:200] not in kept_titles]
    correction_segments = [s for s in segments if s.kind == "correction"]
    correction_source = document
    if correction_document is not None:
        correction_source = correction_document
        correction_segments = [
            s for s in extraction.segment(
                [(p.page_number, p.text) for p in correction_document.pages], all_corrections=True
            )
        ]

    classification = {
        "grade_id": document.grade_id,
        "subject_id": document.subject_id, "chapter_id": document.chapter_id,
    }
    # Association par (leçon, numéro) ; à défaut par numéro seul s'il est sans ambiguïté des deux côtés.
    corrections_by_key: dict[tuple, extraction.Segment] = {}
    corrections_by_number: dict[str, list[extraction.Segment]] = {}
    for seg in correction_segments:
        corrections_by_key.setdefault(seg.key, seg)
        if seg.number:
            corrections_by_number.setdefault(seg.number, []).append(seg)
    exercise_keys: dict[tuple, int] = {}
    exercise_numbers: dict[str, int] = {}
    for seg in exercise_segments:
        exercise_keys[seg.key] = exercise_keys.get(seg.key, 0) + 1
        if seg.number:
            exercise_numbers[seg.number] = exercise_numbers.get(seg.number, 0) + 1

    created: list[tuple[Exercise, extraction.Segment]] = []
    linked = 0
    titles: dict[str, int] = {}
    for order, seg in enumerate(exercise_segments):
        titles[seg.label] = titles.get(seg.label, 0) + 1
        title = seg.label if titles[seg.label] == 1 else f"{seg.label} ({titles[seg.label]})"
        exercise = Exercise(
            document_id=document.id, page_start=seg.page_start, page_end=seg.page_end,
            source_number=seg.number, title=title[:200], original_text=seg.text, statement=seg.text,
            exercise_type="libre", difficulty=2, status="extracted", sort_order=order, **classification,
        )
        exercise.tracks = list(document.tracks)
        match = corrections_by_key.get(seg.key) if exercise_keys[seg.key] == 1 else None
        if match is None and seg.number and exercise_numbers.get(seg.number) == 1:
            candidates = corrections_by_number.get(seg.number, [])
            match = candidates[0] if len(candidates) == 1 else None
        if match is not None:
            exercise.correction = Correction(
                original_text=match.text, steps=match.text, source_document_id=correction_source.id,
                source_page=match.page_start, status="extracted",
            )
            linked += 1
        db.add(exercise)
        created.append((exercise, seg))
    db.flush()
    figures = attach_visuals(db, document, created)
    record(db, actor_id, "segment", "document", document.id, exercises=len(created), corrections=linked, captures=figures)
    db.commit()
    return len(created), linked
