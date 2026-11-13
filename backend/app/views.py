import hashlib
import json

import numpy as np
from astropy.stats import sigma_clip
from astropy.time import Time
from astropy.visualization import ZScaleInterval

from . import settings, wire
from .cutouts import fetch_many
from .frames import M_ARTIFACT, M_BAD, M_SATURATED, M_SOURCE, M_TRANSIENT, cutout_half, make_grid, prepare
from .search import search

VIEWS = ("raw", "epoch", "diff", "sub")
PER_EPOCH = 40  # frames per epoch that go into a co-add; R Dra has hundreds


def limits(image: np.ndarray) -> tuple[float, float]:
    v = image[np.isfinite(image)]
    if v.size < 10:
        return 0.0, 1.0
    lo, hi = ZScaleInterval().get_limits(v)
    return float(lo), float(hi)


def _date(mjd: float) -> str:
    return Time(mjd, format="mjd").iso[:10]


def _meta(f: dict, p: dict) -> dict:
    return {
        "id": f["id"], "obs_id": f["obs_id"], "release": f["release"],
        "det": f["det"], "epoch": f["epoch"], "mjd": f["mjd"], "date": _date(f["mjd"]),
        "wave": round(p["wave"], 4), "bw": round(p["bw"], 4),
        "bkg": round(p["bkg"], 4), "noise": round(p["noise"], 4),
        "flags": p["flags"], "n_coadd": 1,
    }


def coadd(items: list[tuple[dict, dict]]) -> tuple[np.ndarray, np.ndarray, float]:
    images = np.stack([p["image"] for _, p in items]).astype(np.float64)
    masks = np.stack([p["mask"] for _, p in items])
    images[(masks & M_TRANSIENT) != 0] = np.nan  # cosmic rays, and anything moving fast

    if len(items) >= 4:
        images = sigma_clip(images, sigma=3, axis=0, masked=True).filled(np.nan)

    noise = np.array([max(p["noise"], 1e-6) for _, p in items])
    w = np.where(np.isfinite(images), (1 / noise**2)[:, None, None], 0.0)
    total = w.sum(0)
    out = np.full(total.shape, np.nan)
    ok = total > 0
    out[ok] = np.nansum(images * w, 0)[ok] / total[ok]

    mask = np.zeros(out.shape, np.uint8)
    for bit in (M_SATURATED, M_ARTIFACT, M_SOURCE):
        mask[((masks & bit) != 0).mean(0) > 0.5] |= bit
    mask[~ok] |= M_BAD
    return out.astype(np.float32), mask, float(1 / np.sqrt(np.median(total[ok]))) if ok.any() else 0.0


def thin(frames: list[dict], n: int) -> list[dict]:
    if len(frames) <= n:
        return frames
    return [frames[i] for i in np.linspace(0, len(frames) - 1, n).round().astype(int)]


def _epoch_stacks(items, epochs):
    out = []
    for e in sorted({f["epoch"] for f, _ in items}):
        members = [(f, p) for f, p in items if f["epoch"] == e]
        image, mask, noise = coadd(members)
        waves = [p["wave"] for _, p in members]
        mjd = float(np.mean([f["mjd"] for f, _ in members]))
        label = next((x["label"] for x in epochs if x["id"] == e), _date(mjd))
        out.append((image, mask, {
            "id": f"e{e}", "det": members[0][0]["det"], "epoch": e, "label": label,
            "mjd": round(mjd, 4), "date": _date(mjd),
            "mjd_min": min(f["mjd"] for f, _ in members), "mjd_max": max(f["mjd"] for f, _ in members),
            "wave": round(float(np.median(waves)), 4), "wave_min": round(min(waves), 4), "wave_max": round(max(waves), 4),
            "noise": round(noise, 5), "n_coadd": len(members),
        }))
    return out


def build(view: str, items: list, epochs: list, ref: int = 0):
    if view == "raw":
        return [(p["image"], p["mask"], _meta(f, p)) for f, p in items]

    if view == "sub":
        median = np.nanmedian(np.stack([p["image"] for _, p in items]), axis=0)
        return [(p["image"] - median, p["mask"], _meta(f, p)) for f, p in items]

    stacks = _epoch_stacks(items, epochs)
    if view == "epoch":
        return stacks

    base = next((s for s in stacks if s[2]["epoch"] == ref), stacks[0])
    return [(img - base[0], m | base[1], {**meta, "ref": base[2]["epoch"]}) for img, m, meta in stacks]


def stack(ra: float, dec: float, fov: int, det: str, view: str, ref: int = 0, offset: int = 0, limit: int = 120) -> bytes:
    manifest = search(ra, dec)
    frames = [f for f in manifest["frames"] if f["det"] == det]
    if view in ("raw", "sub"):
        frames = frames[offset : offset + limit]
    else:
        frames = [f for e in sorted({f["epoch"] for f in frames}) for f in thin([x for x in frames if x["epoch"] == e], PER_EPOCH)]

    params = dict(ra=round(ra, 5), dec=round(dec, 5), fov=fov, det=det, view=view, ref=ref, frames=[f["id"] for f in frames])
    key = hashlib.sha1(json.dumps(params).encode()).hexdigest()[:16] + ".spxf"
    for path in (settings.DEMO_CACHE / "stacks" / key, settings.CACHE / "stacks" / key):
        if path.exists():
            return path.read_bytes()

    grid = make_grid(ra, dec, fov)
    half = cutout_half(fov)
    cuts = fetch_many([(f, ra, dec, half) for f in frames])
    items = [(f, prepare(c, grid)) for f, c in zip(frames, cuts) if c is not None]
    failed = len(frames) - len(items)

    out = build(view, items, manifest["epochs"], ref) if items else []
    n = grid["n"]
    images = np.stack([o[0] for o in out]) if out else np.zeros((0, n, n), np.float32)
    masks = np.stack([o[1] for o in out]) if out else np.zeros((0, n, n), np.uint8)
    metas = []
    for img, _, meta in out:
        meta["vmin"], meta["vmax"] = limits(img)
        metas.append(meta)

    body = wire.encode({
        "ra": ra, "dec": dec, "fov": fov, "scale": grid["scale"], "det": det, "view": view,
        "unit": "MJy/sr", "failed": failed, "total": len([f for f in manifest["frames"] if f["det"] == det]),
        "offset": offset, "frames": metas,
    }, images, masks)

    if failed == 0:
        path = settings.CACHE / "stacks" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return body
