"""Formules LaTeX → MathML (affichage natif des énoncés de maths)."""

from fastapi.testclient import TestClient

from app.mathtext import render
from test_api import client, create_user  # noqa: F401


def test_inline_and_block_formulas_are_converted():
    result = render(r"Soit $f(x)=\frac{x^2+1}{x}$ sur $]0;+\infty[$. Calculer $$\int_0^1 f(t)\,dt$$ coût 5 \$")
    assert result["has_math"] and not result["errors"]
    assert result["html"].count("<math") == 3 and 'display="block"' in result["html"]
    assert "<mfrac>" in result["html"] and result["html"].endswith("coût 5 $")


def test_text_is_escaped_and_bad_formula_reported():
    result = render("<script>alert(1)</script> $\\frac{1}{$ fin")
    assert "<script>" not in result["html"] and "&lt;script&gt;" in result["html"]
    plain = render("Prix : 3 $ et 4 $ DEMO")  # dollars isolés suivis d'un espace : pas de formule
    assert not plain["has_math"]


def test_render_endpoint_requires_login(client: TestClient):
    assert client.post("/api/v1/math/render", json={"text": "$x$"}).status_code == 401
    token = create_user(client, role="student", email="eleve@example.com")
    response = client.post("/api/v1/math/render", json={"text": "$x^2$"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200 and "<msup>" in response.json()["html"]
