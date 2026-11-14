"""
Build the demo cache for the preset targets so the demo never waits on IRSA.

    python scripts/prebake.py              # every preset, default views
    python scripts/prebake.py "r dra" -d D1 D3 -v epoch raw
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import settings  # noqa: E402

settings.SEARCH_CACHE = settings.DEMO_CACHE / "search"
settings.STACK_CACHE = settings.DEMO_CACHE / "stacks"
settings.MEASURE_CACHE = settings.DEMO_CACHE
settings.CACHE = settings.DEMO_CACHE

from app.coords import presets, resolve  # noqa: E402
from app.gaia import get_gaia_stars  # noqa: E402
from app.measure import spectrum  # noqa: E402
from app.neossat import get_neossat_records  # noqa: E402
from app.search import search  # noqa: E402
from app.views import default_ref, stack  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("targets", nargs="*", help="preset names (default: all)")
    p.add_argument("-d", "--det", nargs="*", help="detectors (default: the preset's)")
    p.add_argument("-v", "--views", nargs="*", default=["epoch", "diff", "raw"])
    p.add_argument("-f", "--fov", type=int, help="field of view in arcmin (default: the preset's)")
    p.add_argument("--no-spectrum", action="store_true", help="skip the all-detector spectrum")
    args = p.parse_args()

    names = args.targets or [t["name"] for t in presets()]
    for name in names:
        hit = resolve(name)
        manifest = search(hit["ra"], hit["dec"])
        fov = args.fov or hit.get("fov", 6)
        for det in args.det or [hit.get("det", "D3")]:
            for view in args.views:
                t0 = time.time()
                body = stack(hit["ra"], hit["dec"], fov, det, view, ref=default_ref(manifest, det))
                print(f"{hit['name']:16} {det} {view:5} fov={fov}  {len(body) / 1e3:7.0f} KB  {time.time() - t0:5.0f}s"
                      f"  ({len(manifest['frames'])} frames total)", flush=True)
        try:
            g_stars = get_gaia_stars(hit["ra"], hit["dec"], fov)
            print(f"{hit['name']:16} Gaia: {len(g_stars)} stars cached", flush=True)
        except Exception as e:
            print(f"{hit['name']:16} Gaia prebake skipped: {e}", flush=True)
        try:
            n_records = get_neossat_records(hit["ra"], hit["dec"], fov)
            print(f"{hit['name']:16} NEOSSat: {len(n_records)} records cached", flush=True)
        except Exception as e:
            print(f"{hit['name']:16} NEOSSat prebake skipped: {e}", flush=True)
        if not args.no_spectrum:
            t0 = time.time()
            spec = spectrum(hit["ra"], hit["dec"], hit.get("pmra") or 0, hit.get("pmdec") or 0)
            print(f"{hit['name']:16} spectrum  {len(spec['points'])} points from {spec['total']} exposures"
                  f"  {time.time() - t0:5.0f}s", flush=True)


if __name__ == "__main__":
    main()
