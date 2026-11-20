"""Questions précises pour les cartes mémoire : nommer la notion (« Énoncer la propriété de Thalès »).

Retour utilisateur (2026-11-20) : « Restituer la propriété (p. 73) qui commence par … » ne dit rien à l'élève,
qui ne connaît pas le document par cœur. Quand le document ne donne pas d'intitulé, le modèle local (Ollama)
lit le passage et le texte qui le précède sur la page (titres de section) et propose le nom de la notion.

Rien n'est inventé : chaque mot porteur de sens du nom proposé doit figurer dans le passage, dans le texte qui
le précède ou dans le titre du chapitre ; sinon la carte reste « à préciser » et n'est pas publiée. La réponse
attendue reste le passage exact du document. Un passage illisible ou incomplet n'est jamais publié.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record
from app.flashcards import TO_SPECIFY, VAGUE
from app.models import Chapter, DocumentPage, Flashcard
from app.rewrite import _fold, ask_model

KIND_LABEL = {"definition": "définition", "formule": "formule", "question": "propriété, théorème, règle ou loi"}
ARTICLES = {"théorème": "le théorème", "propriété": "la propriété", "règle": "la règle", "loi": "la loi",
            "principe": "le principe", "formule": "la formule", "définition": "la définition"}
GENERIC = {
    "enoncer", "donner", "definir", "definition", "propriete", "proprietes", "theoreme", "regle", "formule", "principe",
    "concernant", "relative", "relatif", "relatives", "sont", "dans", "pour", "avec", "entre", "cette", "leur",
    "leurs", "deux", "tout", "toute", "tous", "toutes", "dont", "elle", "elles", "quand", "plan", "espace",
}
SCHEMA = {
    "type": "object",
    "properties": {
        "lisible": {"type": "boolean"},
        "nature": {"type": "string", "enum": list(ARTICLES)},
        "notion": {"type": "string"},
    },
    "required": ["lisible", "nature", "notion"],
}
PROMPT = """Tu aides un professeur à rédiger des cartes de révision pour des élèves.
Voici un passage d'un cours ({kind}). L'élève devra le restituer de mémoire : la question doit nommer
précisément la notion, comme dans un cours, par exemple « la propriété de Thalès », « le théorème de
Pythagore », « la définition de la médiatrice d'un segment », « la formule de l'aire d'un disque ».

