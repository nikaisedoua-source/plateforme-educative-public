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


def test_importer_never_creates_series_outside_the_programme():
    """« 2nde G… » (début d'un mot) n'est pas une série : la 2nde n'a que A et C."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.database import Base
    from app.importer import Referentials
    from app.models import Grade, Track

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seconde = Grade(code="2NDE", name="2nde", sort_order=10)
        terminale = Grade(code="TLE", name="Tle", sort_order=12)
        db.add_all([seconde, terminale])
        db.flush()
        refs = Referentials(db, create=True)
        assert refs.track(seconde, "G") is None
        assert refs.track(seconde, "D") is None
        assert refs.track(seconde, "C").code == "2NDE-C"
        assert refs.track(terminale, "A1").code == "TLE-A1"
        assert {t.code for t in db.query(Track)} == {"2NDE-C", "TLE-A1"}
