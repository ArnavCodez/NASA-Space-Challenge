import hashlib
import json
import logging
import math
import pyvo
from . import settings

log = logging.getLogger(__name__)
ESA_GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap"

def get_gaia_stars(ra: float, dec: float, fov_arcmin: float, limit: int = 200) -> list[dict]:
    # Circle must cover the corners of the square FOV: (sqrt(2)/2) * fov + margin
    radius_deg = (fov_arcmin / 60.0) * (math.sqrt(2) / 2.0) * 1.05
    key = hashlib.sha1(f"gaia_{ra:.4f}_{dec:.4f}_{fov_arcmin}".encode()).hexdigest()[:16] + ".json"

    cache_dir = settings.DEMO_CACHE / "gaia"
    runtime_dir = settings.CACHE / "gaia"
    for d in (cache_dir, runtime_dir):
        path = d / key
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass

    query = f"""
    SELECT TOP {limit} source_id, ra, dec, phot_g_mean_mag, pmra, pmdec
    FROM gaiadr3.gaia_source
    WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.6f}))
      AND phot_g_mean_mag IS NOT NULL
    ORDER BY phot_g_mean_mag ASC
    """

    stars = []
    try:
        tap = pyvo.dal.TAPService(ESA_GAIA_TAP)
        table = tap.search(query).to_table()
        for r in table:
            pmra = float(r["pmra"]) if r["pmra"] is not None and not math.isnan(float(r["pmra"])) else 0.0
            pmdec = float(r["pmdec"]) if r["pmdec"] is not None and not math.isnan(float(r["pmdec"])) else 0.0
            stars.append({
                "id": str(r["source_id"]),
                "ra": float(r["ra"]),
                "dec": float(r["dec"]),
                "mag": round(float(r["phot_g_mean_mag"]), 2),
                "pmra": round(pmra, 2),
                "pmdec": round(pmdec, 2),
            })
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / key).write_text(json.dumps(stars))
    except Exception as e:
        log.warning("Gaia query failed: %s", e)
        return []

    return stars
