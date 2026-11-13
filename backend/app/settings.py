import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
CACHE = Path(os.environ.get("BLINK_CACHE", ROOT / "cache"))
DEMO_CACHE = ROOT / "demo_cache"
STATIC = Path(os.environ.get("BLINK_STATIC", ROOT / "frontend" / "dist"))

# search results and finished stacks are small; prebake points these at demo_cache
SEARCH_CACHE = CACHE / "search"
STACK_CACHE = CACHE / "stacks"
CUTOUT_CACHE = CACHE / "cutouts"
MEASURE_CACHE = CACHE  # spectra/ lives under here

IRSA = "https://irsa.ipac.caltech.edu/"
TAP_URL = IRSA + "TAP"

# preferred first when the same exposure shows up in more than one release;
# releases not listed here (a future dr2, qr4...) are still used, just ranked last
RELEASES = os.environ.get("SPHEREX_RELEASES", "dr1,qr3").split(",")
SKIP_RELEASES = {"qr2"}

PIXEL = 6.15  # arcsec
EPOCH = 2026.0  # moving targets get centred on where they were at this date

WORKERS = int(os.environ.get("BLINK_WORKERS", 12))
SEARCH_TTL = 24 * 3600

DETECTORS = {
    "D1": (0.75, 1.09),
    "D2": (1.10, 1.62),
    "D3": (1.63, 2.41),
    "D4": (2.42, 3.82),
    "D5": (3.83, 4.41),
    "D6": (4.42, 5.00),
}

# output scale per field of view (arcmin); small fields get 2x oversampling
FOVS = {3: PIXEL / 2, 6: PIXEL / 2, 12: PIXEL, 20: PIXEL}
