"""Forced photometry across every detector (a spectrum per visit) and per-epoch positions."""
import hashlib
import json
import warnings

import numpy as np
from astropy.stats import sigma_clipped_stats
from scipy.ndimage import label
from scipy.optimize import OptimizeWarning, curve_fit

from . import settings, views, wire
from .coords import propagate
from .cutouts import celestial_wcs, fetch_many, spectral_wcs
from .frames import M_ARTIFACT, M_BAD, M_SATURATED, M_SOURCE, display_mask
from .search import search

APERTURE = 2.0  # native pixels
ANNULUS = (4.0, 7.0)
HALF = 10
MAX_FRAMES = 360
MJY = 1e9 * (settings.PIXEL / 206264.806) ** 2  # mJy in one pixel at 1 MJy/sr
VERSION = 2


def years_since(mjd: float, epoch: float = settings.EPOCH) -> float:
    return 2000 + (mjd - 51544.5) / 365.25 - epoch


def _aperture(shape, x, y, r, sub=5):
    # fraction of each pixel inside the circle, by supersampling
    yy, xx = np.indices(shape, dtype=float)
    w = np.zeros(shape)
    for dy in (np.arange(sub) + 0.5) / sub - 0.5:
        for dx in (np.arange(sub) + 0.5) / sub - 0.5:
            w += np.hypot(xx + dx - x, yy + dy - y) <= r
    return w / sub**2


def photometry(cut: dict, ra: float, dec: float) -> dict | None:
    image = cut["image"].astype(np.float64)
    mask = display_mask(cut["flags"], cut["flag_names"])
    image[mask & M_BAD != 0] = np.nan

    fx, fy = celestial_wcs(cut["header"]).all_world2pix(ra, dec, 0)
    x, y = float(fx) - cut["x0"], float(fy) - cut["y0"]
    ny, nx = image.shape
    edge = ANNULUS[1] - 1
    if not (edge <= x <= nx - 1 - edge and edge <= y <= ny - 1 - edge):
        return None

    yy, xx = np.indices(image.shape)
    r = np.hypot(xx - x, yy - y)
    ring = (r >= ANNULUS[0]) & (r <= ANNULUS[1]) & np.isfinite(image)
    quiet = ring & (mask & (M_SOURCE | M_ARTIFACT | M_SATURATED) == 0)
    if quiet.sum() >= 15:
        ring = quiet
    if ring.sum() < 8:
        return None
    _, bkg, sigma = sigma_clipped_stats(image[ring], sigma=3, maxiters=5)

    w = _aperture(image.shape, x, y, APERTURE)
    inside = w > 0
    good = inside & np.isfinite(image)
    area = w[inside].sum()
    covered = w[good].sum() / area
    if covered < 0.7:
        return None

    flux = ((image - bkg) * w)[good].sum() / covered
    err = sigma * np.sqrt(area + area**2 / ring.sum())
    hit = int(np.bitwise_or.reduce(mask[inside]))
    wave, bw = spectral_wcs(cut).pixel_to_world(fx, fy)
    return {
        "flux": round(float(flux * MJY), 5),
        "err": round(float(err * MJY), 5),
        "wave": round(float(wave.to_value("um")), 4),
        "bw": round(float(bw.to_value("um")), 4),
        "flags": [name for name, on in (("saturated", hit & M_SATURATED), ("artifact", hit & M_ARTIFACT),
                                        ("partial", covered < 0.999)) if on],
    }


def _pick(frames: list[dict]) -> list[dict]:
    # R Dra has ~2500 exposures; keep an even spread across detectors and visits
    groups: dict[tuple, list] = {}
    for f in frames:
        groups.setdefault((f["det"], f["epoch"]), []).append(f)
    per = max(3, MAX_FRAMES // max(len(groups), 1))
    return [f for k in sorted(groups) for f in views.thin(groups[k], per)]


def _cached(name: str, key: dict):
    digest = hashlib.sha1(json.dumps(key).encode()).hexdigest()[:16] + ".json"
    for path in (settings.DEMO_CACHE / name / digest, settings.MEASURE_CACHE / name / digest):
        if path.exists():
            return json.loads(path.read_text()), path
    return None, settings.MEASURE_CACHE / name / digest


def spectrum(ra: float, dec: float, pmra: float = 0.0, pmdec: float = 0.0, cached_only: bool = False) -> dict | None:
    manifest = search(ra, dec)
    frames = _pick(manifest["frames"])
    key = dict(v=VERSION, ra=round(ra, 5), dec=round(dec, 5), pmra=round(pmra), pmdec=round(pmdec),
               frames=[f["id"] for f in frames])
    hit, path = _cached("spectra", key)
    if hit or cached_only:
        return hit

    cuts = fetch_many([(f, ra, dec, HALF) for f in frames])
    points = []
    for f, cut in zip(frames, cuts):
        if cut is None:
            continue
        at = propagate(ra, dec, pmra, pmdec, years_since(f["mjd"]))
        p = photometry(cut, *at)
        if p:
            points.append({"id": f["id"], "det": f["det"], "epoch": f["epoch"], "mjd": round(f["mjd"], 5), **p})

    failed = sum(c is None for c in cuts)
    out = {
        "ra": ra, "dec": dec, "unit": "mJy", "aperture": round(APERTURE * settings.PIXEL, 1),
        "epochs": manifest["epochs"], "total": len(frames), "failed": failed,
        "points": sorted(points, key=lambda p: p["wave"]),
    }
    if not failed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out))
    return out


