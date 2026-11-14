import pytest
from app.gaia import get_gaia_stars
from app.neossat import get_neossat_records

def test_gaia_fetch():
    # querying a small field around Barnard's Star
    stars = get_gaia_stars(269.452, 4.693, 3.0, limit=10)
    assert isinstance(stars, list)
    if stars:
        s = stars[0]
        assert "id" in s
        assert "ra" in s
        assert "dec" in s
        assert "mag" in s

def test_neossat_fetch():
    records = get_neossat_records(133.8189, -7.2470, 6.0, limit=10)
    assert isinstance(records, list)
