from unittest.mock import MagicMock, patch
from astropy.table import Table

from app.gaia import get_gaia_stars
from app.neossat import get_neossat_records


def test_gaia_fetch_mocked():
    fake_table = Table({
        "source_id": ["123456789"],
        "ra": [12.3456],
        "dec": [-45.6789],
        "phot_g_mean_mag": [9.54],
        "pmra": [-798.5],
        "pmdec": [10328.2],
    })

    mock_service = MagicMock()
    mock_service.search.return_value.to_table.return_value = fake_table

    with patch("pyvo.dal.TAPService", return_value=mock_service):
        stars = get_gaia_stars(12.3456, -45.6789, 3.0, limit=10)
        assert isinstance(stars, list)
        assert len(stars) == 1
        s = stars[0]
        assert s["id"] == "123456789"
        assert s["ra"] == 12.3456
        assert s["dec"] == -45.6789
        assert s["mag"] == 9.54
        assert s["pmra"] == -798.5
        assert s["pmdec"] == 10328.2


def test_gaia_fetch_error_handling():
    with patch("pyvo.dal.TAPService", side_effect=RuntimeError("Network timeout")):
        stars = get_gaia_stars(99.0, 99.0, 3.0, limit=10)
        assert isinstance(stars, list)


def test_neossat_fetch_mocked():
    fake_table = Table({
        "obsID": ["NEOS_OBS_001"],
        "target_name": ["2024_YR4"],
        "time_bounds_lower": [59000.1],
        "time_bounds_upper": [59000.2],
    })

    mock_service = MagicMock()
    mock_service.search.return_value.to_table.return_value = fake_table

    with patch("pyvo.dal.TAPService", return_value=mock_service):
        records = get_neossat_records(11.2233, -44.5566, 6.0, limit=10)
        assert isinstance(records, list)
        assert len(records) == 1
        r = records[0]
        assert r["obs_id"] == "NEOS_OBS_001"
        assert r["target"] == "2024_YR4"
        assert r["mjd_min"] == 59000.1
        assert "cadc_url" in r
