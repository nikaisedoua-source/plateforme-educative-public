"""Correction automatique côté serveur. Le navigateur ne reçoit jamais la bonne réponse avant que la règle
d'accès au corrigé ne l'autorise."""

import re
import unicodedata

from app.models import Exercise

AUTO_TYPES = {"qcm", "vrai_faux", "numerique", "a_completer"}


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = value.replace("$", "")
    return re.sub(r"[\s.;:!?'\"«»()]+", " ", value).strip()


def parse_number(value: str) -> float | None:
    text = value.strip().replace("−", "-").replace(" ", "").replace(" ", "")
    text = text.replace(",", ".")
    fraction = re.fullmatch(r"(-?\d+(?:\.\d+)?)/(-?\d+(?:\.\d+)?)", text)
    try:
        if fraction:
            denominator = float(fraction.group(2))
            return float(fraction.group(1)) / denominator if denominator else None
        return float(text)
    except ValueError:
        pass
    # Écriture du clavier mathématique : \frac{5}{2}, 2{,}5, \sqrt{4}…
    from app.answers import to_sympy  # import local : sympy n'est chargé qu'au besoin

    expression = to_sympy(value)
    if expression is None or expression.free_symbols:
        return None
    try:
        number = complex(expression.evalf())
    except (TypeError, ValueError):
        return None
    return number.real if abs(number.imag) < 1e-12 else None


def grade(exercise: Exercise, answer_text: str | None, option_ids: list[int] | None) -> tuple[str, float]:
    """Renvoie (résultat, score). « submitted » : réponse libre, à comparer au corrigé par l'élève."""
    points = exercise.points
    kind = exercise.exercise_type
    if kind in ("qcm", "vrai_faux"):
        correct = {o.id for o in exercise.options if o.is_correct}
        chosen = set(option_ids or [])
        if not correct:
            return "submitted", 0.0
        if chosen == correct:
            return "correct", float(points)
        if kind == "qcm" and len(correct) > 1 and chosen and chosen < correct:
            return "partial", round(points * len(chosen) / len(correct), 2)
        return "incorrect", 0.0
    verdict = check_text(kind, exercise.expected_answer, exercise.numeric_tolerance, answer_text)
    if verdict is None:
        return "submitted", 0.0
    return ("correct", float(points)) if verdict else ("incorrect", 0.0)


def check_text(kind: str, expected: str | None, tolerance: float | None, answer_text: str | None) -> bool | None:
    """Réponse écrite : True/False, ou None si elle ne peut pas être corrigée automatiquement.
    `vrai_faux` écrit (cartes mémoire) se corrige comme un texte à compléter."""
    expected = (expected or "").strip()
    if not expected or answer_text is None:
        return None
    if kind == "numerique":
        given, target = parse_number(answer_text), parse_number(expected)
        if target is None:
            return None
        if given is None:
            return False
        return abs(given - target) <= (tolerance or 1e-9)
    if kind in ("a_completer", "vrai_faux"):
        accepted = {_plain(item) for item in expected.split("|") if item.strip()}
        return _plain(answer_text) in accepted
    return None
