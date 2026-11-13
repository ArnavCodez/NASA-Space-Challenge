"""
Pull small pieces of SPHEREx spectral images straight out of the full files
with HTTP range requests.

IRSA's cutout service works, but every cutout carries the full EPSF table
(~4 MB) no matter how small the image is. We only need a few dozen rows of
IMAGE and FLAGS plus the WCS-WAVE table at the end of the file, which comes
to tens of KB per frame. IRSA's server answers multi-range requests, so each
file costs three round trips.
"""
import hashlib
import io
import json
import re
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests
from astropy import log
from astropy.io import fits
from astropy.io.fits.hdu.compressed._codecs import Rice1
from astropy.wcs import WCS, FITSFixedWarning

from . import settings

warnings.simplefilter("ignore", FITSFixedWarning)
log.setLevel("WARNING")

BLOCK = 2880
MAX_RANGES = 120  # apache gives up on multi-range past 200 and sends the whole file
TAIL = 4 * BLOCK

_local = threading.local()
_pool = ThreadPoolExecutor(settings.WORKERS)


def _session() -> requests.Session:
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def _split_parts(body: bytes, headers) -> tuple[list[tuple[int, bytes]], int]:
    ctype = headers.get("Content-Type", "")
    if not ctype.startswith("multipart/byteranges"):
        m = re.match(r"bytes (\d+)-(\d+)/(\d+)", headers["Content-Range"])
        return [(int(m[1]), body)], int(m[3])

    boundary = ctype.split("boundary=")[1].strip('"').encode()
    parts, total = [], 0
    for chunk in body.split(b"--" + boundary):
        head, sep, data = chunk.partition(b"\r\n\r\n")
        m = re.search(rb"Content-Range:\s*bytes (\d+)-(\d+)/(\d+)", head, re.I)
        if not sep or not m:
            continue
        start, end, total = int(m[1]), int(m[2]), int(m[3])
        parts.append((start, data[: end - start + 1]))
    return parts, total


def _get(url: str, spec: list[str]) -> tuple[list[tuple[int, bytes]], int]:
    r = _session().get(url, headers={"Range": "bytes=" + ",".join(spec)}, stream=True, timeout=60)
    with r:
        if r.status_code != 206:
            raise IOError(f"{r.status_code} for range request on {url}")
        body = r.content
    return _split_parts(body, r.headers)


def read_ranges(url: str, ranges: list[tuple[int, int]], extra: list[str] = ()) -> tuple[list[bytes], list, int]:
    """Fetch inclusive byte ranges; `extra` takes raw specs like '-11520' whose parts come back as-is."""
    parts, total = [], 0
    specs = [f"{a}-{b}" for a, b in ranges] + list(extra)
    for i in range(0, len(specs), MAX_RANGES):
        got, total = _get(url, specs[i : i + MAX_RANGES])
        parts += got

    out = []
    for a, b in ranges:
        for start, data in parts:
            if start <= a and b < start + len(data):
                out.append(data[a - start : b - start + 1])
                break
        else:
            raise IOError(f"server skipped range {a}-{b} on {url}")
    return out, parts, total


def _header_at(buf: bytes, offset: int = 0) -> tuple[fits.Header, int] | None:
    end = offset
    while end + BLOCK <= len(buf):
        block = buf[end : end + BLOCK]
        end += BLOCK
        if any(block[i : i + 8] == b"END     " for i in range(0, BLOCK, 80)):
            return fits.Header.fromstring(buf[offset:end].decode("ascii")), end - offset
    return None


