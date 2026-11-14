import pytest

from app.coords import parse, propagate, resolve


def test_parse_sexagesimal_from_brief():
    ra, dec = parse("08h55m10.831s -7d14m42.53s")
    assert ra == pytest.approx(133.795129, abs=1e-5)
    assert dec == pytest.approx(-7.245147, abs=1e-5)


@pytest.mark.parametrize("text", [
    "08 55 10.831 -07 14 42.53",
    "08:55:10.831 -07:14:42.53",
    "133.795129, -7.245147",
    " RA 05h 55m 10.3s, Dec +07° 24′ 25″",
    "RA: 05:55:10.3 Dec: +07:24:25",
])
def test_parse_other_formats(text):
    ra, dec = parse(text)
    assert 0 <= ra < 360
    assert -90 <= dec <= 90


def test_parse_rejects_names():
    assert parse("R Dra") is None
    assert parse("Barnard's Star") is None


def test_propagate_barnard():
    # ~4.5 arcmin north in 26 years
    ra, dec = propagate(269.45207696, 4.69336497, -801.551, 10362.394, 26.0)
    assert (dec - 4.69336497) * 60 == pytest.approx(4.49, abs=0.01)
    assert ra < 269.45207696


def test_resolve_preset_alias():
    hit = resolve("barnard")
    assert hit["source"] == "preset"
    assert hit["moved"] > 250
    assert hit["dec"] > hit["dec0"]

    atlas = resolve("3i/atlas")
    assert atlas["source"] == "preset"
    assert atlas["name"] == "Comet 3I/ATLAS"

    ceres = resolve("ceres")
    assert ceres["source"] == "preset"
    assert ceres["name"] == "(1) Ceres"