Règles :
- "nature" : définition, propriété, théorème, règle, loi, principe ou formule.
- "notion" : un groupe nominal court (moins de 10 mots, sans verbe conjugué, jamais le début de l'énoncé),
  le complément qui suit la nature, en commençant par « de », « du », « des » ou « d' »
  (exemples : « de Thalès », « de la médiatrice d'un segment », « des angles inscrits »,
  « de l'aire d'un disque »). Pour une définition : la chose définie, avec son article
  (exemples : « la médiatrice d'un segment », « une plante autotrophe »).
- Utilise uniquement des mots présents dans le passage, le texte qui le précède ou le chapitre. N'invente rien.
- "lisible" : false si le passage est illisible, coupé, sans énoncé complet, ou si c'est un exercice ou un
  exemple numérique au lieu d'une règle générale.

Chapitre : {chapter}
Texte qui précède le passage sur la page :
<<<
{before}
>>>
Passage :
<<<
{passage}
>>>"""


def _context(db: Session, card: Flashcard) -> tuple[str, str]:
    chapter = db.get(Chapter, card.chapter_id).title if card.chapter_id else ""
    page = db.scalar(select(DocumentPage).where(DocumentPage.document_id == card.document_id,
                                                DocumentPage.page_number == card.page_number))
    text = page.text if page else ""
    first = (card.original_text or "").strip().splitlines()[0] if (card.original_text or "").strip() else ""
    position = text.find(first) if first else -1
    before = text[max(0, position - 900):position] if position > 0 else ""
    return chapter or "", before.strip()


def _content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{4,}", _fold(text)) if w not in GENERIC]


# Une notion est un groupe nominal (« de Thalès », « la médiatrice d'un segment »), pas une phrase : un verbe
# conjugué ou une condition signale le début de l'énoncé recopié, qui ne nomme rien.
SENTENCE = re.compile(r"(?i)\b(est|sont|admet|admettent|a pour|ont|si|alors|soit|soient|on|peut|doit|vaut|égale?s?)\b|=")
ARTICLE = re.compile(r"(?i)^(le|la|les|l['’]|un|une)\b ?")


def _question(nature: str, notion: str) -> str | None:
    notion = re.sub(r"\s+", " ", notion).strip(" .:;,?«»\"").replace("’", "'")
    if SENTENCE.search(notion) or len(notion) > 70:
        return None
    if nature == "définition":
        notion = re.sub(r"(?i)^(la )?d[ée]finition ", "", notion)
        for start, article in (("de la ", "la "), ("de l'", "l'"), ("du ", "le "), ("des ", "les "), ("d'", "")):
            if notion.lower().startswith(start):
                notion = article + notion[len(start):]
                break
        if not ARTICLE.match(notion):
            return f"Définir : {notion}"
        elided = re.match(r"(?i)[aeiouyhéèêàâîôû]", notion)
        return f"Qu'est-ce qu{chr(39) if elided else 'e '}{notion} ?"
    if not re.match(r"(?i)(de|du|des|d['’]|sur|relative)\b|d['’]", notion):
        notion = f": {notion}"
    return f"Énoncer {ARTICLES[nature]} {notion}"


def precise(db: Session, card: Flashcard) -> tuple[str | None, str]:
    """Question précise pour la carte, ou (None, raison) si la notion ne peut être nommée sans inventer."""
    chapter, before = _context(db, card)
    kind = KIND_LABEL.get(card.card_type, "propriété")
    answer = ask_model(PROMPT.format(kind=kind, chapter=chapter or "—", before=before[-900:] or "—",
                                     passage=(card.original_text or card.answer)[:1500]), None, SCHEMA)
    notion = (answer.get("notion") or "").strip()
    nature = answer.get("nature") if answer.get("nature") in ARTICLES else None
    if not answer.get("lisible"):
        return None, "passage illisible ou incomplet"
    if nature is None or len(notion) < 3 or len(notion) > 110:
        return None, "notion non trouvée"
    source = set(_content_words(" ".join([card.original_text or "", card.answer or "", before, chapter])))
    words = _content_words(notion)
    if not words:
        return None, "notion trop vague"
    missing = [w for w in words if w not in source]
    if missing:
        return None, f"mots absents du document : {', '.join(missing)}"
    question = _question(nature, notion)
    if question is None:
        return None, "phrase recopiée au lieu du nom de la notion"
    if VAGUE.search(question):
        return None, "notion non trouvée"
    return question, "ok"


def precise_all(db: Session, ids: list[int] | None = None, log=print) -> dict:
    """Renomme les cartes à la question imprécise ; republie celles qui deviennent précises (si publiables)."""
    from datetime import UTC, datetime

    from app.publication import publish

    query = select(Flashcard).where(Flashcard.is_archived.is_(False), Flashcard.status != "rejected")
    if ids:
        query = query.where(Flashcard.id.in_(ids))
    cards = [c for c in db.scalars(query.order_by(Flashcard.id)) if VAGUE.search(c.question or "")]
    log(f"{len(cards)} carte(s) à préciser.")
    totals: dict = {}
    for index, card in enumerate(cards, 1):
        try:
            question, reason = precise(db, card)
        except ValueError:
            question, reason = None, "réponse du modèle illisible"
        if question:
            before = card.question
            card.question = question
            record(db, None, "precise_question", "flashcard", card.id, before=before, after=question,
                   rule="notion nommée d'après le document (mots vérifiés)")
            outcome = publish(db, card, datetime.now(UTC)) or "publiée"
        else:
            card.question = f"{TO_SPECIFY} : {ARTICLES.get('propriété') if card.card_type == 'question' else card.card_type}"
            card.is_published = False
            outcome = reason
        db.commit()
        totals[outcome] = totals.get(outcome, 0) + 1
        log(f"[{index}/{len(cards)}] carte {card.id} : {question or '—'} ({outcome})")
    return totals