def _gauss(xy, amp, x0, y0, s, c):
    x, y = xy
    return amp * np.exp(-((x - x0) ** 2 + (y - y0) ** 2) / (2 * s**2)) + c


def centroid(image: np.ndarray, x: float, y: float, reach: float, width: float):
    """Fit a round gaussian to the brightest blob within `reach` px of (x, y)."""
    ny, nx = image.shape
    yy, xx = np.indices(image.shape)
    near = (np.hypot(xx - x, yy - y) <= reach) & np.isfinite(image)
    if not near.any():
        return None
    py, px = np.unravel_index(np.nanargmax(np.where(near, image, -np.inf)), image.shape)

    b = int(np.ceil(2 * width))
    y0, y1, x0, x1 = max(py - b, 0), min(py + b + 1, ny), max(px - b, 0), min(px + b + 1, nx)
    box = image[y0:y1, x0:x1]
    by, bx = np.indices(box.shape)
    ok = np.isfinite(box)
    if ok.sum() < 12:
        return None

    floor = float(np.nanmedian(box))
    guess = [float(np.nanmax(box)) - floor, px - x0, py - y0, width, floor]
    bounds = ([0, 0, 0, 0.3 * width, -np.inf], [np.inf, box.shape[1] - 1, box.shape[0] - 1, 4 * width, np.inf])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)
            p, cov = curve_fit(_gauss, (bx[ok], by[ok]), box[ok], p0=guess, bounds=bounds, maxfev=4000)
    except (RuntimeError, ValueError):
        return None
    err = np.sqrt(np.clip(np.diag(cov), 0, None))
    if not np.all(np.isfinite(err[1:3])):
        return None
    return p[1] + x0, p[2] + y0, err[1], err[2], p[0]


def saturated_core(image: np.ndarray, x: float, y: float, reach: float):
    """Centre of the blanked-out core of a saturated star, if there is one near (x, y)."""
    holes, n = label(~np.isfinite(image))
    if not n:
        return None
    yy, xx = np.indices(image.shape)
    best = None
    for i in range(1, n + 1):
        sel = holes == i
        if sel.sum() < 4:
            continue
        cx, cy = xx[sel].mean(), yy[sel].mean()
        d = np.hypot(cx - x, cy - y)
        if d <= reach and (best is None or d < best[0]):
            best = (d, cx, cy, sel.sum())
    if best is None:
        return None
    _, cx, cy, size = best
    err = 0.5 / np.sqrt(size) + 0.15  # in output pixels; a hole edge is only good to about a pixel
    return cx, cy, err, err, np.nan


def _line(t, v, e):
    # weighted straight-line fit, slope and its error
    w = 1 / np.maximum(e, 1e-3) ** 2
    A = np.vstack([t, np.ones_like(t)]).T
    cov = np.linalg.inv(A.T @ (A * w[:, None]))
    slope, _ = cov @ (A.T @ (w * v))
    return float(slope), float(np.sqrt(cov[0, 0]))


def motion(ra: float, dec: float, det: str, fov: int, pmra: float = 0.0, pmdec: float = 0.0) -> dict:
    meta, images, _ = wire.decode(views.stack(ra, dec, fov, det, "epoch"))
    scale = meta["scale"]
    c = (meta["nx"] - 1) / 2
    width = settings.PIXEL / scale  # psf sigma is roughly one native pixel

    rows = []
    for img, f in zip(images, meta["frames"]):
        dt = years_since(f["mjd"])
        exp_e, exp_n = pmra / 1000 * dt, pmdec / 1000 * dt
        x, y = c - exp_e / scale, c + exp_n / scale
        img = img.astype(np.float64)
        row = {"epoch": f["epoch"], "label": f["label"], "mjd": f["mjd"], "n_coadd": f["n_coadd"],
               "wave": f["wave"], "expected": [round(exp_e, 3), round(exp_n, 3)]}
        found, how = saturated_core(img, x, y, 3 * width), "core"
        if not found:
            found, how = centroid(img, x, y, 2 * width, width), "fit"
        if found:
            fx, fy, ex, ey, _ = found
            floor = 0.1 * settings.PIXEL  # stacking and resampling won't do better than this
            row.update(east=round(-(fx - c) * scale, 3), north=round((fy - c) * scale, 3), method=how,
                       err=[round(float(np.hypot(ex * scale, floor)), 3), round(float(np.hypot(ey * scale, floor)), 3)])
        rows.append(row)

    fit = None
    got = [r for r in rows if "east" in r]
    if len(got) >= 2:
        t = np.array([years_since(r["mjd"], 2000) for r in got])
        pe, pe_err = _line(t, np.array([r["east"] for r in got]), np.array([r["err"][0] for r in got]))
        pn, pn_err = _line(t, np.array([r["north"] for r in got]), np.array([r["err"][1] for r in got]))
        fit = {"pmra": round(pe * 1000), "pmdec": round(pn * 1000),
               "pmra_err": round(pe_err * 1000), "pmdec_err": round(pn_err * 1000),
               "span": round(float(t.max() - t.min()), 2)}

    return {"det": det, "fov": fov, "scale": scale, "catalog": {"pmra": pmra, "pmdec": pmdec},
            "epochs": rows, "fit": fit}
