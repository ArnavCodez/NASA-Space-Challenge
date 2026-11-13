import hashlib
import json
import re
import time
from datetime import datetime, timezone

import numpy as np
import pyvo
from astropy.time import Time

from . import settings

QUERY = """
SELECT a.uri, p.energy_bandpassname AS band, p.time_bounds_lower AS t0, p.time_bounds_upper AS t1
FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {ra:.6f}, {dec:.6f}), p.poly)
"""

# level2_2025W19_1B_0116_1D6_spx_l2b-v27-2026-197.fits
FILENAME = re.compile(r"level2_(?P<obs>.+)D(?P<det>\d)_spx_(?P<version>.+)\.fits$")


def frame_id(uri: str) -> str:
    return hashlib.sha1(uri.encode()).hexdigest()[:12]


def release_rank(release: str) -> int:
    return settings.RELEASES.index(release) if release in settings.RELEASES else len(settings.RELEASES)


def parse_rows(rows) -> list[dict]:
    frames = {}
    for uri, band, t0, t1 in rows:
        m = FILENAME.search(uri)
        if not m:
            continue
        release = uri.split("/")[3]
        if release in settings.SKIP_RELEASES:
            continue
        frame = {
            "id": frame_id(uri),
            "obs_id": m["obs"],
            "det": "D" + m["det"],
            "mjd": round((t0 + t1) / 2, 6),
            "release": release,
            "version": m["version"],
            "uri": uri,
        }
        # the same exposure can sit in more than one release (or be reprocessed);
        # keep the preferred release, then the newest processing
        key = (frame["obs_id"], frame["det"])
        old = frames.get(key)
        if old is None or (release_rank(release), old["version"]) < (release_rank(old["release"]), frame["version"]):
            frames[key] = frame
    return sorted(frames.values(), key=lambda f: f["mjd"])


def group_epochs(mjd, gap=30.0, span=60.0) -> np.ndarray:
    # a sky position gets revisited in bursts a few months apart; split on the
    # quiet gaps, and chop long stretches (near the ecliptic poles) into chunks
    mjd = np.asarray(mjd, float)
    labels = np.zeros(len(mjd), int)
    epoch, start, prev = 0, None, None
    for i in np.argsort(mjd):
        t = mjd[i]
        if prev is not None and (t - prev > gap or t - start > span):
            epoch += 1
            start = t
        if start is None:
            start = t
        labels[i] = epoch
        prev = t
    return labels


def summarize_epochs(frames: list[dict]) -> list[dict]:
    epochs = []
    for e in sorted({f["epoch"] for f in frames}):
        members = [f for f in frames if f["epoch"] == e]
        mjd = [f["mjd"] for f in members]
        counts = {}
        for f in members:
            counts[f["det"]] = counts.get(f["det"], 0) + 1
        mid = Time(float(np.median(mjd)), format="mjd").datetime
        epochs.append({
            "id": e,
            "mjd_min": min(mjd),
            "mjd_max": max(mjd),
            "label": mid.strftime("%b %Y"),
            "n": counts,
        })
    return epochs


def query_irsa(ra: float, dec: float) -> list[tuple]:
    tap = pyvo.dal.TAPService(settings.TAP_URL)
    table = tap.search(QUERY.format(ra=ra, dec=dec)).to_table()
    return [(str(r["uri"]), str(r["band"]), float(r["t0"]), float(r["t1"])) for r in table]


def search(ra: float, dec: float, fresh: bool = False) -> dict:
    path = settings.CACHE / "search" / f"{ra:.4f}_{dec:.4f}.json"
    demo = settings.DEMO_CACHE / "search" / path.name
    for p in (path, demo):
        if not fresh and p.exists() and (p == demo or time.time() - p.stat().st_mtime < settings.SEARCH_TTL):
            manifest = json.loads(p.read_text())
            manifest["cached"] = True
            return manifest

    frames = parse_rows(query_irsa(ra, dec))
    for f, e in zip(frames, group_epochs([f["mjd"] for f in frames])):
        f["epoch"] = int(e)

    counts = {}
    for f in frames:
        counts[f["det"]] = counts.get(f["det"], 0) + 1

    manifest = {
        "ra": ra,
        "dec": dec,
        "queried_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frames": frames,
        "epochs": summarize_epochs(frames),
        "counts": dict(sorted(counts.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest))
    manifest["cached"] = False
    return manifest
