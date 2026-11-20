"""Série d'un document de lycée trouvée en croisant son contenu avec les programmes officiels.

Référence : progressions annuelles 2026-2027 de la DPFC (Côte d'Ivoire, https://dpfc-ci.net), téléchargées dans
`<stockage>/programmes/` (hors Git). Chaque progression est découpée par classe et série (ex. « Tle C »,
« Premières C et D »). Pour un document de matière M et de niveau N, on compte les termes des leçons
**propres** à chaque série (absents des autres séries du même niveau) retrouvés dans le texte du document.

Règles (décisions notées dans le journal) :
- A1 et A2 sont regroupées en « A » (séries listées par l'utilisateur : 2nde A, C ; 1ère et Tle A, C, D, E) ;
- en mathématiques et physique-chimie, la série E suit le programme de la série C ;
- une matière dont le programme est identique pour toutes les séries du niveau (ex. histoire-géographie)
  vaut pour toutes les séries de ce niveau.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.storage import storage_root

SERIES_BY_GRADE = {"2NDE": ["A", "C"], "1RE": ["A", "C", "D", "E"], "TLE": ["A", "C", "D", "E"]}
E_FOLLOWS_C = {"mathematiques", "physique-chimie"}

GRADE_WORDS = {
    "2NDE": r"(?:2de|2nde|seconde|secondes)",
    "1RE": r"(?:1re|1ere|1e|premiere|premieres)",
    "TLE": r"(?:tle|tles|terminale|terminales)",
}
SERIES_TEXT = r"((?:a1|a2|a|c|d|e)(?:\s*(?:-|,|et|/)\s*(?:a1|a2|a|c|d|e))*)"

# Fichier (début du nom) → matière (nom normalisé) et forme des titres de section.
FILES = {
    "MATHEMATIQUES": "mathematiques",
    "PHYSIQUE-CHIMIE": "physique-chimie",
    "SVT": "svt",
    "FRANCAIS_2nd": "francais",
    "PHILOSOPHIE": "philosophie",
    "ANGLAIS_2nd": "anglais",
    "HG_": "histoire-geographie",
}
SUBJECT_ALIASES = {
    "mathematiques": "mathematiques", "maths": "mathematiques", "math": "mathematiques",
    "physique-chimie": "physique-chimie", "physique chimie": "physique-chimie", "physique": "physique-chimie",
    "pc": "physique-chimie", "svt": "svt", "sciences de la vie et de la terre": "svt", "francais": "francais",
    "philosophie": "philosophie", "anglais": "anglais", "histoire-geographie": "histoire-geographie",
    "histoire geographie": "histoire-geographie", "histoire-geo": "histoire-geographie", "hg": "histoire-geographie",
}
STOPWORDS = set("""
avec dans pour par sans sous entre leur leurs cette ces des les une sur aux du de la le et ou en au est sont
trimestre semaine semaines mois heures heure lecon lecons regulation devoir niveau evaluation evaluations
septembre octobre novembre decembre janvier fevrier mars avril juin juillet progression progressions
annuelle annuelles nationale national page volume horaire classe classes taux execution premier premiere
deuxieme troisieme second seconde terminale terminales premieres secondes theme themes unite unites
competence competences situation activite activites seance seances ecrit oral annee scolaire dpfc
coordination disciplinaire cndf igena usage pedagogique administratif professeur sequence sequences
""".split())


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text)


def terms(text: str) -> set[str]:
    words = [w for w in norm(text).split() if len(w) >= 4 and w not in STOPWORDS and not w.isdigit()]
    return set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}


def _series_letters(raw: str, subject: str) -> list[str]:
    letters: list[str] = []
    for part in re.findall(r"a1|a2|a|c|d|e", raw):
        letter = "A" if part.startswith("a") else part.upper()
        if letter not in letters:
            letters.append(letter)
    if subject in E_FOLLOWS_C and "C" in letters and "E" not in letters:
        letters.append("E")
    return letters


@dataclass
class Programme:
    """Termes du programme par (niveau, séries) pour une matière."""

    sections: dict[tuple[str, tuple[str, ...]], set[str]] = field(default_factory=dict)


def _header(line: str, subject: str) -> tuple[str, tuple[str, ...]] | None:
    text = norm(line).strip()
    if len(text) > 160 or not re.search(r"progression|niveau|classe", text):
        return None
    for grade, words in GRADE_WORDS.items():
        match = re.search(rf"\b{words}\s*(?:\(\s*\w+\s*\)\s*)?{SERIES_TEXT}?\b", text)
        if not match:
            continue
        letters = _series_letters(match.group(1) or "", subject)
        return grade, tuple(letters or SERIES_BY_GRADE[grade])
    return None


def parse(text: str, subject: str) -> Programme:
    programme = Programme()
    current: tuple[str, tuple[str, ...]] | None = None
    for line in text.splitlines():
        header = _header(line, subject)
        if header is not None:
            current = header
            continue
        if current is not None:
            programme.sections.setdefault(current, set()).update(terms(line))
    return programme


def programmes_dir() -> Path:
    return storage_root().parent / "programmes"


@lru_cache(maxsize=1)
def load() -> dict[str, Programme]:
    """Programmes disponibles (texte extrait des PDF officiels, mis en cache dans un .txt voisin)."""
    found: dict[str, Programme] = {}
    folder = programmes_dir()
    if not folder.exists():
        return found
    for pdf in sorted(folder.glob("*.pdf")):
        subject = next((s for prefix, s in FILES.items() if pdf.name.startswith(prefix)), None)
        if subject is None:
            continue
        cache = pdf.with_suffix(".txt")
        if not cache.exists():
            import pypdf

            cache.write_text("\n".join(page.extract_text() or "" for page in pypdf.PdfReader(pdf).pages))
        found[subject] = parse(cache.read_text(), subject)
    return found


def subject_key(name: str | None) -> str | None:
    if not name:
        return None
    key = norm(name).strip().replace(" ", "-")
    return SUBJECT_ALIASES.get(key) or SUBJECT_ALIASES.get(key.replace("-", " "))


@dataclass
class Match:
    series: list[str]
    method: str
    scores: dict[str, int]


def match_series(subject_name: str | None, grade_code: str | None, text: str) -> Match | None:
    """Séries du document d'après le programme officiel, ou None si le programme ne permet pas de conclure."""
    if grade_code not in SERIES_BY_GRADE:
        return None
    programme = load().get(subject_key(subject_name) or "")
    if programme is None:
        return None
    sections = {key: words for key, words in programme.sections.items() if key[0] == grade_code}
    if not sections:
        return None
    if len(sections) == 1:  # même programme pour toutes les séries du niveau
        return Match(list(SERIES_BY_GRADE[grade_code]), "programme commun à toutes les séries", {})
    document_terms = terms(text)
    scores: dict[tuple, int] = {}
    for key, words in sections.items():
        others = set().union(*(w for k, w in sections.items() if k != key))
        scores[key] = len((words - others) & document_terms)
    top = max(scores.values())
    labels = {"-".join(k[1]): v for k, v in scores.items()}
    if top < 3:
        return None
    chosen = [k for k, v in scores.items() if v >= 0.6 * top]
    series: list[str] = []
    for key in chosen:
        series += [s for s in key[1] if s not in series]
    return Match(sorted(series), "croisement avec le programme officiel", labels)
