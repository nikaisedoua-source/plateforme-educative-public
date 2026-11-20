"""Réécriture des énoncés et des corrigés en LaTeX, d'après l'image du document, par un modèle de vision
local (Ollama). Rien ne sort de l'ordinateur.

Le texte extrait des PDF casse souvent les formules (« 𝐾𝐾𝐾𝐾 » au lieu de [KL), fractions sur trois lignes).
Le modèle relit donc la zone de la page où se trouve l'exercice et le recopie avec les formules en LaTeX,
découpé en questions.

Garde-fous contre l'invention :
- consigne de recopie stricte (ne rien ajouter, ne rien résoudre) et température 0 ;
- chaque formule doit être un LaTeX valide ;
- les mots et les nombres de la réécriture doivent se retrouver dans le texte extrait du document ;
- la réécriture ne peut pas être beaucoup plus longue que l'original ;
- le résultat attendu d'une question n'est retenu que s'il figure dans le corrigé fourni.
Si un contrôle échoue, la réécriture est marquée « douteuse » : l'élève voit d'abord l'image originale.
L'extraction brute (`original_text`, `statement`) n'est jamais modifiée.
"""

import base64
import io
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import extraction, storage
from app.answers import to_sympy
from app.audit import record
from app.config import get_settings
from app.mathtext import render as render_math
from app.models import Correction, Document, Exercise, ExerciseQuestion

MAX_QUESTIONS = 30
MAX_IMAGE_WIDTH = 1100
MAX_IMAGE_HEIGHT = 3200
# À augmenter dès que le recadrage change : les images déjà servies aux élèves sont alors recalculées.
CROP_VERSION = 3

STATEMENT_PROMPT = """Tu recopies fidèlement un exercice scolaire à partir de l'image (programme ivoirien).
Règles absolues :
- Recopie exactement le texte de l'image : n'ajoute rien, ne résous rien, ne corrige pas le fond, ne traduis pas.
- Écris toutes les expressions mathématiques, chimiques et physiques en LaTeX, entre $...$
  (ou $$...$$ pour une formule seule sur sa ligne). Exemples : $\\frac{3}{4}$, $x^{2}$, $\\sqrt{5}$, $[KL)$,
  $\\overline{AB}$, $\\vec{u}$, $\\mathbb{R}$, $H_{2}O$.
- Garde la numérotation d'origine (1., 2., a), b)...) et les retours à la ligne utiles.
- Si une figure ou un tableau est dessiné, écris [figure] à sa place, sans le décrire.
- Ignore les en-têtes, pieds de page, numéros de page, versets ou devises, et tout ce qui appartient
  à un autre exercice.
- Une opération posée en colonnes (addition, soustraction, multiplication, division) s'écrit sur une ligne
  en LaTeX, sans la calculer : par exemple « $2{,}98 + 48{,}571 + 495$ » ou « $17{,}56 \\div 0{,}8$ ».
  Les nombres décimaux s'écrivent avec une virgule : $48{,}571$. Pas de chiffres séparés par des espaces.
- Les pointillés à compléter s'écrivent « ... ».
- L'image fait foi ; le texte extrait plus bas sert seulement à vérifier l'orthographe des mots.
Ensuite, liste les questions auxquelles l'élève doit répondre, dans l'ordre :
- "numero" : la numérotation telle qu'elle est écrite ("1", "2.a", "b"...) ;
- "texte" : le texte de la question recopié (LaTeX) ;
- "nature" : "resultat" si la réponse attendue est courte (un nombre, une expression, un ensemble de
  solutions, un intervalle, vrai/faux, un mot) ; "demonstration" si on demande de démontrer, justifier,
  expliquer, construire, tracer, représenter ou rédiger.
S'il n'y a pas de question numérotée, mets une seule question avec tout l'énoncé.

Texte extrait automatiquement du même passage (il peut être déformé, sers-t'en seulement pour lire les mots) :
<<<
{raw}
>>>"""

CORRECTION_PROMPT = """Tu recopies fidèlement le corrigé d'un exercice scolaire à partir de l'image.
Règles absolues :
- Recopie exactement le texte de l'image : n'ajoute rien, ne corrige rien, ne complète pas.
- Écris toutes les expressions mathématiques en LaTeX entre $...$ (ou $$...$$).
- Si une figure est dessinée, écris [figure].
Ensuite, pour chacune de ces questions, donne le résultat final court s'il est écrit explicitement dans ce
corrigé (par exemple "x = 4", "\\frac{20}{7}", "S = \\{2 ; 3\\}", "vrai"), en LaTeX sans $ ; sinon "".
Questions : {questions}

Texte extrait automatiquement (il peut être déformé, sers-t'en seulement pour lire les mots) :
<<<
{raw}
>>>"""

STATEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "enonce": {"type": "string"},
        "questions": {"type": "array", "items": {
            "type": "object",
            "properties": {"numero": {"type": "string"}, "texte": {"type": "string"},
                           "nature": {"type": "string", "enum": ["resultat", "demonstration"]}},
            "required": ["numero", "texte", "nature"]}},
    },
    "required": ["enonce", "questions"],
}
CORRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "corrige": {"type": "string"},
        "resultats": {"type": "array", "items": {
            "type": "object", "properties": {"numero": {"type": "string"}, "resultat": {"type": "string"}},
            "required": ["numero", "resultat"]}},
    },
    "required": ["corrige", "resultats"],
}


class RewriteUnavailable(RuntimeError):
    """Le modèle local ne répond pas (Ollama arrêté ou modèle absent)."""


# ---------------------------------------------------------------------------
# Zone de la page
# ---------------------------------------------------------------------------

@dataclass
class _PageCache:
    path: Path
    positions: dict[tuple[int, str], float | None] = field(default_factory=dict)
    marks: dict[int, list[float]] = field(default_factory=dict)
    margins: dict[int, tuple[float, float]] = field(default_factory=dict)

    def page_margins(self, page: int) -> tuple[float, float]:
        if page not in self.margins:
            from app.processing import page_margins

            try:
                self.margins[page] = page_margins(self.path, page)
            except Exception:
                self.margins[page] = (0.0, 1.0)
        return self.margins[page]

    def position(self, page: int, heading: str) -> float | None:
        key = (page, heading)
        if key not in self.positions:
            from app.processing import _heading_positions

            try:
                self.positions[key] = _heading_positions(self.path, page, [heading])[0]
            except Exception:
                self.positions[key] = None
        return self.positions[key]

    def heading_marks(self, page: int) -> list[float]:
        if page not in self.marks:
            from app.processing import heading_marks

            try:
                self.marks[page] = heading_marks(self.path, page)
            except Exception:
                self.marks[page] = []
        return self.marks[page]


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def _stack(parts: list[bytes]) -> bytes:
    from PIL import Image

    images = [Image.open(io.BytesIO(part)).convert("RGB") for part in parts]
    width = max(image.width for image in images)
    height = sum(image.height for image in images)
    canvas = Image.new("RGB", (width, height), "white")
    y = 0
    for image in images:
        canvas.paste(image, (0, y))
        y += image.height
    scale = min(1.0, MAX_IMAGE_WIDTH / canvas.width, MAX_IMAGE_HEIGHT / canvas.height)
    if scale < 1:
        canvas = canvas.resize((max(1, int(canvas.width * scale)), max(1, int(canvas.height * scale))))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def region_image(document: Document, page_start: int, page_end: int, heading: str,
                 siblings: list[tuple[int, str]], cache: _PageCache | None = None) -> bytes | None:
    """Image de la zone d'un exercice : du titre de l'exercice jusqu'au titre suivant (`siblings` : autres
    blocs du même document, (page de début, titre)). Page entière quand la position est introuvable."""
    path = storage.resolve(document.storage_key)
    if document.mime_type in extraction.IMAGE_TYPES:
        return _stack([extraction.image_to_png(path)])
    if document.mime_type != "application/pdf" or not path.exists():
        return None
    cache = cache or _PageCache(path)
    page_end = min(max(page_end, page_start), page_start + 2)  # au plus trois pages
    parts: list[bytes] = []
    for page in range(page_start, page_end + 1):
        png = extraction.render_pdf_page(path, page, dpi=150)
        header, footer = cache.page_margins(page)
        top = cache.position(page, heading) if page == page_start else None
        top = header if top is None else top
        # Fin de zone : titre d'un autre bloc du document, ou tout début de bloc (« EXERCICE 3 », « PARTIE B »)
        # repéré sur la page, sous le titre de l'exercice.
        following = [cache.position(page, title) for start, title in siblings if start == page and title != heading]
        following += cache.heading_marks(page)
        following = [pos for pos in following if pos is not None and pos > top + 0.02]
        bottom = min(following) - 0.006 if following and page == page_end else 1.0
        bottom = min(bottom, footer)
        if page < page_end and following:  # l'exercice continue page suivante : rien après un autre titre
            bottom = min(min(following) - 0.006, footer)
            parts.append(extraction.crop_png(png, (0.0, max(0.0, top - 0.01), 1.0, bottom), margin=0.0))
            break
        parts.append(extraction.crop_png(png, (0.0, max(0.0, top - 0.01), 1.0, bottom), margin=0.0))
    return _stack(parts)


# ---------------------------------------------------------------------------
# Modèle local
# ---------------------------------------------------------------------------

