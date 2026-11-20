"""Phase 4 : énoncés réécrits en LaTeX, questions séparées, réponses « résultat » vérifiées par le serveur
(écritures équivalentes acceptées), démonstrations facultatives et auto-évaluées."""

import pytest
from fastapi.testclient import TestClient

from app import rewrite
from app.answers import equivalent
from app.database import get_db
from app.main import app
from app.models import Correction, Exercise, ExerciseQuestion
from test_api import client, create_user  # noqa: F401
from test_student import _student, isolated_storage, world  # noqa: F401


@pytest.mark.parametrize("given, expected, verdict", [
    (r"\frac{1}{2}", "0,5", True),
    ("2/4", r"\frac12", True),
    (r"2\left(x+1\right)", "2x+2", True),
    (r"\sqrt{2}x^2-3", r"x^{2}\sqrt{2}-3", True),
    (r"S=\{3;2\}", r"\{2 ; 3\}", True),
    ("x=4", "4", True),
    ("4", "x = 4", True),
    ("5", "x=4", False),
    ("y=2", "x=2", False),
    (r"]-\infty;2]", r"]-\infty ; 2]", True),
    ("[1;2]", "]1;2]", False),
    ("Vrai", "vrai", True),
    ("faux", "Vrai", False),
    (r"\frac{20}{7}", r"\frac{4\times5}{7}", True),
    (r"\sqrt[3]{8}", "2", True),
    ("3,14", r"\pi", False),
    ("abc", r"\frac{1}{2}", False),
    ("2{,}5", r"\frac{5}{2}", True),  # virgule décimale écrite par MathLive
    (r"\left\lbrace1{,}5;2\right\rbrace", r"\{2 ; 1,5\}", True),
])
def test_equivalent_writings_are_accepted(given, expected, verdict):
    assert equivalent(given, expected) is verdict


def test_no_verdict_without_reference():
    assert equivalent("4", None) is None
    assert equivalent("", "4") is None


def test_fidelity_checks_detect_invention():
    raw = "Exercice 3\nSoit f la fonction définie sur R par f(x) = x2 - 3x + 2. Calcule f(0) puis f(1)."
    good = "Exercice 3\nSoit $f$ la fonction définie sur $\\mathbb{R}$ par $f(x) = x^{2} - 3x + 2$. Calcule $f(0)$ puis $f(1)$."
    assert rewrite.fidelity_problems(raw, good) == []
    invented = ("Exercice 3\nOn considère une suite géométrique de raison quelconque, démontrer rigoureusement "
                "chaque propriété énoncée précédemment avec soin $u_{n+1} = 7u_{n}$.")
    assert any("mots" in p for p in rewrite.fidelity_problems(raw, invented))
    broken = "Soit $f$ la fonction définie sur $\\frac{1}{$ par $f(x) = x^{2} - 3x + 2$. Calcule $f(0)$ puis $f(1)$."
    assert any("LaTeX" in p for p in rewrite.fidelity_problems(raw, broken))


def test_expected_answer_must_appear_in_the_correction():
    raw = "Corrigé 3\n1) f(0) = 2\n2) f(1) = 0"
    assert rewrite.answer_supported("f(0) = 2", "$f(0) = 2$", raw)
    assert not rewrite.answer_supported("f(0) = 5", "$f(0) = 5$", raw)  # 5 n'est pas dans le corrigé fourni
    assert not rewrite.answer_supported("", "", raw)


def _db():
    return next(app.dependency_overrides[get_db]())


def test_rewrite_exercise_stores_latex_and_questions(client: TestClient, world: dict, monkeypatch):
    replies = iter([
        {"enonce": "Énoncé Calcul DEMO : calcule $\\frac{5}{2}$ puis démontre.",
         "questions": [{"numero": "1", "texte": "Calcule $\\frac{5}{2}$.", "nature": "resultat"},
                       {"numero": "2", "texte": "Démontre le résultat.", "nature": "demonstration"}]},
        {"corrige": "1) $\\frac{5}{2} = 2,5$", "resultats": [{"numero": "1", "resultat": "2,5"},
                                                           {"numero": "2", "resultat": ""}]},
    ])
    monkeypatch.setattr(rewrite, "ask_model", lambda prompt, image, schema: next(replies))
    monkeypatch.setattr(rewrite, "region_image", lambda *args, **kwargs: b"png")
    db = _db()
    exercise = db.get(Exercise, world["numeric"])
    exercise.original_text = "Énoncé Calcul DEMO : calcule 5 sur 2 puis démontre. Calcule 5/2. Démontre le résultat."
    exercise.correction = Correction(original_text="Corrigé : 1) 5/2 = 2,5", final_answer="2,5", status="validated",
                                     source_document_id=exercise.document_id, source_page=1)
    assert rewrite.rewrite_exercise(db, exercise) == "ok"
    assert rewrite.rewrite_correction(db, exercise) == "ok"
    db.commit()
    labels = [(q.label, q.kind, q.expected_answer) for q in exercise.questions]
    assert labels == [("1", "result", "2,5"), ("2", "proof", None)]
    assert exercise.statement.startswith("Énoncé Calcul")  # l'extraction n'est jamais écrasée


