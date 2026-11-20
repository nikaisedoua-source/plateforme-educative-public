"""Cartes mémoire : la question nomme la notion (« Énoncer la propriété de Thalès »), jamais une page ni les
premiers mots du passage ; le nom proposé par le modèle local ne contient aucun mot absent du document."""

from types import SimpleNamespace

import pytest

from app import flashcard_questions
from app.flashcards import card_problem, propose


def test_untitled_passage_is_never_a_page_reference():
    cards = propose([(73, "Propriété\nUne homothétie conserve le milieu d'un segment et le parallélisme.")])
    assert cards and all("p. 73" not in c.question and "commence par" not in c.question for c in cards)
    assert card_problem(cards[0].question, cards[0].answer) == "question imprécise : la notion n'est pas nommée"


@pytest.mark.parametrize("question", [
    "Restituer la propriété (p. 73) qui commence par : « une homothétie … »",
    "À préciser : la propriété",
])
def test_vague_questions_are_blocked(question):
    assert card_problem(question, "Une homothétie conserve le milieu d'un segment.") is not None


def test_named_question_is_allowed():
    assert card_problem("Énoncer la propriété de Thalès", "Si (MN) // (BC) alors AM/AB = AN/AC.") is None


def _card(text):
    return SimpleNamespace(card_type="question", original_text=text, answer=text, chapter_id=None,
                           document_id=1, page_number=1)


def test_model_notion_is_checked_against_the_document(monkeypatch):
    monkeypatch.setattr(flashcard_questions, "_context", lambda db, card: ("Homothéties", ""))
    passage = "Propriété\nUne homothétie conserve le milieu d'un segment."
    monkeypatch.setattr(flashcard_questions, "ask_model", lambda *a, **k: {
        "lisible": True, "nature": "propriété", "notion": "de conservation du milieu par une homothétie"})
    question, reason = flashcard_questions.precise(None, _card(passage))
    assert question is None and "conservation" in reason  # mot absent du passage : refusé
    monkeypatch.setattr(flashcard_questions, "ask_model", lambda *a, **k: {
        "lisible": True, "nature": "propriété", "notion": "de l'homothétie et du milieu d'un segment"})
    question, reason = flashcard_questions.precise(None, _card(passage))
    assert question == "Énoncer la propriété de l'homothétie et du milieu d'un segment" and reason == "ok"
    monkeypatch.setattr(flashcard_questions, "ask_model", lambda *a, **k: {
        "lisible": False, "nature": "propriété", "notion": "de Thalès"})
    assert flashcard_questions.precise(None, _card(passage))[0] is None


def test_definition_question_reads_naturally(monkeypatch):
    monkeypatch.setattr(flashcard_questions, "_context", lambda db, card: ("", ""))
    monkeypatch.setattr(flashcard_questions, "ask_model", lambda *a, **k: {
        "lisible": True, "nature": "définition", "notion": "une plante autotrophe"})
    card = _card("Définition\nUne plante autotrophe : plante qui produit ses propres matières organiques.")
    assert flashcard_questions.precise(None, card)[0] == "Qu'est-ce qu'une plante autotrophe ?"


@pytest.mark.parametrize("nature, notion, expected", [
    ("définition", "de l'enallage", "Qu'est-ce que l'enallage ?"),
    ("définition", "couple de coordonnées du vecteur AB", "Définir : couple de coordonnées du vecteur AB"),
    ("définition", "la rotation de centre O", "Qu'est-ce que la rotation de centre O ?"),
    ("propriété", "deux polynômes sont égaux si et seulement si", None),
    ("propriété", "de l'équation f(x) = 0 admet une solution", None),
    ("théorème", "de Thalès", "Énoncer le théorème de Thalès"),
])
def test_question_grammar(nature, notion, expected):
    assert flashcard_questions._question(nature, notion) == expected


def test_rewrite_must_cover_the_whole_document():
    """Retour utilisateur : un énoncé réécrit réduit à « Exercice 1 : » était affiché comme sûr."""
    from app.rewrite import coverage_problems

    raw = ("Exercice 1 :\nOn se place dans un repère (O ; i , j ).\nSoient les points A(- 7\n2 ; 2), B(-2 ; 5).\n"
           "1. Déterminer les coordonnées des vecteurs AB et CD.")
    dropped = coverage_problems(raw, "Exercice 1 :", ["Déterminer les coordonnées des vecteurs $\\vec{AB}$ et $\\vec{CD}$."])
    assert any("incomplet" in p for p in dropped) and any("nombre" in p for p in dropped)
    full = ("Exercice 1 :\nOn se place dans un repère $(O ; \\vec{i}, \\vec{j})$.\n"
            "Soient les points $A(-\\frac{7}{2} ; 2)$, $B(-2 ; 5)$.")
    assert coverage_problems(raw, full, ["1. Déterminer les coordonnées des vecteurs $\\vec{AB}$ et $\\vec{CD}$."]) == []
    assert "formule écrite hors LaTeX" in coverage_problems("P(x) = x4 + 1", "P(x) = x^4 + 1", [])
