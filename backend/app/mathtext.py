"""Formules mathématiques : les énoncés sont saisis en LaTeX ($…$ en ligne, $$…$$ centré).

Le serveur convertit en MathML, que les navigateurs affichent nativement (hors ligne, sans police à télécharger).
Chaque formule garde aussi son LaTeX (`data-tex`) : l'application web la compose avec KaTeX (copié dans le
projet, licence MIT), rendu typographique proche d'un document imprimé ; le MathML reste en secours.
Le texte hors formules est échappé : aucun HTML saisi n'est jamais injecté tel quel dans la page.
"""

import html
import re
from functools import lru_cache

from latex2mathml.converter import convert

# $$…$$ ou \[…\] (bloc), $…$ ou \(…\) (en ligne) ; « \$ » reste un dollar littéral.
MATH = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]|(?<![\\$])\$(?!\s)([^$\n]+?)(?<![\s\\])\$|\\\((.+?)\\\)", re.DOTALL)


@lru_cache(maxsize=4096)
def latex_to_mathml(latex: str, block: bool = False) -> str | None:
    try:
        return convert(latex.strip(), display="block" if block else "inline")
    except Exception:  # formule invalide : on la laisse visible telle quelle pour correction
        return None


def render(text: str) -> dict:
    """HTML sûr (texte échappé + MathML) et liste des formules non reconnues."""
    out: list[str] = []
    errors: list[str] = []
    position = 0
    for match in MATH.finditer(text):
        out.append(html.escape(text[position:match.start()]).replace("\\$", "$"))
        block = match.group(1) is not None or match.group(2) is not None
        latex = next(g for g in match.groups() if g is not None)
        mathml = latex_to_mathml(latex, block)
        if mathml is None:
            errors.append(latex)
            out.append(f'<code class="math-error">{html.escape(match.group(0))}</code>')
        else:
            tex = html.escape(latex.strip(), quote=True)
            out.append(f'<span class="tex" data-display="{int(block)}" data-tex="{tex}">{mathml}</span>')
        position = match.end()
    out.append(html.escape(text[position:]).replace("\\$", "$"))
    return {"html": "".join(out).replace("\n", "<br>"), "errors": errors, "has_math": position > 0 or bool(errors)}
