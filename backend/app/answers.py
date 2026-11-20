"""Comparaison d'une réponse courte d'élève (saisie avec le clavier mathématique, donc en LaTeX) au résultat
du corrigé. Les écritures équivalentes sont acceptées : ½ = 0,5 = 2/4, 2(x+1) = 2x+2, S = {2 ; 3} = {3 ; 2},
« x = 4 » = « 4 ». Tout se fait côté serveur : le navigateur ne reçoit jamais le résultat attendu avant que la
règle d'accès au corrigé ne l'autorise.

`equivalent` renvoie True / False, ou None quand la comparaison n'est pas possible (l'élève compare alors
lui-même avec le corrigé).
"""

import re
import unicodedata
from functools import lru_cache

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor, implicit_multiplication_application, parse_expr, standard_transformations,
)

TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
SAFE_NAMES = {
    "sqrt": sympy.sqrt, "root": sympy.root, "pi": sympy.pi, "E": sympy.E, "oo": sympy.oo, "ln": sympy.log,
    "log": sympy.log, "exp": sympy.exp, "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan,
    "Abs": sympy.Abs,
}
WORDS_TRUE = {"vrai", "v", "oui", "true"}
WORDS_FALSE = {"faux", "f", "non", "false"}


def _plain_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


# Mot d'au moins trois lettres hors commande LaTeX : la réponse est rédigée (« rectangle », « la hauteur »)
# et se compare comme un texte, jamais comme un produit de variables (sinon « chien » vaudrait « niche »).
WORD = re.compile(r"(?<![\\A-Za-z])[A-Za-zÀ-ÿœ]{3,}")
ARTICLES = re.compile(r"^(?:(?:le|la|les|l|un|une|des|du|de|d)\s+)+")


def _words(value: str) -> str:
    return ARTICLES.sub("", _plain_text(value))


def _is_text(value: str) -> bool:
    return any(match.group(0) not in SAFE_NAMES for match in WORD.finditer(value))


def _braced(text: str, start: int) -> tuple[str, int]:
    """Contenu de l'accolade ouvrante située à `start` et position après l'accolade fermante."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    raise ValueError("accolade non fermée")


def _argument(text: str, start: int) -> tuple[str, int]:
    """Argument d'une commande : {…} ou un seul caractère (\\frac12)."""
    while start < len(text) and text[start] == " ":
        start += 1
    if start < len(text) and text[start] == "{":
        return _braced(text, start)
    if start < len(text):
        return text[start], start + 1
    raise ValueError("argument manquant")


def latex_to_python(latex: str) -> str:
    """Traduit le LaTeX produit par le clavier mathématique en écriture lisible par sympy."""
    text = latex.strip().strip("$").strip().replace("{,}", ",")  # virgule décimale du clavier mathématique
    text = text.replace("\\left", "").replace("\\right", "").replace("\\,", " ").replace("\\!", "")
    text = text.replace("\\displaystyle", "").replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    text = re.sub(r"\\operatorname\{(\w+)\}", r"\\\1", text)
    text = text.replace("−", "-").replace("×", "*").replace("÷", "/").replace("·", "*")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)  # virgule décimale française
    text = re.sub(r"(?<=\d) (?=\d{3}\b)", "", text)  # 1 000
    out: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith("\\frac", index):
            numerator, index = _argument(text, index + 5)
            denominator, index = _argument(text, index)
            out.append(f"(({latex_to_python(numerator)})/({latex_to_python(denominator)}))")
            continue
        if text.startswith("\\sqrt", index):
            index += 5
            degree = None
            if index < len(text) and text[index] == "[":
                end = text.index("]", index)
                degree, index = text[index + 1:end], end + 1
            body, index = _argument(text, index)
            body = latex_to_python(body)
            # Espace devant : « x\sqrt{2} » ne doit pas devenir « xsqrt(2) », lu comme un produit de lettres.
            out.append(f" root(({body}),({latex_to_python(degree)}))" if degree else f" sqrt({body})")
            continue
        if text[index] == "^":
            power, index = _argument(text, index + 1)
            out.append(f"**({latex_to_python(power)})")
            continue
        if text[index] == "{":
            body, index = _braced(text, index)
            out.append(f"({latex_to_python(body)})")
            continue
        command = re.match(r"\\([a-zA-Z]+)", text[index:])
        if command:
            name = command.group(1)
            index += len(command.group(0))
            mapping = {"times": "*", "cdot": "*", "div": "/", "pi": "pi", "infty": "oo", "ln": "ln", "log": "log",
                       "exp": "exp", "sin": "sin", "cos": "cos", "tan": "tan", "e": "E"}
            if name not in mapping:
                raise ValueError(f"commande non prise en charge : \\{name}")
            out.append(f" {mapping[name]} ")
            continue
        if text[index] == "|":
            end = text.find("|", index + 1)
            if end < 0:
                raise ValueError("valeur absolue non fermée")
            out.append(f"Abs({latex_to_python(text[index + 1:end])})")
            index = end + 1
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