def ask_model(prompt: str, image: bytes | None, schema: dict, retry: bool = True) -> dict:
    settings = get_settings()
    message = {"role": "user", "content": prompt}
    if image:
        message["images"] = [base64.b64encode(image).decode()]
    body = {"model": settings.ollama_vision_model, "messages": [message], "stream": False, "format": schema,
            "options": {"temperature": 0 if retry else 0.3, "num_ctx": 8192, "num_predict": 3000,
                        "repeat_penalty": 1.0 if retry else 1.15}, "keep_alive": "30m"}
    try:
        response = httpx.post(f"{settings.ollama_url.rstrip('/')}/api/chat", json=body, timeout=600)
    except httpx.HTTPError as error:
        raise RewriteUnavailable("Ollama est injoignable : lancez « ollama serve ».") from error
    if response.status_code == 404:
        raise RewriteUnavailable(f"Modèle absent : lancez « ollama pull {settings.ollama_vision_model} ».")
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        if not retry:
            raise ValueError("réponse du modèle illisible") from error
        return ask_model(prompt, image, schema, retry=False)  # seconde tentative, moins de répétitions


# ---------------------------------------------------------------------------
# Contrôles de fidélité
# ---------------------------------------------------------------------------

MATH = re.compile(r"\$\$.+?\$\$|\$[^$]+\$", re.DOTALL)


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]{4,}", _fold(MATH.sub(" ", text)))


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+", unicodedata.normalize("NFKC", text))


def _joined_numbers(text: str) -> list[str]:
    """Nombres écrits avec des espaces ou une virgule (« 2 , 9 8 », « 48,571 ») réduits à leurs chiffres."""
    text = unicodedata.normalize("NFKC", text).replace("{,}", ",")
    return [re.sub(r"\D", "", n) for n in re.findall(r"\d+(?:[ \t]{0,3}[,.]?[ \t]{0,3}\d+)*", text)]


def fidelity_problems(raw: str, rewritten: str) -> list[str]:
    """Raisons de douter de la réécriture (liste vide : contrôles réussis)."""
    problems: list[str] = []
    rendered = render_math(rewritten)
    if rendered["errors"]:
        problems.append(f"{len(rendered['errors'])} formule(s) LaTeX invalide(s)")
    if rewritten.count("$") % 2:
        problems.append("délimiteur $ non fermé")
    checked = False  # au moins une preuve (mots ou nombres) doit relier la réécriture au document
    raw_words = set(_words(raw))
    words = _words(rewritten)
    if len(raw_words) >= 4 and words:
        checked = True
        share = sum(word in raw_words for word in words) / len(words)
        if share < 0.6:
            problems.append(f"seulement {share:.0%} des mots se retrouvent dans le document")
    raw_numbers = set(_numbers(raw)) | set(_joined_numbers(raw))
    numbers = _joined_numbers(MATH.sub(lambda m: m.group(0).replace("{,}", ","), rewritten))
    if len(numbers) >= 3 and raw_numbers:
        checked = True
        share = sum(number in raw_numbers or all(part in raw_numbers for part in _numbers(number))
                    for number in numbers) / len(numbers)
        if share < 0.6:
            problems.append(f"seulement {share:.0%} des nombres se retrouvent dans le document")
    if not checked:
        problems.append("texte du document trop court ou illisible pour vérifier")
    spaced_digits = re.findall(r"(?<!\d)\d {1,3}(?=\d(?!\d))", MATH.sub(" ", rewritten))
    if len(spaced_digits) >= 3 or re.search(r"\S {4,}\S", rewritten):
        problems.append("mise en page recopiée (chiffres espacés ou colonnes)")
    if re.search(r"(?i)\b(?:page \d+|DGEM|DREN|examen blanc)\b", _fold(rewritten)) and not re.search(
            r"(?i)\b(?:page \d+|DGEM|DREN|examen blanc)\b", _fold(_first_line(raw))):
        problems.append("en-tête ou pied de page recopié")
    plain = len(re.sub(r"\s+", "", MATH.sub("", rewritten)))
    if plain > 2 * len(re.sub(r"\s+", "", raw)) + 200:
        problems.append("réécriture beaucoup plus longue que l'original")
    return problems


def answer_supported(answer: str, correction_text: str, raw: str) -> bool:
    """Le résultat attendu doit être lisible et figurer dans le corrigé (nombres présents dans l'original)."""
    if not answer.strip() or len(answer) > 120:
        return False
    body = answer.split("=", 1)[-1] if answer.count("=") == 1 else answer
    folded = _fold(body).strip()
    if folded in {"vrai", "faux"}:
        return folded in _fold(correction_text) and folded in _fold(raw)
    numbers = _numbers(body)
    if numbers and not all(number in set(_numbers(raw)) for number in numbers):
        return False
    readable = to_sympy(body) is not None or bool(re.match(r"^\s*(?:S\s*=\s*)?\\?\{", answer)) \
        or bool(re.match(r"^\s*[\]\[]", body))
    return readable and bool(numbers or re.search(r"[a-z]", folded))