def _questions(world: dict, expected: str | None = "2,5") -> tuple[int, int]:
    db = _db()
    exercise = db.get(Exercise, world["numeric"])
    exercise.statement_latex = "Calcule $\\frac{5}{2}$, puis démontre."
    exercise.rewrite_status = "ok"
    exercise.questions.extend([
        ExerciseQuestion(label="1", text="Calcule $\\frac{5}{2}$.", kind="result", expected_answer=expected,
                         sort_order=0),
        ExerciseQuestion(label="2", text="Démontre.", kind="proof", sort_order=1),
    ])
    exercise.correction = Correction(original_text="2,5", final_answer="2,5", status="validated",
                                     source_document_id=exercise.document_id, source_page=1)
    db.commit()
    return exercise.questions[0].id, exercise.questions[1].id


def test_student_answers_question_by_question(client: TestClient, world: dict):
    result_id, proof_id = _questions(world)
    student = _student(client, world["admin"], "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    view = client.get(f"/api/v1/student/exercises/{world['numeric']}", headers=student)
    assert view.status_code == 200, view.text
    body = view.json()
    assert body["statement"].startswith("Calcule $\\frac") and body["original_first"] is False
    assert [(q["label"], q["kind"], q["checkable"]) for q in body["questions"]] == [
        ("1", "result", True), ("2", "proof", False)]
    assert "2,5" not in view.text  # le résultat attendu n'est jamais envoyé avant la correction

    url = "/api/v1/student/questions/{}/attempts"
    wrong = client.post(url.format(result_id), json={"answer_latex": "3"}, headers=student)
    assert wrong.status_code == 201 and wrong.json()["result"] == "incorrect"
    assert wrong.json()["correction_available"] is True  # une seule question répondue suffit
    assert client.post(url.format(result_id), json={"answer_latex": r"\frac{5}{2}"}, headers=student).status_code == 429

    # La démonstration n'est pas obligatoire ; l'auto-évaluation exige d'avoir ouvert la correction.
    assert client.post(url.format(proof_id), json={"self_check": "self_ok"}, headers=student).status_code == 409
    correction = client.get(f"/api/v1/student/exercises/{world['numeric']}/correction", headers=student)
    assert correction.status_code == 200 and correction.json()["question_answers"] == {"1": "2,5"}
    seen = client.get(f"/api/v1/student/exercises/{world['numeric']}", headers=student).json()
    assert seen["correction_viewed"] is True and body["correction_viewed"] is False
    graded = client.post(url.format(proof_id), json={"self_check": "self_review"}, headers=student)
    assert graded.status_code == 201 and graded.json()["after_correction"] is True


def test_equivalent_answer_is_correct(client: TestClient, world: dict):
    result_id, _ = _questions(world)
    student = _student(client, world["admin"], "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    done = client.post(f"/api/v1/student/questions/{result_id}/attempts", json={"answer_latex": r"\frac{5}{2}"},
                       headers=student)
    assert done.json()["result"] == "correct" and done.json()["after_correction"] is False


def test_question_without_reference_is_submitted(client: TestClient, world: dict):
    result_id, _ = _questions(world, expected=None)
    student = _student(client, world["admin"], "c@example.com", "EleveC", world["tle"]["id"], world["tracks"]["TLE-C"])
    done = client.post(f"/api/v1/student/questions/{result_id}/attempts", json={"answer_latex": "2,5"},
                       headers=student)
    assert done.json()["result"] == "submitted"


def test_other_series_cannot_answer(client: TestClient, world: dict):
    result_id, _ = _questions(world)
    student_a = _student(client, world["admin"], "a@example.com", "EleveA", world["tle"]["id"], world["tracks"]["TLE-A"])
    refused = client.post(f"/api/v1/student/questions/{result_id}/attempts", json={"answer_latex": "2,5"},
                          headers=student_a)
    assert refused.status_code == 404


@pytest.mark.parametrize("written, value", [(r"\frac{5}{2}", 2.5), ("2{,}5", 2.5), (r"\sqrt{4}", 2.0), ("x+1", None)])
def test_numeric_cards_accept_math_keyboard(written, value):
    from app.grading import parse_number
    assert parse_number(written) == value


def test_heading_needles_tolerate_spacing():
    from app.processing import _needles

    needles = _needles("EXERCICE 1\xa0: Calcule")
    assert "EXERCICE 1 : Calcule" in needles
    assert "EXERCICE 1" in needles


@pytest.mark.parametrize("text", ["Calcule : 2 , 9  8 + 4  8, 5  7  1", "Calcule      la somme",
                                  "EXERCICE 2 2 Thes 3-10 EB 24 25 ZONE 3 DGEM"])
def test_fidelity_flags_copied_layout(text):
    from app.rewrite import fidelity_problems

    raw = "EXERCICE 1 : Calcule la somme\n2 , 9 8 + 4 8, 5 7 1 + 4 9 5\n2 Thes 3-10 EB 24 25 ZONE 3 DGEM"
    assert fidelity_problems(raw, text)


@pytest.mark.parametrize("name,kind", [
    ("CORRIGES-MATHS-PYRAMIDE-3e.pdf", "corrige"), ("Corrigé MATHS Pyr 2ndC.pdf", "corrige"),
    ("PYRAMIDE TleD corrigé.pdf", "corrige"), ("Devoir_CM2_Cote_dIvoire_2026_2027_Corrige.pdf", "corrige"),
    ("AREX +CORRIGES TleC.pdf", "exercices"), ("Sujets Corrigés Sciences Physique Terminale C, D et E.pdf", "exercices"),
    ("CHIMIE TS2 exos corrigés.pdf", "exercices"), ("Exercise_svt_et_corrigé_.pdf", "exercices"),
    ("Livre 220 Exercices Corrigés Mathématiques 1re.pdf", "exercices"), ("pyramide 4e.pdf", None),
])
def test_kind_from_name(name, kind):
    from app.extraction import kind_from_name

    assert kind_from_name(name) == kind


def test_segment_recognises_humanities_subjects():
    from app.extraction import segment

    text = ("Sujet 1 :\nLa décolonisation de l'Afrique : causes et conséquences. Analyse ce sujet.\n"
            "Commentaire de document\nTexte : Discours de Roosevelt. Présente le document puis explique-le.\n"
            "Dissertation\nLe travail libère-t-il l'homme ? Tu répondras de façon argumentée.")
    found = segment([(1, text)])
    assert [s.heading.lower() for s in found] == ["sujet", "commentaire de document", "dissertation"]


@pytest.mark.parametrize("statement,problem", [
    ("Exercice 9\n    Les figures b et c.", "énoncé trop court"),
    ("Exercice 1\nRésous dans R l'équation 2x + 3 = 7 puis vérifie ta réponse.", None),
    ("Sommaire\nLeçon 1 : nombres entiers ........ 3\nLeçon 2 : fractions ........ 9\n"
     "Leçon 3 : proportionnalité ........ 15\nLeçon 4 : géométrie plane ........ 21", "page de sommaire"),
    ("Exercice 1\n" + "Calcule la somme des nombres. " * 500, "énoncé trop long"),
])
def test_quality_problem(statement, problem):
    from app.models import Exercise
    from app.publication import quality_problem

    found = quality_problem(Exercise(statement=statement, rewrite_status="none"))
    if problem is None:
        assert found is None
    else:
        assert found and found.startswith(problem)


def test_exam_rubrics_split_subjects_and_bareme():
    from app.extraction import rubric, segment

    assert rubric("MATHEMATIQUES") == (False, "Mathématiques", None)
    assert rubric("II- EDHC") == (False, "", "EDHC")
    assert rubric("BAREME EPREUVE DE MATHEMATIQUE CM2 50/50") == (True, "Mathématiques", None)
    assert rubric("3- SCIENCES ET TECHNOLOGIE 30/30") == (False, "SVT", "Sciences et technologie")
    assert rubric("Mathématiques") is None  # en-tête courant d'un manuel : ignoré
    pages = [
        (1, "EXAMEN BLANC\nNom et Prénoms : ……………\n« Lis le texte ci-dessous et traite les consignes. »\n"
            "Le travail des enfants est interdit par la loi dans tous les pays du monde.\n"
            "I - COMPREHENSION DU TEXTE\n1- Donne une définition du travail des enfants selon le texte."),
        (2, "DICTEE\nDictée : …………………………………………………………………\nÉcris le texte que le maître va te lire."),
        (3, "MATHEMATIQUES\nEXERCICE 1 :\nCalcule 2,98 + 48,571 et pose l'opération.\n"
            "EXERCICE 2 :\nObserve la figure et complète les phrases."),
        (4, "BAREME EPREUVE DE MATHEMATIQUE CM2 50/50\nEXERCICE 1 :\n2,98 + 48,571 = 51,551 (4 pts)\n"
            "EXERCICE 2 :\n(AH) est la hauteur du triangle ABC."),
    ]
    found = [(s.kind, s.subject, s.label) for s in segment(pages, exam=True)]
    assert found == [
        ("exercise", "Français", "Compréhension du texte"),
        ("exercise", "Français", "Dictée"),
        ("exercise", "Mathématiques", "Exercice 1"),
        ("exercise", "Mathématiques", "Exercice 2"),
        ("correction", "Mathématiques", "Exercice 1"),
        ("correction", "Mathématiques", "Exercice 2"),
    ]
    first = segment(pages, exam=True)[0]
    assert first.text.startswith("« Lis le texte") and first.page_start == 1
    # Sans le mode examen, rien ne change pour les manuels.
    assert all(s.subject is None for s in segment(pages))