def _data_size(h: fits.Header) -> int:
    n = abs(h["BITPIX"]) // 8
    for i in range(1, h["NAXIS"] + 1):
        n *= h[f"NAXIS{i}"]
    n += h.get("PCOUNT", 0)
    return -(-n // BLOCK) * BLOCK


def _rows(offset: int, h: fits.Header, x0: int, x1: int, y0: int, y1: int) -> list[tuple[int, int]]:
    size = abs(h["BITPIX"]) // 8
    width = h["NAXIS1"]
    return [(offset + (y * width + x0) * size, offset + (y * width + x1) * size - 1) for y in range(y0, y1)]


def _unpack(chunks: list[bytes], h: fits.Header, nx: int) -> np.ndarray:
    dtype = {-32: ">f4", -64: ">f8", 32: ">i4", 16: ">i2"}[h["BITPIX"]]
    arr = np.frombuffer(b"".join(chunks), dtype=dtype).reshape(len(chunks), nx)
    arr = arr.astype(np.float32 if h["BITPIX"] < 0 else np.int64)
    if "BZERO" in h or "BSCALE" in h:
        arr = arr * h.get("BSCALE", 1) + h.get("BZERO", 0)
    return arr


def _compressed_rows(url: str, data_at: int, h: fits.Header, y0: int, y1: int) -> np.ndarray:
    # FLAGS is stored tile-compressed (RICE_1), one tile per detector row:
    # read the tile descriptors for our rows, then just those tiles from the heap
    if h.get("ZCMPTYPE") != "RICE_1" or h.get("ZTILE2", 1) != 1:
        raise IOError(f"unexpected FLAGS compression {h.get('ZCMPTYPE')} {h.get('ZTILE2')}")
    (desc,), _, _ = read_ranges(url, [(data_at + y0 * 8, data_at + y1 * 8 - 1)])
    sizes_offsets = np.frombuffer(desc, ">i4").reshape(-1, 2)
    heap = data_at + h.get("THEAP", h["NAXIS1"] * h["NAXIS2"])
    tiles, _, _ = read_ranges(url, [(heap + off, heap + off + n - 1) for n, off in sizes_offsets])

    zvals = {h[f"ZNAME{i}"]: h[f"ZVAL{i}"] for i in range(1, 10) if f"ZNAME{i}" in h}
    width = h["ZNAXIS1"]
    codec = Rice1(blocksize=zvals.get("BLOCKSIZE", 32), bytepix=zvals.get("BYTEPIX", 4), tilesize=width)
    rows = [codec.decode(np.frombuffer(t, np.uint8)) for t in tiles]
    return np.vstack([np.asarray(r).view(f"i{zvals.get('BYTEPIX', 4)}")[:width] for r in rows]).astype(np.int64)


def _wave_table(primary: bytes, tail_parts: list, total: int) -> bytes:
    # the WCS-WAVE extension is the last HDU in the file
    start, tail = next((s, d) for s, d in tail_parts if s + len(d) == total)
    for off in range(0, len(tail), BLOCK):
        if tail[off : off + 9] == b"XTENSION=" and b"WCS-WAVE" in tail[off : off + BLOCK]:
            return primary + tail[off:]
    raise IOError("WCS-WAVE not found in file tail")


def read_cutout(uri: str, ra: float, dec: float, half: int) -> dict:
    """Read a (2*half+1)^2 pixel box of IMAGE and FLAGS centred on (ra, dec)."""
    url = settings.IRSA + uri

    # round 1: primary + IMAGE header from the front, WCS-WAVE from the back
    (front,), parts, total = read_ranges(url, [(0, 12 * BLOCK - 1)], extra=[f"-{TAIL}"])
    primary, plen = _header_at(front)
    hit = _header_at(front, plen)
    if hit is None:
        (front,), _, _ = read_ranges(url, [(0, 40 * BLOCK - 1)])
        hit = _header_at(front, plen)
    img_hdr, ilen = hit
    wave = _wave_table(front[:plen], parts, total)

    ny_full, nx_full = img_hdr["NAXIS2"], img_hdr["NAXIS1"]
    x, y = celestial_wcs(img_hdr).all_world2pix(ra, dec, 0)
    cx, cy = int(round(float(x))), int(round(float(y)))
    x0, x1 = max(cx - half, 0), min(cx + half + 1, nx_full)
    y0, y1 = max(cy - half, 0), min(cy + half + 1, ny_full)
    if x0 >= x1 or y0 >= y1:
        raise ValueError("box falls off the detector")

    img_data = plen + ilen
    flags_hdr_at = img_data + _data_size(img_hdr)

    # round 2: image rows + FLAGS header
    got, _, _ = read_ranges(url, _rows(img_data, img_hdr, x0, x1, y0, y1) + [(flags_hdr_at, flags_hdr_at + 8 * BLOCK - 1)])
    image = _unpack(got[:-1], img_hdr, x1 - x0)
    flags_hdr, flen = _header_at(got[-1])
    flags = _compressed_rows(url, flags_hdr_at + flen, flags_hdr, y0, y1)[:, x0:x1]

    names = {int(k[4:]): flags_hdr[k] for k in flags_hdr if k.startswith("MSKN")}
    return {
        "image": image,
        "flags": flags,
        "x0": x0,
        "y0": y0,
        "header": img_hdr.tostring(),
        "wave": wave,
        "flag_names": names,
    }


def _cache_path(frame: dict, ra: float, dec: float, half: int):
    key = hashlib.sha1(f"{ra:.5f},{dec:.5f},{half}".encode()).hexdigest()[:10]
    return settings.CACHE / "cutouts" / f"{frame['id']}_{key}.npz"


def _save(path, cut: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        tmp,
        image=cut["image"],
        flags=cut["flags"],
        origin=np.array([cut["x0"], cut["y0"]]),
        header=np.frombuffer(cut["header"].encode(), np.uint8),
        wave=np.frombuffer(cut["wave"], np.uint8),
        flag_names=np.frombuffer(json.dumps(cut["flag_names"]).encode(), np.uint8),
    )
    tmp.replace(path)


def _load(path) -> dict:
    with np.load(path) as z:
        return {
            "image": z["image"],
            "flags": z["flags"],
            "x0": int(z["origin"][0]),
            "y0": int(z["origin"][1]),
            "header": z["header"].tobytes().decode(),
            "wave": z["wave"].tobytes(),
            "flag_names": {int(k): v for k, v in json.loads(z["flag_names"].tobytes()).items()},
        }


def celestial_wcs(header: fits.Header | str) -> WCS:
    if isinstance(header, str):
        header = fits.Header.fromstring(header)
    return WCS(header)


def spectral_wcs(cut: dict) -> WCS:
    hdul = fits.open(io.BytesIO(cut["wave"]))
    w = WCS(header=fits.Header.fromstring(cut["header"]), fobj=hdul, key="W")
    w.sip = None  # the W solution is a lookup table; leftover SIP keys confuse astropy
    return w


def fetch(frame: dict, ra: float, dec: float, half: int, tries: int = 3) -> dict:
    path = _cache_path(frame, ra, dec, half)
    if path.exists():
        return _load(path)
    for attempt in range(tries):
        try:
            cut = read_cutout(frame["uri"], ra, dec, half)
            break
        except (IOError, requests.RequestException):
            if attempt == tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    _save(path, cut)
    return cut


def fetch_many(jobs: list[tuple[dict, float, float, int]]) -> list[dict | None]:
    """Run fetch() for each (frame, ra, dec, half). Failures come back as None."""

    def one(job):
        try:
            return fetch(*job)
        except (IOError, ValueError, requests.RequestException):
            return None

    return list(_pool.map(one, jobs))
