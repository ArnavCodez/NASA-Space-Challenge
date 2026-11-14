import hashlib
import json
import logging
import urllib.parse
import urllib.request
import ssl
from . import settings

log = logging.getLogger(__name__)
ESA_GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
SSL_CTX = ssl._create_unverified_context()

def get_gaia_stars(ra: float, dec: float, fov_arcmin: float, limit: int = 150) -> list[dict]:
    radius_deg = (fov_arcmin / 60.0) / 2.0 * 1.15  # slightly larger than FOV
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
    data = urllib.parse.urlencode({
        "REQUEST": "doQuery",
        "LANG": "ADQL",
        "FORMAT": "csv",
        "QUERY": query,
    }).encode()

    req = urllib.request.Request(ESA_GAIA_TAP, data=data, headers={"User-Agent": "SPHEREx-Sky-Viewer/1.0"})
    stars = []
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=12) as res:
            lines = res.read().decode("utf-8", errors="ignore").strip().splitlines()
            if len(lines) > 1:
                headers = [h.strip() for h in lines[0].split(",")]
                for line in lines[1:]:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        try:
                            s_id = parts[headers.index("source_id")]
                            s_ra = float(parts[headers.index("ra")])
                            s_dec = float(parts[headers.index("dec")])
                            mag = float(parts[headers.index("phot_g_mean_mag")])
                            pmra = float(parts[headers.index("pmra")]) if parts[headers.index("pmra")] else 0.0
                            pmdec = float(parts[headers.index("pmdec")]) if parts[headers.index("pmdec")] else 0.0
                            stars.append({
                                "id": str(s_id),
                                "ra": s_ra,
                                "dec": s_dec,
                                "mag": round(mag, 2),
                                "pmra": round(pmra, 2),
                                "pmdec": round(pmdec, 2),
                            })
                        except (ValueError, IndexError):
                            continue
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / key).write_text(json.dumps(stars))
    except Exception as e:
        log.warning("Gaia query failed: %s", e)
        return []

    return stars
