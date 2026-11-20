"""Extraction du texte des documents (texte natif, puis OCR hors ligne) et découpage en exercices.

Aucun contenu n'est inventé : on ne fait que lire et découper le document fourni.
Tout ce qui sort d'ici a le statut « extracted » et doit être relu par l'administrateur.
"""

import io
import re
import unicodedata
import subprocess
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from app.config import get_settings
from app.storage import BACKEND_DIR, IMAGE_TYPES

MIN_TEXT_CHARS = 40  # en dessous, la page est considérée comme scannée → OCR
RENDER_DPI = 200


class ExtractionError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Rendu et OCR
# ---------------------------------------------------------------------------

def ocr_command() -> Path | None:
    configured = Path(get_settings().ocr_command)
    if not configured.is_absolute():
        configured = BACKEND_DIR / configured
    return configured if configured.exists() else None


def ocr_png(png: bytes) -> str:
    command = ocr_command()
    if command is None:
        raise ExtractionError("OCR indisponible : compiler bin/ocr-vision (voir AGENTS.md)")
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        tmp.write(png)
        tmp.flush()
        result = subprocess.run([str(command), tmp.name], capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise ExtractionError(f"OCR en échec : {result.stderr.strip()[:200]}")
    return result.stdout.strip()


def render_pdf_page(path: Path, page_number: int, dpi: int = RENDER_DPI) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        if not 1 <= page_number <= len(pdf):
            raise ExtractionError("Page inexistante")
        image = pdf[page_number - 1].render(scale=dpi / 72).to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    finally:
        pdf.close()


def image_to_png(path: Path) -> bytes:
    from PIL import Image

    with Image.open(path) as image:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()


def render_page(path: Path, mime_type: str, page_number: int) -> bytes:
    if mime_type == "application/pdf":
        return render_pdf_page(path, page_number)
    if mime_type in IMAGE_TYPES and page_number == 1:
        return image_to_png(path)
    raise ExtractionError("Aperçu disponible uniquement pour les PDF et les images")


def page_count(path: Path, mime_type: str) -> int:
    if mime_type == "application/pdf":
        import pypdfium2 as pdfium

        try:
            pdf = pdfium.PdfDocument(str(path))
        except Exception as exc:
            raise ExtractionError(f"PDF illisible : {exc}") from None
        try:
            return len(pdf)
        finally:
            pdf.close()
    return 1


# ---------------------------------------------------------------------------
# Extraction page par page
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    # Paires de substitution (émojis mal décodés) → caractère réel ; restes isolés supprimés.
    text = text.encode("utf-16", "surrogatepass").decode("utf-16", "replace").replace("\ufffd", "")
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_ODD_CHARS = re.compile(r"[âêîôûÂÊÎÔÛ€$^{}\\|~ùÈ]")
GARBLED_RATIO = 0.02  # pages propres ≈ 0,2 % ; couche texte d'un mauvais OCR ≈ 6 %


def garbled(text: str) -> bool:
    """Couche texte illisible (ancien OCR de mauvaise qualité) : la page sera relue par OCR."""
    letters = sum(char.isalpha() for char in text)
    return letters >= 80 and len(_ODD_CHARS.findall(text)) / letters > GARBLED_RATIO


def _pdf_texts(path: Path) -> Iterator[str]:
    """Texte natif page par page : pypdf, ou pdfium si pypdf échoue (PDF chiffré, abîmé)."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = list(reader.pages)
    except Exception:
        pages = None
    if pages is not None:
        for page in pages:
            try:
                yield page.extract_text() or ""
            except Exception:
                yield ""
        return
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        for index in range(len(pdf)):
            textpage = pdf[index].get_textpage()
            yield textpage.get_text_bounded()
    finally:
        pdf.close()


MHTML = "multipart/related"


class _HtmlText(HTMLParser):
    """Texte lisible d'une page HTML (sans scripts, styles ni menus)."""

    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "svg", "form", "button"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def mhtml_text(path: Path) -> str:
    """Page web enregistrée (MHTML, souvent sans extension parlante) : texte de la partie HTML principale."""
    from email import policy
    from email.parser import BytesParser

    message = BytesParser(policy=policy.default).parse(path.open("rb"))
    for part in message.walk():
        if part.get_content_type() == "text/html":
            parser = _HtmlText()
            raw = part.get_payload(decode=True) or b""
            parser.feed(raw.decode(part.get_content_charset() or "utf-8", errors="replace"))
            text = "".join(parser.parts)
            return "\n".join(line.strip() for line in text.split("\n"))
    raise ExtractionError("Aucune page HTML dans ce fichier MHTML")


def sniff_mime(path: Path) -> str | None:
    """Type réel d'un fichier à l'extension inconnue, d'après ses premiers octets."""
    head = path.open("rb").read(2048)
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"PK") and b"word/" in path.open("rb").read(65536):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if b"MIME-Version:" in head and b"multipart/related" in head:
        return MHTML
    return None