# ---------------------------------------------------------------------------
# Traitement d'un exercice
# ---------------------------------------------------------------------------

def _siblings(db: Session, document_id: int) -> list[tuple[int, str]]:
    rows = db.execute(select(Exercise.page_start, Exercise.original_text).where(Exercise.document_id == document_id))
    return [(page, _first_line(text)) for page, text in rows]


def rewrite_exercise(db: Session, exercise: Exercise, cache: _PageCache | None = None) -> str:
    """Réécrit l'énoncé et ses questions ; renvoie le statut obtenu."""
    settings = get_settings()
    document = db.get(Document, exercise.document_id)
    raw = exercise.original_text or exercise.statement
    image = region_image(document, exercise.page_start, exercise.page_end, _first_line(raw),
                         _siblings(db, document.id), cache)
    result = ask_model(STATEMENT_PROMPT.replace("{raw}", raw[:6000]), image, STATEMENT_SCHEMA)
    statement = str(result.get("enonce") or "").strip()
    questions = [q for q in result.get("questions") or [] if isinstance(q, dict) and str(q.get("texte", "")).strip()]
    if not statement:
        exercise.rewrite_status = "failed"
        return "failed"
    problems = fidelity_problems(raw, statement)
    if any(problem.startswith("mise en page") for problem in problems) and questions:
        # Opérations posées recopiées en colonnes : l'énoncé est reconstitué avec la consigne d'origine
        # et les questions déjà écrites en LaTeX par le modèle, puis revérifié.
        rebuilt = "\n".join([_first_line(statement)] + [
            f"{q.get('numero') or i + 1}. {str(q['texte']).strip()}" for i, q in enumerate(questions)])
        if not fidelity_problems(raw, rebuilt):
            statement, problems = rebuilt, []
    if image is None:
        problems.append("pas d'image du document : réécriture d'après le texte seul")
    exercise.statement_latex = statement
    exercise.rewrite_status = "doubtful" if problems else "ok"
    exercise.rewrite_model = settings.ollama_vision_model
    exercise.rewritten_at = datetime.now(UTC)
    exercise.questions.clear()
    db.flush()
    for order, question in enumerate(questions[:MAX_QUESTIONS]):
        exercise.questions.append(ExerciseQuestion(
            label=str(question.get("numero") or order + 1)[:20], text=str(question["texte"]).strip(),
            kind="proof" if question.get("nature") == "demonstration" else "result", sort_order=order,
        ))
    record(db, None, "rewrite", "exercise", exercise.id, status=exercise.rewrite_status, problems=problems,
           questions=len(exercise.questions), model=settings.ollama_vision_model)
    return exercise.rewrite_status


def rewrite_correction(db: Session, exercise: Exercise, cache: _PageCache | None = None) -> str:
    """Réécrit le corrigé et retient le résultat de chaque question quand il y figure."""
    correction = exercise.correction
    if correction is None or not exercise.questions:
        return "none"
    document = db.get(Document, correction.source_document_id)
    raw = correction.original_text or ""
    page = correction.source_page or exercise.page_start
    siblings = [(p or 0, _first_line(t)) for p, t in db.execute(
        select(Correction.source_page, Correction.original_text).where(
            Correction.source_document_id == document.id))]
    if document.id == exercise.document_id:
        siblings += _siblings(db, document.id)
    image = region_image(document, page, page, _first_line(raw), siblings, cache) if raw.strip() else None
    labels = ", ".join(f'"{q.label}"' for q in exercise.questions)
    result = ask_model(CORRECTION_PROMPT.replace("{questions}", labels).replace("{raw}", raw[:6000]),
                       image, CORRECTION_SCHEMA)
    text = str(result.get("corrige") or "").strip()
    if not text:
        correction.rewrite_status = "failed"
        return "failed"
    problems = fidelity_problems(raw, text)
    correction.text_latex = text
    correction.rewrite_status = "doubtful" if problems else "ok"
    by_label = {str(item.get("numero", "")).strip(): str(item.get("resultat", "")).strip()
                for item in result.get("resultats") or [] if isinstance(item, dict)}
    kept = 0
    for question in exercise.questions:
        answer = by_label.get(question.label, "")
        if question.kind == "result" and not problems and answer_supported(answer, text, raw):
            question.expected_answer = answer
            kept += 1
        else:
            question.expected_answer = None
    record(db, None, "rewrite", "correction", correction.id, status=correction.rewrite_status, problems=problems,
           expected_answers=kept)
    return correction.rewrite_status