@lru_cache(maxsize=2048)
def to_sympy(latex: str) -> sympy.Expr | None:
    try:
        python = latex_to_python(latex)
        if not python.strip() or re.search(r"[=<>;\[\]]|__|lambda|import", python):
            return None
        symbols = {name: sympy.Symbol(name) for name in set(re.findall(r"\b[a-zA-Z]\b", python)) - {"E"}}
        return parse_expr(python, local_dict=SAFE_NAMES | symbols, transformations=TRANSFORMS, evaluate=True)
    except Exception:  # écriture non reconnue : pas de verdict automatique
        return None


def _same_value(first: sympy.Expr, second: sympy.Expr) -> bool:
    try:
        if first == second:
            return True
        if first.has(sympy.oo, -sympy.oo, sympy.zoo) or second.has(sympy.oo, -sympy.oo, sympy.zoo):
            return False
        difference = sympy.simplify(first - second)
        if difference == 0:
            return True
        free = sorted(difference.free_symbols, key=str)
        if not free:
            return abs(complex(difference.evalf())) < 1e-9
        for trial in (0.37, 1.61, -2.29):  # identité vérifiée en quelques points
            value = complex(difference.subs({s: trial for s in free}).evalf())
            if abs(value) > 1e-9:
                return False
        return True
    except Exception:
        return False


SET = re.compile(r"^(?:S\s*=\s*)?\\?\{(.*)\\?\}$")
INTERVAL = re.compile(r"^(?:S\s*=\s*)?(\]|\[)(.+?)[;,](.+?)(\]|\[)$")


def _clean(value: str) -> str:
    value = value.strip().strip("$").strip().replace("{,}", ",")
    value = value.replace("\\left", "").replace("\\right", "").replace("\\lbrace", "\\{").replace("\\rbrace", "\\}")
    value = value.replace("\\mathbb{R}", "R").replace("\\R", "R").replace("ℝ", "R")
    value = re.sub(r"\\(?:text|mathrm)\{([^}]*)\}", r"\1", value)
    return re.sub(r"\s+", " ", value).replace("\\{", "{").replace("\\}", "}").strip()


def _elements(body: str) -> list[str]:
    return [item.strip() for item in re.split(r";|\\;", body) if item.strip()]


def equivalent(given: str | None, expected: str | None) -> bool | None:
    if not given or not expected or not given.strip() or not expected.strip():
        return None
    given, expected = _clean(given), _clean(expected)
    if _plain_text(expected) in WORDS_TRUE | WORDS_FALSE:
        word = _plain_text(given)
        if word not in WORDS_TRUE | WORDS_FALSE:
            return False
        return (word in WORDS_TRUE) == (_plain_text(expected) in WORDS_TRUE)

    if _is_text(expected):
        return _words(given) == _words(expected)

    expected_set, given_set = SET.match(expected.replace("\\{", "{")), SET.match(given)
    if expected_set:
        if not given_set:
            items = _elements(given)
            if len(items) != 1:
                return False
            given_items = items
        else:
            given_items = _elements(given_set.group(1))
        expected_items = _elements(expected_set.group(1))
        if len(given_items) != len(expected_items):
            return False
        remaining = [to_sympy(item) for item in expected_items]
        if any(item is None for item in remaining):
            return None
        for item in given_items:
            value = to_sympy(item)
            if value is None:
                return False
            match = next((index for index, other in enumerate(remaining) if _same_value(value, other)), None)
            if match is None:
                return False
            remaining.pop(match)
        return True

    expected_interval = INTERVAL.match(expected)
    if expected_interval:
        given_interval = INTERVAL.match(given)
        if not given_interval:
            return False
        if given_interval.group(1) != expected_interval.group(1) or given_interval.group(4) != expected_interval.group(4):
            return False
        for index in (2, 3):
            a, b = to_sympy(given_interval.group(index)), to_sympy(expected_interval.group(index))
            if a is None or b is None or not _same_value(a, b):
                return False
        return True

    # « x = 4 » : on compare le membre de droite ; « 4 » seul est aussi accepté.
    def right_side(value: str) -> tuple[str | None, str]:
        if value.count("=") == 1:
            left, right = value.split("=")
            return left.strip(), right.strip()
        return None, value

    expected_left, expected_value = right_side(expected)
    given_left, given_value = right_side(given)
    if given_left is not None and expected_left is not None and _plain_text(given_left) != _plain_text(expected_left):
        return False
    target = to_sympy(expected_value)
    if target is None:
        return _plain_text(given_value) == _plain_text(expected_value) if _plain_text(expected_value) else None
    value = to_sympy(given_value)
    if value is None:
        return False
    return _same_value(value, target)
