import hashlib
import json
import logging
import urllib.parse
import urllib.request
import ssl
from . import settings

log = logging.getLogger(__name__)
CADC_ARGUS_TAP = "https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus/sync"
SSL_CTX = ssl._create_unverified_context()

def get_neossat_records(ra: float, dec: float, fov_arcmin: float, limit: int = 50) -> list[dict]:
    radius_deg = (fov_arcmin / 60.0) / 2.0 * 2.0  # slightly broader search radius for wide-field pointing
    key = hashlib.sha1(f"neossat_{ra:.4f}_{dec:.4f}_{fov_arcmin}".encode()).hexdigest()[:16] + ".json"

    cache_dir = settings.DEMO_CACHE / "neossat"
    runtime_dir = settings.CACHE / "neossat"
    for d in (cache_dir, runtime_dir):
        path = d / key
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass

    query = f"""
    SELECT TOP {limit} obsID, target_name, time_bounds_lower, time_bounds_upper
    FROM caom2.Observation
    WHERE collection = 'NEOSSAT'
      AND 1 = INTERSECTS(CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.6f}), position_bounds)
    """
    data = urllib.parse.urlencode({
        "REQUEST": "doQuery",
        "LANG": "ADQL",
        "FORMAT": "csv",
        "QUERY": query,
    }).encode()

    req = urllib.request.Request(CADC_ARGUS_TAP, data=data, headers={"User-Agent": "SPHEREx-Sky-Viewer/1.0"})
    records = []
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=12) as res:
            lines = res.read().decode("utf-8", errors="ignore").strip().splitlines()
            if len(lines) > 1:
                headers = [h.strip() for h in lines[0].split(",")]
                for line in lines[1:]:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        obs_id = parts[headers.index("obsID")] if "obsID" in headers else parts[0]
                        tgt = parts[headers.index("target_name")] if "target_name" in headers else ""
                        records.append({
                            "obs_id": obs_id,
                            "target": tgt,
                            "cadc_url": f"https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/search/?collection=NEOSSAT&target={urllib.parse.quote(tgt or '')}",
                        })
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / key).write_text(json.dumps(records))
    except Exception as e:
        log.warning("CADC NEOSSat query failed: %s", e)
        return []

    return records
