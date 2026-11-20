"""Séries lues dans les noms de fichiers (usages ivoiriens) ; la 2nde n'a jamais de série E par erreur de lecture."""

import unicodedata

import pytest

from app.extraction import crop_png, identify_series


@pytest.mark.parametrize("name, expected", [
    ("Corrigé CIAM 2NDE S.pdf", ["C"]),          # « 2NDE » n'est pas « 2ND » + E
    ("Maths 2NDC.pdf", ["C"]),
    ("CIAM Mathématiques TSM-1-1.pdf", ["C", "E"]),
    ("CIAM Corrigé Tle SE.pdf", ["D"]),
    ("Ciam 1ère SE guide.pdf", ["D"]),
    (unicodedata.normalize("NFD", "CIAM 1ère AB.pdf"), ["A", "B"]),  # nom de fichier macOS
    ("Terminale C,E.pdf", ["C", "E"]),
])
def test_series_from_filename(name, expected):
    assert identify_series("", name) == expected


def test_crop_accepts_inverted_box():
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buffer, "PNG")
    assert crop_png(buffer.getvalue(), (0.8, 0.2, 0.3, 0.1))


def test_grade_read_when_glued_by_underscore():
    from app.extraction import identify

    result = identify("", "vallesse habilete_1ere C&D.pdf")
    assert result["grade"] == "1ère" and result["series"] == ["C", "D"]
