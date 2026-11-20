"""Propositions de cartes mémoire à partir des documents (cahier §5 et §7).

Repère dans le texte extrait les définitions, théorèmes, propriétés, règles, formules et les phrases
« On appelle … ». Chaque proposition garde le passage source exact (`original_text`), la page et le document ;
elle a le statut « extrait » et n'est jamais montrée aux élèves avant relecture et validation par
l'administrateur. Rien n'est inventé : la réponse attendue est le passage du document.
"""

import re
from dataclasses import dataclass

KEYWORDS = {
    "definition": ("definition", "la définition"),
    "theoreme": ("question", "le théorème"),
    "propriete": ("question", "la propriété"),
    "regle": ("question", "la règle"),
    "formule": ("formule", "la formule"),
    "loi": ("question", "la loi"),
    "principe": ("question", "le principe"),
}
HEADING = re.compile(
    r"^\s*(D[ée]finition|DÉFINITION|DEFINITION|Th[ée]or[èe]me|THÉORÈME|THEOREME|Propri[ée]t[ée]|PROPRIÉTÉ|PROPRIETE|"
    r"R[èe]gle|RÈGLE|REGLE|Formule|FORMULE|Loi|LOI|Principe|PRINCIPE)s?\b(?:\s*(\d+))?\s*(?:([:.\-–—])\s*)?(.*)$"
)
STOP = re.compile(
    r"^\s*(?:Exemples?|Remarques?|Exercices?|M[ée]thode|Le[çc]on|Activit[ée]|Application|Preuve|D[ée]monstration|"
    r"Cons[ée]quence|Corollaire|NB|N\.B|Dessin|[IVX]+\s*[.\-)]|\d+\s*[.)]\s+[A-Z])\b|XERCICE",
)
NOISE = re.compile(r"(?i)scanned by camscanner|www\.|https?://")
ON_APPELLE = re.compile(
    r"\b[Oo]n (?:appelle|nomme)\s+(.{3,70}?)(?<!\bà)(?<!\bde)(?<!\bdu)(?<!\ben)(?<!\bsur)(?<!\bpar)(?<!\bpour)"
    r"\s+(?=(?:le|la|les|l['’]|un|une|tout|toute|tous|toutes|des|ce|cette)\b)"
    r"[^.]{5,400}\.",
)
MAX_ANSWER = 700


@dataclass
class Proposal:
    page_number: int
    card_type: str
    question: str
    answer: str
    original_text: str


def _plain(word: str) -> str:
    return (word.lower().replace("é", "e").replace("è", "e").replace("É", "e").replace("È", "e"))


def _trim(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= MAX_ANSWER:
        return text
    cut = text[:MAX_ANSWER]
    end = max(cut.rfind(". "), cut.rfind(". "))
    return cut[: end + 1] if end > 200 else cut.rstrip() + " …"


def _is_title(line: str) -> bool:
    words = line.split()
    if NOISE.search(line) or not re.search(r"[A-Za-zÀ-ÿ]{3,}", line):
        return False
    return 0 < len(words) <= 8 and not line.rstrip().endswith((".", ",", ";")) and not re.search(r"\d{2,}", line)


# Une question doit nommer la notion (« Énoncer la propriété de Thalès ») : l'élève ne connaît pas le document
# par cœur, un renvoi à une page ou aux premiers mots du passage ne lui dit rien (retour utilisateur 2026-11-20).
TO_SPECIFY = "À préciser"
VAGUE = re.compile(r"\(p\.\s*\d+\)|qui commence par|^\s*" + TO_SPECIFY)


def card_problem(question: str | None, answer: str | None) -> str | None:
    """Raison de ne pas montrer une carte aux élèves (None : la carte peut être publiée)."""
    from app.extraction import garbled

    if VAGUE.search(question or ""):
        return "question imprécise : la notion n'est pas nommée"
    if garbled(answer or ""):
        return "réponse illisible (texte du document mal lu)"
    return None


def _question(kind: str, title: str | None, body: str, page: int) -> str:
    article = KEYWORDS[kind][1]
    if title:
        if kind == "definition":
            return f"Définir : {title}"
        joiner = " " if re.match(r"(?i)(de|du|des|d['’])\b", title) else " : "
        return f"Énoncer {article}{joiner}{title}"
    # Pas d'intitulé dans le document : la notion sera nommée par `preciser` (jamais publiée avant).
    return f"{TO_SPECIFY} : {article}"


def propose(pages: list[tuple[int, str]]) -> list[Proposal]:
    proposals: list[Proposal] = []
    for page_number, text in pages:
        lines = [line for line in text.splitlines() if not NOISE.search(line)]
        for index, line in enumerate(lines):
            match = HEADING.match(line)
            if not match:
                continue
            keyword, _number, separator, rest = match.groups()
            # « propriété de Pythagore » au fil d'une solution n'est pas un titre : majuscule exigée,
            # et sans « : » la suite doit être un intitulé court.
            if not keyword[0].isupper() or (not separator and rest and not _is_title(rest)):
                continue
            kind = _plain(keyword).rstrip("s")
            kind = {"theoreme": "theoreme", "propriete": "propriete", "regle": "regle"}.get(kind, kind)
            if kind not in KEYWORDS:
                continue
            title, body_lines = None, []
            rest = rest.strip()
            if rest and _is_title(rest):
                title = rest
            elif rest:
                body_lines.append(rest)
            if title is None and index > 0 and lines[index - 1].strip() and _is_title(lines[index - 1].strip()) \
                    and not HEADING.match(lines[index - 1]):
                title = lines[index - 1].strip()
            for following in lines[index + 1:]:
                if HEADING.match(following) or STOP.match(following) or sum(map(len, body_lines)) > MAX_ANSWER:
                    break
                if following.strip():
                    body_lines.append(following.strip())
                if len(body_lines) >= 14:
                    break
            body = _trim(" ".join(body_lines))
            if len(body) < 20:
                continue
            original = "\n".join([line.strip(), *body_lines])
            proposals.append(Proposal(page_number, KEYWORDS[kind][0], _question(kind, title, body, page_number),
                                      body, original))
        flat = re.sub(r"\s+", " ", text)
        for match in ON_APPELLE.finditer(flat):
            term = match.group(1).strip(" ,:")
            sentence = match.group(0).strip()
            proposals.append(Proposal(page_number, "definition", f"Qu'appelle-t-on {term} ?", _trim(sentence), sentence))
    return proposals


def create_proposals(db, document) -> tuple[int, int]:
    """Crée les cartes proposées pour un document (sans doublon). Renvoie (trouvées, créées)."""
    from sqlalchemy import select

    from app.models import Flashcard

    found = propose([(p.page_number, p.text) for p in document.pages])
    existing = {(c.page_number, c.original_text) for c in db.scalars(
        select(Flashcard).where(Flashcard.document_id == document.id))}
    created = 0
    for item in found:
        if (item.page_number, item.original_text) in existing:
            continue
        card = Flashcard(
            document_id=document.id, page_number=item.page_number, card_type=item.card_type, question=item.question,
            answer=item.answer, original_text=item.original_text, status="extracted",
            grade_id=document.grade_id, subject_id=document.subject_id, chapter_id=document.chapter_id,
        )
        card.tracks = list(document.tracks)
        db.add(card)
        existing.add((item.page_number, item.original_text))
        created += 1
    return len(found), created
