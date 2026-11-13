import math

import numpy as np
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS
from scipy.ndimage import map_coordinates

from . import settings
from .cutouts import celestial_wcs, spectral_wcs

# FLAGS bit names come from the MSKN keywords in each file; group them by what we do with them
BAD = {"SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "PERSIST", "OUTLIER"}
SATURATED = {"OVERFLOW", "NONLINEAR"}
ARTIFACT = {"GHOST", "GHOST_FPA", "GHOST_EXT", "STREAK", "BLOOM", "SNOWBALL", "HALO", "CROSSTALK"}

# bits in the uint8 mask we send to the browser
M_BAD, M_SOURCE, M_ARTIFACT, M_TRANSIENT, M_SATURATED = 1, 2, 4, 8, 16


def _bits(names: dict[int, str], wanted: set[str]) -> int:
    return sum(1 << b for b, n in names.items() if n in wanted)


def display_mask(flags: np.ndarray, names: dict[int, str]) -> np.ndarray:
    mask = np.zeros(flags.shape, np.uint8)
    for bit, group in ((M_BAD, BAD), (M_SATURATED, SATURATED), (M_ARTIFACT, ARTIFACT),
                       (M_SOURCE, {"SOURCE"}), (M_TRANSIENT, {"TRANSIENT"})):
        mask[(flags & _bits(names, group)) != 0] |= bit
    return mask


def make_grid(ra: float, dec: float, fov: int) -> dict:
    scale = settings.FOVS[fov]
    n = int(round(fov * 60 / scale)) | 1  # odd so the target sits on a pixel centre
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-scale / 3600, scale / 3600]  # north up, east left
    yy, xx = np.mgrid[0:n, 0:n]
    sky_ra, sky_dec = w.wcs_pix2world(xx, yy, 0)
    return {"ra": ra, "dec": dec, "fov": fov, "scale": scale, "n": n, "wcs": w, "sky": (sky_ra, sky_dec)}


def cutout_half(fov: int) -> int:
    # enough native pixels to cover the grid at any roll angle
    return math.ceil(fov * 60 / 2 * math.sqrt(2) / settings.PIXEL) + 3


def prepare(cut: dict, grid: dict) -> dict:
    image = cut["image"].astype(np.float64)
    mask = display_mask(cut["flags"], cut["flag_names"])
    image[mask & M_BAD != 0] = np.nan

    clean = np.isfinite(image) & (mask == 0)
    if clean.sum() < 20:
        clean = np.isfinite(image)
    _, bkg, noise = sigma_clipped_stats(image[clean], sigma=3, maxiters=5)
    image -= bkg

    w = celestial_wcs(cut["header"])
    x, y = w.all_world2pix(grid["sky"][0], grid["sky"][1], 0)
    coords = [y - cut["y0"], x - cut["x0"]]
    out = map_coordinates(image, coords, order=1, cval=np.nan)
    out_mask = map_coordinates(mask.astype(float), coords, order=0, cval=0).astype(np.uint8)

    cx, cy = w.all_world2pix(grid["ra"], grid["dec"], 0)
    wave, bw = spectral_wcs(cut).pixel_to_world(cx, cy)

    counts = {}
    for b, name in cut["flag_names"].items():
        k = int(((cut["flags"] >> b) & 1).sum())
        if k:
            counts[name] = k

    return {
        "image": out.astype(np.float32),
        "mask": out_mask,
        "bkg": float(bkg),
        "noise": float(noise),
        "wave": float(wave.to_value("um")),
        "bw": float(bw.to_value("um")),
        "flags": counts,
    }
