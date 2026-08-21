"""RG007 — format ID + unicité + non-réutilisation."""
import re
from datetime import datetime

from app.services.id_generator import generer_code

PATTERN = re.compile(r"^RECB-\d{6}-\d{5}$")


def test_format_id_conforme(db_session):
    code = generer_code(db_session, datetime(2025, 5, 15, 10, 0))
    assert PATTERN.match(code), f"Format invalide: {code}"
    assert code == "RECB-202505-00001"


def test_ids_strictement_croissants(db_session):
    ids = [generer_code(db_session, datetime(2025, 5, 1)) for _ in range(5)]
    numeros = [int(c.split("-")[-1]) for c in ids]
    assert numeros == [1, 2, 3, 4, 5]


def test_compteur_reinitialise_par_mois(db_session):
    c1 = generer_code(db_session, datetime(2025, 5, 31))
    c2 = generer_code(db_session, datetime(2025, 6, 1))
    assert c1.endswith("-00001")
    assert c2.endswith("-00001")
    assert "202505" in c1 and "202506" in c2
