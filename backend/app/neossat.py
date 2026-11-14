import hashlib
import json
import logging
import math
import numpy as np
import pyvo
from . import settings

log = logging.getLogger(__name__)
CADC_ARGUS_TAP = "https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus"

def get_neossat_records(ra: float, dec: float, fov_arcmin: float, limit: int = 50) -> list[dict]:
    radius_deg = (fov_arcmin / 60.0) * (math.sqrt(2) / 2.0) * 1.5
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
    SELECT TOP {limit} o.obsID, o.target_name, p.time_bounds_lower, p.time_bounds_upper
    FROM caom2.Observation AS o JOIN caom2.Plane AS p ON o.obsID = p.obsID
    WHERE o.collection = 'NEOSSAT'
      AND 1 = INTERSECTS(CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.6f}), p.position_bounds)
    """

    records = []
    try:
        tap = pyvo.dal.TAPService(CADC_ARGUS_TAP)
        table = tap.search(query).to_table()
        for r in table:
            obs_id = str(r["obsID"])
            tgt = str(r["target_name"]) if r["target_name"] is not None and r["target_name"] is not np.ma.masked else ""
            t0_raw = r["time_bounds_lower"]
            t1_raw = r["time_bounds_upper"]
            t0 = float(t0_raw) if t0_raw is not None and t0_raw is not np.ma.masked and not math.isnan(float(t0_raw)) else None
            t1 = float(t1_raw) if t1_raw is not None and t1_raw is not np.ma.masked and not math.isnan(float(t1_raw)) else None
            records.append({
                "obs_id": obs_id,
                "target": tgt,
                "mjd_min": t0,
                "mjd_max": t1,
                "cadc_url": f"https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/search/?collection=NEOSSAT&target={tgt}",
            })
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / key).write_text(json.dumps(records))
    except Exception as e:
        log.warning("CADC NEOSSat query failed: %s", e)
        return []

    return records
