import pyvo
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import coords, gaia, measure, neossat, settings, views
from .search import search

app = FastAPI(title="SPHEREx Blink")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

UPSTREAM_ERRORS = (requests.RequestException, pyvo.dal.DALServiceError, pyvo.dal.DALQueryError, IOError)


def _pos(ra: float, dec: float) -> tuple[float, float]:
    if not (-90 <= dec <= 90):
        raise HTTPException(400, "dec must be between -90 and 90")
    return round(ra % 360, 5), round(dec, 5)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def config():
    return {
        "detectors": settings.DETECTORS,
        "fovs": list(settings.FOVS),
        "views": list(views.VIEWS),
        "releases": settings.RELEASES,
        "epoch": settings.EPOCH,
    }


@app.get("/api/targets")
def targets():
    return [coords.resolve(p["name"]) for p in coords.presets()]


@app.get("/api/resolve")
def resolve(q: str = Query(min_length=1, max_length=120)):
    try:
        return coords.resolve(q)
    except coords.NotFound:
        raise HTTPException(404, f"couldn't find anything called '{q}'")
    except requests.RequestException:
        raise HTTPException(502, "name lookup (CDS Sesame) is unreachable; try coordinates instead")


@app.get("/api/search")
def search_frames(ra: float, dec: float, fresh: bool = False):
    ra, dec = _pos(ra, dec)
    try:
        return search(ra, dec, fresh)
    except UPSTREAM_ERRORS as e:
        raise HTTPException(502, f"IRSA search failed: {e}")


@app.get("/api/frames")
def frames(
    ra: float,
    dec: float,
    det: str = "D3",
    view: str = "epoch",
    fov: int = 6,
    ref: int = 0,
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=200),
    sort: str = Query("time", pattern="^(time|wave)$"),
):
    ra, dec = _pos(ra, dec)
    if det not in settings.DETECTORS:
        raise HTTPException(400, f"det must be one of {', '.join(settings.DETECTORS)}")
    if view not in views.VIEWS:
        raise HTTPException(400, f"view must be one of {', '.join(views.VIEWS)}")
    if fov not in settings.FOVS:
        raise HTTPException(400, f"fov must be one of {list(settings.FOVS)}")
    try:
        body = views.stack(ra, dec, fov, det, view, ref, offset, limit, sort)
    except UPSTREAM_ERRORS as e:
        raise HTTPException(502, f"IRSA request failed: {e}")
    return Response(body, media_type="application/octet-stream")


@app.get("/api/gaia")
def gaia_stars(ra: float, dec: float, fov: float = 6.0):
    ra, dec = _pos(ra, dec)
    return gaia.get_gaia_stars(ra, dec, fov)


@app.get("/api/neossat")
def neossat_records(ra: float, dec: float, fov: float = 6.0):
    ra, dec = _pos(ra, dec)
    return neossat.get_neossat_records(ra, dec, fov)


@app.get("/api/spectrum")
def spectrum(ra: float, dec: float, pmra: float = 0.0, pmdec: float = 0.0, cached: bool = False):
    ra, dec = _pos(ra, dec)
    try:
        out = measure.spectrum(ra, dec, pmra, pmdec, cached_only=cached)
    except UPSTREAM_ERRORS as e:
        raise HTTPException(502, f"IRSA request failed: {e}")
    if out is None:
        return Response(status_code=204)
    return out


@app.get("/api/motion")
def motion(ra: float, dec: float, det: str = "D3", fov: int = 6, pmra: float = 0.0, pmdec: float = 0.0):
    ra, dec = _pos(ra, dec)
    if det not in settings.DETECTORS or fov not in settings.FOVS:
        raise HTTPException(400, "unknown detector or field of view")
    try:
        return measure.motion(ra, dec, det, fov, pmra, pmdec)
    except UPSTREAM_ERRORS as e:
        raise HTTPException(502, f"IRSA request failed: {e}")


# the built frontend, when there is one; in dev vite serves it and proxies /api here
if (settings.STATIC / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=settings.STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def page(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "no such endpoint")
        file = (settings.STATIC / path).resolve()
        if path and file.is_file() and settings.STATIC.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(settings.STATIC / "index.html")