def extract_pages(path: Path, mime_type: str, use_ocr: bool = True) -> Iterator[tuple[int, str, str]]:
    """Produit (numéro de page, texte, méthode) ; méthode ∈ text, ocr, empty."""
    if mime_type == "application/pdf":
        for index, raw in enumerate(_pdf_texts(path), start=1):
            text = _clean(raw)
            if (len(text) >= MIN_TEXT_CHARS and not garbled(text)) or not use_ocr:
                yield index, text, "text" if text else "empty"
                continue
            ocr = _clean(ocr_png(render_pdf_page(path, index)))
            if not ocr and text:  # l'OCR n'a rien lu : on garde le peu de texte natif
                yield index, text, "text"
                continue
            yield index, ocr, "ocr" if ocr else "empty"
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document as DocxDocument

        doc = DocxDocument(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        yield 1, _clean("\n".join(parts)), "text"
    elif mime_type == "application/msword":
        result = subprocess.run(
            ["/usr/bin/textutil", "-convert", "txt", "-stdout", str(path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise ExtractionError("Lecture du fichier .doc impossible (textutil)")
        yield 1, _clean(result.stdout), "text"
    elif mime_type == MHTML:
        yield 1, _clean(mhtml_text(path)), "text"
    elif mime_type == "text/plain":
        yield 1, _clean(path.read_text(encoding="utf-8", errors="replace")), "text"
    elif mime_type in IMAGE_TYPES:
        if not use_ocr:
            yield 1, "", "empty"
            return
        text = _clean(ocr_png(image_to_png(path)))
        yield 1, text, "ocr" if text else "empty"
    else:
        raise ExtractionError(f"Format non pris en charge : {mime_type}")


# ---------------------------------------------------------------------------
# Découpage en exercices et corrections
# ---------------------------------------------------------------------------

_NUMBER = r"(?:n[°o]\s*)?(?P<num>\d{1,3}|[IVX]{1,5})\b"
# Titres numérotés : « Exercice 3 », « EXERCICE 1 (5 points) », « Application 2 », « Situation 1 », « Problème II »…
EXERCISE_HEADING = re.compile(
    r"^\s*(?P<word>exercices?|exercises?|exo|ex\.|probl[eè]mes?|problems?|situations?(?:\s+d['’]\s*[ée]valuation)?"
    r"|activit[ée]s?|activity|applications?|questions?\s+de\s+cours|test)\s*" + _NUMBER + r"\s*(?:[:.\-–—·)(/]|$|\s)",
    re.IGNORECASE,
)
# Rubriques d'exercices sans numéro (cahiers d'habileté, fiches ivoiriennes).
EXERCISE_SECTION = re.compile(
    r"^\s*(?P<word>situation\s+d['’]\s*[ée]valuation|je\s+m['’]\s*exerce|je\s+m['’]\s*entra[iî]ne|je\s+m['’]\s*[ée]value"
    r"|j['’]\s*approfondi[st]?|tests?\s+objectifs?|exercices?\s+d['’]\s*(?:application|entra[iî]nement|renforcement|approfondissement)"
    r"|activit[ée]s?\s+d['’]\s*(?:application|[ée]valuation|int[ée]gration)|[ée]valuation)\s*[:.!]?\s*$",
    re.IGNORECASE,
)
CORRECTION_SECTION = re.compile(
    r"^\s*(corrig[ée]s?|corrections?|solutions?|[ée]l[ée]ments\s+de\s+(?:correction|r[ée]ponse)|proposition\s+de\s+corrig[ée])\b",
    re.IGNORECASE,
)
# Leçon / chapitre : la numérotation des exercices repart souvent à 1 dans chaque leçon.
LESSON_HEADING = re.compile(
    r"^\s*(?P<word>le[cç]ons?|chapitres?|th[eè]mes?|s[ée]quences?|unit[ée]?|unit|module)\s*" + _NUMBER,
    re.IGNORECASE,
)
# « Solution » / « Correction » / « Corrigé » seul, juste après un exercice : corrigé de CET exercice.
LOCAL_CORRECTION = re.compile(
    r"^\s*(solution|correction|corrig[ée]|r[ée]ponse|r[ée]solution)\s*(?:(?:de\s+l['’]\s*|du\s+|des\s+)?(?:exercices?|applications?|activit[ée]s?|probl[eè]mes?)"
    r"(?:\s*(?:n[°o]\s*)?(?:\d{1,3}|[IVX]{1,5}))?)?\s*[:.\-–—]?\s*$",
    re.IGNORECASE,
)
MIN_BODY_CHARS = 15  # en dessous (sommaire, renvoi), le bloc est ignoré


@dataclass
class Segment:
    kind: str  # "exercise" ou "correction"
    number: str | None
    heading: str
    page_start: int
    page_end: int
    lines: list[str] = field(default_factory=list)
    section: str | None = None  # « Leçon 2 », « Chapitre III »…

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def body_chars(self) -> int:
        return len("\n".join(self.lines[1:]).strip())

    @property
    def label(self) -> str:
        word = self.heading.strip()
        word = word[:1].upper() + word[1:].lower() if word else "Exercice"
        base = f"{word} {self.number}" if self.number else word
        return f"{self.section} — {base}" if self.section else base

    @property
    def key(self) -> tuple[str | None, str]:
        """Clé d'association exercice ↔ corrigé."""
        return (self.section, self.number or self.heading.lower())


def normalize_number(raw: str) -> str:
    roman = {"I": 1, "V": 5, "X": 10}
    if raw.isdigit():
        return str(int(raw))
    total, previous = 0, 0
    for char in reversed(raw.upper()):
        value = roman.get(char, 0)
        total = total - value if value < previous else total + value
        previous = max(previous, value)
    return str(total)


def segment(pages: list[tuple[int, str]], all_corrections: bool = False) -> list[Segment]:
    """Découpe tout le document (jusqu'à la dernière page) en exercices et corrigés.

    - « Exercice N », « Application N », « Situation d'évaluation », « Je m'exerce »… ouvrent un exercice ;
    - « Leçon N » / « Chapitre N » fixe la section courante (numérotation propre à chaque leçon) ;
    - après « Corrigé »/« Correction », les blocs sont des corrigés jusqu'à la leçon suivante ;
    - `all_corrections` : document entièrement corrigé (livre du professeur, corrigé d'un cahier)."""
    segments: list[Segment] = []
    current: Segment | None = None
    in_corrections = all_corrections
    section: str | None = None
    local_pending = False
    part = 1
    last_number: dict[str, int] = {}

    def section_label() -> str | None:
        if part == 1:
            return section
        return f"{section} · partie {part}" if section else f"Partie {part}"

    def close() -> None:
        nonlocal current
        if current is not None:
            segments.append(current)
            current = None

    for page_number, text in pages:
        for line in text.split("\n"):
            stripped = line.strip()
            lesson = LESSON_HEADING.match(stripped) if len(stripped) <= 160 else None
            if lesson:
                local_pending = False
                close()
                word = lesson.group("word")
                section = f"{word[:1].upper()}{word[1:].lower().rstrip('s')} {normalize_number(lesson.group('num'))}"
                in_corrections = all_corrections
                part, last_number = 1, {}
                continue
            numbered = EXERCISE_HEADING.match(stripped)
            if (LOCAL_CORRECTION.match(stripped) and current is not None and current.kind == "exercise"
                    and not in_corrections):
                owner = current
                close()
                local_pending = True
                current = Segment(
                    kind="correction", number=owner.number, heading=owner.heading, page_start=page_number,
                    page_end=page_number, lines=[stripped], section=owner.section,
                )
                continue
            if CORRECTION_SECTION.match(stripped) and not numbered and len(stripped) <= 80:
                close()
                in_corrections = True
                continue
            unnumbered = None if numbered or len(stripped) > 80 else EXERCISE_SECTION.match(stripped)
            if numbered or unnumbered:
                if local_pending and current is not None and current.body_chars == 0:
                    current = None  # « Corrigé » suivi directement d'un titre : c'est une section de corrigés
                    in_corrections = True
                local_pending = False
                close()
                match = numbered or unnumbered
                if numbered:
                    family = (match.group("word").lower()[:5], "corr" if in_corrections else "ex")
                    value = int(normalize_number(numbered.group("num")))
                    if family in last_number and value <= last_number[family] and value == 1:
                        part += 1  # la numérotation repart à 1 : nouvelle série d'exercices
                        last_number = {}
                    last_number[family] = value
                current = Segment(
                    kind="correction" if in_corrections else "exercise",
                    number=normalize_number(numbered.group("num")) if numbered else None,
                    heading=re.sub(r"\s+", " ", match.group("word")),
                    page_start=page_number,
                    page_end=page_number,
                    lines=[stripped],
                    section=section_label(),
                )
                continue
            if current is not None:
                current.lines.append(line)
                if stripped:
                    current.page_end = page_number
    close()
    return [s for s in segments if s.body_chars >= MIN_BODY_CHARS or (s.kind == "correction" and s.body_chars > 0)]


# ---------------------------------------------------------------------------
# Figures : captures des images d'une page PDF
# ---------------------------------------------------------------------------

@dataclass
class PageVisuals:
    figures: list[tuple[float, float, float, float]]  # boîtes en fractions de page (gauche, haut, droite, bas)
    scanned: bool  # page entièrement scannée (une image couvre presque toute la page)
    drawings: int  # nombre de tracés vectoriels (schémas, figures géométriques)

    @property
    def has_visuals(self) -> bool:
        return bool(self.figures) or self.scanned or self.drawings >= 25


def page_visuals(path: Path, page_number: int) -> PageVisuals:
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    pdf = pdfium.PdfDocument(str(path))
    try:
        page = pdf[page_number - 1]
        width, height = page.get_size()
        figures, scanned, drawings = [], False, 0
        for obj in page.get_objects(max_depth=2):
            if obj.type == pdfium_c.FPDF_PAGEOBJ_PATH:
                drawings += 1
                continue
            if obj.type != pdfium_c.FPDF_PAGEOBJ_IMAGE:
                continue
            left, bottom, right, top = obj.get_pos()
            w, h = right - left, top - bottom
            if w < 40 or h < 40:  # logos, puces
                continue
            if w * h > 0.75 * width * height:
                scanned = True
                continue
            figures.append((
                max(0.0, left / width), max(0.0, 1 - top / height),
                min(1.0, right / width), min(1.0, 1 - bottom / height),
            ))
        return PageVisuals(figures=figures, scanned=scanned, drawings=drawings)
    finally:
        pdf.close()


def crop_png(png: bytes, box: tuple[float, float, float, float], margin: float = 0.01) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(png)) as image:
        w, h = image.size
        left, right = sorted((box[0], box[2]))  # boîte parfois inversée par l'OCR
        top, bottom = sorted((box[1], box[3]))
        area = (
            int(max(0, left - margin) * w), int(max(0, top - margin) * h),
            int(min(1, right + margin) * w), int(min(1, bottom + margin) * h),
        )
        area = (area[0], area[1], max(area[2], area[0] + 1), max(area[3], area[1] + 1))
        buffer = io.BytesIO()
        image.crop(area).save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()


# ---------------------------------------------------------------------------
# Identification : propositions de titre, niveau, matière et type à partir du contenu
# ---------------------------------------------------------------------------

GRADE_PATTERNS = [
    ("CE1", r"\bce\s?1\b"), ("CE2", r"\bce\s?2\b"), ("CM1", r"\bcm\s?1\b"), ("CM2", r"\bcm\s?2\b"),
    ("6ème", r"\b(6\s?(?:e|è|ème|eme)|sixi[eè]me)\b"), ("5ème", r"\b(5\s?(?:e|è|ème|eme)|cinqui[eè]me)\b"),
    ("4ème", r"\b(4\s?(?:e|è|ème|eme)|quatri[eè]me)\b"), ("3ème", r"\b(3\s?(?:e|è|ème|eme)|troisi[eè]me|bepc)\b"),
    ("2nde", r"\b(2\s?(?:nde|nd)|seconde)\b"), ("1ère", r"\b(1\s?(?:ère|ere|re)|premi[eè]re)\b"),
    ("Terminale", r"\b(t\s?les?|terminales?|bac(?:calaur[ée]at)?)\b"), ("BTS", r"\bbts\b"),
]
SUBJECT_PATTERNS = [
    ("Mathématiques", r"\b(math[ée]matiques?|maths?|g[ée]om[ée]trie|alg[eè]bre|[ée]quations?|fonctions?)\b"),
    ("Physique-Chimie", r"\b(physique|chimie|[ée]lectricit[ée]|m[ée]canique|optique)\b"),
    ("SVT", r"\b(svt|sciences?\s+de\s+la\s+vie|biologie|g[ée]ologie)\b"),
    ("Histoire-Géographie", r"\b(histoire|g[ée]ographie)\b"),
    ("Français", r"\b(fran[cç]ais|grammaire|conjugaison|orthographe|dict[ée]e|r[ée]daction)\b"),
    ("Anglais", r"\b(anglais|english)\b"),
    ("Philosophie", r"\b(philosophie|philo)\b"),
]
KIND_PATTERNS = [
    ("corrige", r"\b(corrig[ée]s?|correction|solutions?)\b"),
    ("examen", r"\b(examen|bepc|cepe|baccalaur[ée]at|bac\s|concours|annales?)\b"),
    ("devoir", r"\b(devoir|[ée]valuation|composition|interrogation)\b"),
    ("fiche", r"\b(fiche|travaux\s+dirig[ée]s|td)\b"),
    ("exercices", r"\b(exercices?|habilet[ée]s?)\b"),
    ("manuel", r"\b(cours|manuel|le[cç]ons?)\b"),
]


def _first_match(patterns: list[tuple[str, str]], text: str) -> str | None:
    lowered = text.lower()
    best: tuple[int, str] | None = None
    for label, pattern in patterns:
        found = re.search(pattern, lowered)
        if found and (best is None or found.start() < best[0]):
            best = (found.start(), label)
    return best[1] if best else None


def guess_title(text: str) -> str | None:
    for line in text.split("\n"):
        candidate = line.strip(" .:-–—·\t")
        letters = sum(char.isalpha() for char in candidate)
        if 8 <= len(candidate) <= 120 and letters >= 0.6 * len(candidate):
            return candidate[:120]
    return None


# Séries du second cycle : « TleC », « Terminales C, E », « 1ère C&D », « TLES A-B-C-D », « 2NDC », « BAC D », « série A2 ».
_SERIE = r"(?:A[12]?|B|C|D|E|F\d?|G\d?)"
_SERIES_LIST = rf"({_SERIE}(?:\s*(?:[,&/\-]|et)?\s*{_SERIE})*)(?![A-Za-z0-9])"  # « AB » = A et B
SERIES_PATTERN = re.compile(
    rf"(?:(?i:terminales?|tles?|1(?:ere|ère|re|ère)s?|premi[eè]res?|2(?:nde|nd(?!e))s?|secondes?|bac|s[ée]ries?))\s*{_SERIES_LIST}"
)
SERIES_GRADE = re.compile(
    r"(?i:(terminales?|tles?)|(1(?:ere|ère|re)s?|premi[eè]res?)|(2(?:nde|nd(?!e))s?|secondes?))\s*" + _SERIES_LIST.replace("(", "(?:", 1)
)


def identify_series(text: str, filename: str = "") -> list[str]:
    """Lettres de série citées (A, A1, C, D, E…), dans l'ordre d'apparition, sans doublon."""
    found: list[str] = []
    filename = unicodedata.normalize("NFC", filename)  # macOS écrit « è » en deux caractères
    for sample in (filename.replace("_", " "), text[:6000]):
        for match in SERIES_PATTERN.finditer(sample):
            group = match.group(1)
            if group == "DE":  # « TERMINALE DE … » : article, pas une série
                continue
            for letter in re.findall(_SERIE, group):
                if letter not in found:
                    found.append(letter)
        if found:  # le nom de fichier prime ; sinon, l'en-tête du document
            break
    if not found:  # usages ivoiriens dans les noms de fichiers : « 2nde S » = 2nde C, « SM » = C et E, « SE » = D
        name = filename.replace("_", " ")
        for pattern, letters in FILENAME_SERIES_CODES:
            if pattern.search(name):
                return list(letters)
    return found


FILENAME_SERIES_CODES = [
    (re.compile(r"(?i)\b(?:2nde?|seconde)\s*S\b"), ("C",)),
    (re.compile(r"(?i)\b(?:t|tle|terminale|1(?:ere|ère|re))\s*SM\b"), ("C", "E")),
    (re.compile(r"(?i)\b(?:t|tle|terminale|1(?:ere|ère|re))\s*SE\b"), ("D",)),
]


def identify(text: str, filename: str = "") -> dict:
    """Propositions (jamais imposées) tirées du nom de fichier et des premières pages."""
    sample = f"{filename}\n{text[:6000]}"
    return {
        "title": guess_title(text),
        "grade": _first_match(GRADE_PATTERNS, sample),
        "subject": _first_match(SUBJECT_PATTERNS, sample),
        "kind": _first_match(KIND_PATTERNS, sample),
        "series": identify_series(text, filename),
    }
