import re
import xml.etree.ElementTree as ET
from functools import lru_cache

import numpy as np
import requests
import yaml
import astropy.units as u
from astropy.coordinates import SkyCoord

from . import settings

SESAME = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?{}"


class NotFound(Exception):
    pass


@lru_cache
def presets() -> list[dict]:
    with open(settings.CONFIG / "targets.yaml") as f:
        return yaml.safe_load(f)


def parse(text: str) -> tuple[float, float] | None:
    parts = text.replace(",", " ").split()
    if len(parts) < 2:
        return None
    try:
        if len(parts) == 2 and all(re.fullmatch(r"[+-]?\d+(\.\d*)?", p) for p in parts):
            c = SkyCoord(float(parts[0]), float(parts[1]), unit="deg")
        else:
            c = SkyCoord(" ".join(parts), unit=(u.hourangle, u.deg))
    except ValueError:
        return None
    return float(c.ra.deg), float(c.dec.deg)


def propagate(ra, dec, pmra, pmdec, years):
    # linear is plenty over a few decades, and parallax is under a tenth of a pixel
    dec2 = dec + pmdec * years / 3.6e6
    ra2 = ra + pmra * years / 3.6e6 / np.cos(np.radians((dec + dec2) / 2))
    return float(ra2 % 360), float(dec2)


def sesame(name: str) -> dict:
    r = requests.get(SESAME.format(requests.utils.quote(name)), timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    hit = root.find(".//Resolver[jradeg]")
    if hit is None:
        raise NotFound(name)

    def num(path):
        el = hit.find(path)
        return float(el.text) if el is not None and el.text else 0.0

    oname = hit.findtext("oname") or name
    return {
        "name": re.sub(r"^(NAME|V\*|\*)\s+", "", oname),
        "ra": num("jradeg"),
        "dec": num("jdedeg"),
        "pmra": num("pm/pmRA"),
        "pmdec": num("pm/pmDE"),
        "plx": num("plx/v"),
        "source": "sesame",
    }


def resolve(text: str, epoch: float = settings.EPOCH) -> dict:
    text = text.strip()
    key = text.lower().replace("'", "")

    hit = None
    for p in presets():
        names = [p["name"].lower().replace("'", "")] + p.get("aliases", [])
        if key in names:
            hit = {**p, "source": "preset"}
            break

    if hit is None:
        pos = parse(text)
        if pos:
            return {"name": text, "ra": pos[0], "dec": pos[1], "ra0": pos[0], "dec0": pos[1],
                    "pmra": 0.0, "pmdec": 0.0, "plx": 0.0, "moved": 0.0, "source": "coords"}
        hit = sesame(text)

    ra, dec = propagate(hit["ra"], hit["dec"], hit["pmra"], hit["pmdec"], epoch - 2000.0)
    moved = float(np.hypot(hit["pmra"], hit["pmdec"]) * (epoch - 2000.0) / 1000)
    return {
        "name": hit["name"],
        "ra": ra,
        "dec": dec,
        "ra0": hit["ra"],
        "dec0": hit["dec"],
        "pmra": hit["pmra"],
        "pmdec": hit["pmdec"],
        "plx": hit.get("plx", 0.0),
        "moved": moved,
        "epoch": epoch,
        "source": hit["source"],
        **{k: hit[k] for k in ("det", "fov", "note") if k in hit},
    }
