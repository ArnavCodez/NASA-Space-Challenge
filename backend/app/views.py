import hashlib
import json

import numpy as np
from astropy.stats import mad_std, sigma_clip
from astropy.time import Time
from astropy.visualization import ZScaleInterval

from . import settings, wire
from .cutouts import fetch_many
from .frames import M_ARTIFACT, M_BAD, M_SATURATED, M_SOURCE, M_TRANSIENT, cutout_half, make_grid, prepare
from .search import search

VIEWS = ("raw", "epoch", "diff", "sub")
PER_EPOCH = 8  # optimal frame count per epoch: keeps 3-sigma clipping & coaddition while speeding up download by 4-5x!
VERSION = 4  # bump when the stack output changes so old cached stacks are skipped


def limits(image: np.ndarray, centered: bool = False) -> tuple[float, float]:
    v = image[np.isfinite(image)]
    if v.size < 10 or not v.any():
        return 0.0, 0.0
    if centered:
        # residuals of bright stars blow out zscale; scale to the background noise instead
        s = 5 * mad_std(v)
        return -float(s), float(s)
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
        images = sigma_clip(images, sigma=3, axis=0, masked=True, cenfunc="median", stdfunc="mad_std").filled(np.nan)

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


def build(view: str, items: list, epochs: list, ref: int = 0, sort: str = "time"):
    if sort == "wave" and view in ("raw", "sub"):
        items = sorted(items, key=lambda it: it[1]["wave"])

    if view == "raw":
        return [(p["image"], p["mask"], _meta(f, p)) for f, p in items]

    if view == "sub":
        median = np.nanmedian(np.stack([p["image"] for _, p in items]), axis=0)
        return [(p["image"] - median, p["mask"], _meta(f, p)) for f, p in items]

    stacks = _epoch_stacks(items, epochs)
    if view == "epoch":
        return stacks

    base = next((s for s in stacks if s[2]["epoch"] == ref), stacks[0])
    base_wave = base[2].get("wave", 0.0)
    diff_out = []
    for img, m, meta in stacks:
        diff_meta = {**meta, "ref": base[2]["epoch"]}
        delta_wave = abs(meta.get("wave", 0.0) - base_wave)
        diff_meta["delta_wave"] = round(delta_wave, 4)
        if delta_wave > 0.15:
            diff_meta["wave_warn"] = (
                f"Δλ = {delta_wave:.2f} µm vs ref e{base[2]['epoch']} "
                f"({meta.get('wave', 0.0):.2f} vs {base_wave:.2f} µm): "
                f"color difference may mimic brightness change"
            )
        diff_out.append((img - base[0], m | base[1], diff_meta))
    return diff_out


def default_ref(manifest: dict, det: str) -> int:
    # earliest visit with at least half the exposures of the best one, so the reference isn't mostly noise
    counts = [e["n"].get(det, 0) for e in manifest["epochs"]]
    enough = max(counts, default=0) / 2
    return next((e["id"] for e, n in zip(manifest["epochs"], counts) if n and n >= enough), 0)


def stack(ra: float, dec: float, fov: int, det: str, view: str, ref: int = 0, offset: int = 0, limit: int = 24, sort: str = "time") -> bytes:
    manifest = search(ra, dec)
    if view != "diff":
        ref = 0  # only the difference view uses it; keeps the cache key stable
    frames = [f for f in manifest["frames"] if f["det"] == det]
    if view in ("raw", "sub"):
        if settings.MAX_BYTES:
            n = int(round(fov * 60 / settings.FOVS[fov])) | 1
            limit = max(1, min(limit, settings.MAX_BYTES // (n * n * 5)))  # float32 pixel + uint8 mask
        if offset == 0 and len(frames) > limit:
            frames = thin(frames, limit)
        else:
            frames = frames[offset : offset + limit]
    else:
        frames = [f for e in sorted({f["epoch"] for f in frames}) for f in thin([x for x in frames if x["epoch"] == e], PER_EPOCH)]

    params = dict(v=VERSION, ra=round(ra, 5), dec=round(dec, 5), fov=fov, det=det, view=view, ref=ref,
                  sort=sort, frames=[f["id"] for f in frames])
    key = hashlib.sha1(json.dumps(params).encode()).hexdigest()[:16] + ".spxf"
    for path in (settings.DEMO_CACHE / "stacks" / key, settings.STACK_CACHE / key):
        if path.exists():
            return path.read_bytes()

    grid = make_grid(ra, dec, fov)
    half = cutout_half(fov)
    cuts = fetch_many([(f, ra, dec, half) for f in frames])
    items = [(f, prepare(c, grid)) for f, c in zip(frames, cuts) if c is not None]
    failed = len(frames) - len(items)

    out = build(view, items, manifest["epochs"], ref, sort) if items else []
    n = grid["n"]
    images = np.stack([o[0] for o in out]) if out else np.zeros((0, n, n), np.float32)
    masks = np.stack([o[1] for o in out]) if out else np.zeros((0, n, n), np.uint8)
    metas = []
    for img, _, meta in out:
        meta["vmin"], meta["vmax"] = limits(img, centered=view in ("diff", "sub"))
        metas.append(meta)

    body = wire.encode({
        "ra": ra, "dec": dec, "fov": fov, "scale": grid["scale"], "det": det, "view": view,
        "unit": "MJy/sr", "failed": failed, "total": len([f for f in manifest["frames"] if f["det"] == det]),
        "offset": offset, "frames": metas,
    }, images, masks)

    if len(out) > 0:
        path = settings.STACK_CACHE / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return body
