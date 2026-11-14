# SPHEREx Blink

Type a star name or coordinates and flip through every image NASA's SPHEREx
telescope has taken of that spot, like a short video. Anything that moves or
changes brightness between visits jumps out.

Built at NASA Space Apps 2026 for the **Planet X and SPHEREx** challenge by
team Skill-Issue (Delhi).

## What it does

- **Search** by name (resolved through CDS Sesame) or by RA/Dec in decimal or
  sexagesimal. Fast movers like Barnard's Star are centred on where they are
  in 2026, not where catalogues list them for 2000.
- **Four views** of the same patch:
  - *Epochs*: one stacked image per visit. SPHEREx comes back to each part of
    the sky about every six months, so this is the view for slow movers and
    brightness changes.
  - *Difference*: each visit minus a reference visit. A moving object shows
    up as a dark/light pair.
  - *Frames*: every single exposure in time order or sorted by wavelength.
  - *Static removed*: single exposures minus the median sky.
- **Sort by Observation Date or Wavelength (LVF)**: In raw frames mode, toggle between
  chronological order (to spot movement) and wavelength order (to inspect spectral color transitions).
- **Gaia DR3 Star Overlay**: Overlay known stars from ESA Gaia DR3 so true solar system movers
  and unknown transients stand out against background stars.
- **CSA NEOSSat Cross-Matching**: Detects overlapping asteroid/comet tracking data from the
  Canadian Space Agency's NEOSSat space telescope via CADC Argus TAP.
- **Blink Comparator & Pan/Zoom**: A/B toggle between frames (Clyde Tombaugh mode), keyboard
  shortcuts (Space to pause, arrows to step), interactive pan & zoom, and 1-click WebM clip export.
- **Pick any of the six detectors** (0.75–5 µm) and a 3, 6, 12 or 20 arcmin field.
- **Spectrum from every exposure.** SPHEREx's filters change wavelength across
  the detector, so each exposure sees the target at a slightly different
  wavelength. Measuring the target in all of them gives a 0.75–5 µm spectrum
  per visit. When visits disagree at the same wavelength, the source changed.
- **Measured motion.** The target is located in each visit stack and a straight
  line is fitted through the positions. That gives a proper motion you can
  compare with the catalogue value, which is drawn as a track on the image.
- **Flags.** Pixels SPHEREx marked as saturated, ghosts/artifacts or transients
  can be tinted, bad pixels are dropped, and transients are left out of stacks.
- **Share and embed.** The URL holds the target, detector, view and field, so a
  link opens the same thing. `/embed?...` is a stripped-down player for an iframe.

## Test targets

| Target | Opens with | What to look for |
|---|---|---|
| WISE 0855-0714 | D6, 3′ | Coldest known brown dwarf. Invisible at short wavelengths, clear at 4–5 µm, moves about 8″/yr west. |
| Barnard's Star | D4, 6′ | Over 10″/yr northwards; saturated core, so its position comes from the blanked-out centre. |
| Epsilon Indi B | D4, 6′ | Brown dwarf pair. Its brightness swings with wavelength inside D4 (methane band at 3.3 µm). |
| RW Aurigae | D3, 6′ | Young star whose disk keeps dimming it. Compare visits in the spectrum. |
| R Draconis | D3, 6′ | Mira variable near the north ecliptic pole, so it has many more visits than anything else. |
| Comet 3I/ATLAS | D4, 6′ | Interstellar comet; reveals volatile sublimation and outgassing across 102 NIR channels. |
| (1) Ceres | D3, 6′ | Largest asteroid & dwarf planet in the asteroid belt, cross-matched with CSA NEOSSat. |
| Betelgeuse | D3, 6′ | Red supergiant in Orion, pulsating variable and nearby supernova progenitor. |

## How it works

```
browser ──/api/search──► IRSA TAP (spherex.plane + spherex.artifact)
        ──/api/frames──► HTTP range requests into each Level 2 image on IRSA
                          └► reproject onto a north-up grid, co-add per visit
        ──/api/spectrum► aperture photometry in every exposure, all detectors
        ──/api/motion──► gaussian centroids in each visit stack
```

**Finding images.** One ADQL query against IRSA's `spherex.plane` and
`spherex.artifact` tables returns every Level 2 spectral image whose footprint
contains the position. When the same exposure is in more than one release, the
DR1 version wins over the weekly QR3 one. Exposures are grouped into visits
wherever there is a gap of more than 30 days, and continuous stretches longer than
60 days (near the ecliptic poles) get split into separate visits.

**Reading only what we need.** Each Level 2 file is about 70 MB (2040×2040
image, flags, variance, zodiacal model, PSF cube, wavelength table). Instead of
downloading files or using the cutout service, the backend sends HTTP
multi-range requests for the header blocks, the image rows around the target,
the compressed flag rows and the wavelength table at the end of the file. That
is three or four round trips and a few hundred KB per exposure. The result
matches IRSA's own cutouts pixel for pixel.

**Making the movie.** Each cutout is background-subtracted, then resampled with
its own WCS onto a common north-up, east-left grid centred on the target.
Visit stacks are inverse-variance weighted means with robust 3σ MAD clipping, so cosmic
rays and satellite trails drop out. Every frame keeps its wavelength, which is
read from the file's spectral WCS at the target position.

**Display.** Frames go to the browser as raw float32 arrays (a small binary
format, see `backend/app/wire.py`) so stretch, contrast and colour map change
instantly without another request.

Everything the backend fetches is cached on disk. `demo_cache/` holds the
search results, stacks, spectra, Gaia star catalogues, and NEOSSat cross-matches for the presets, so they open
instantly even if IRSA is slow.

## Run it

Backend (Python 3.11+):

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt    # .venv/bin/pip on mac/linux
.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000
```

Frontend, in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173. Vite proxies `/api` to the backend.

Or run everything in one container (the site is served by the backend on port 7860):

```bash
docker build -t spherex-blink .
docker run -p 7860:7860 spherex-blink
```

Tests: `.venv/Scripts/python -m pytest backend/tests`

### Settings

| Variable | Default | |
|---|---|---|
| `SPHEREX_RELEASES` | `dr1,qr3` | Release preference order. New releases are picked up even if not listed. |
| `BLINK_CACHE` | `./cache` | Where search results, cutouts and stacks are cached. |
| `BLINK_WORKERS` | `12` | Parallel requests to IRSA. |

### Keeping up with new data

SPHEREx publishes new quick-release images every week. Search results are
cached for 24 hours, so new visits show up within a day without anything being
redeployed. `GET /api/search?ra=..&dec=..&fresh=true` forces a fresh query, and
`python scripts/prebake.py` rebuilds the demo cache.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/resolve?q=` | Position, proper motion and parallax for a name or coordinate string |
| `GET /api/targets` | The preset targets |
| `GET /api/search?ra&dec` | Every exposure covering the position, grouped into visits |
| `GET /api/frames?ra&dec&det&view&fov&ref` | Image stack in the SPXF binary format |
| `GET /api/spectrum?ra&dec&pmra&pmdec` | Forced photometry in every exposure (JSON) |
| `GET /api/motion?ra&dec&det&fov&pmra&pmdec` | Per-visit centroids and fitted proper motion |
| `GET /api/gaia?ra&dec&fov` | Gaia DR3 stars in the field with G-band magnitudes |
| `GET /api/neossat?ra&dec&fov` | CADC CAOM-TAP observations for CSA NEOSSat |

## Limitations

- Spectrum fluxes are summed in a fixed 12″ aperture with no aperture
  correction. SPHEREx pixels are 6.15″, so a neighbouring star inside that
  radius adds its light (WISE 0855's blue end is mostly a background star).
- Very bright stars saturate. Their points are flagged and hidden in the
  spectrum by default.
- The catalogue track ignores parallax, which is under 0.6″ for every preset.
- Motion measured from three visits over one year is good to about 1″/yr.
  Only trust it for fast movers.

## Data and credits

This uses data from SPHEREx (Spectro-Photometer for the History of the
Universe, Epoch of Reionization and Ices Explorer), a NASA mission led by
Caltech and managed by JPL, served by the NASA/IPAC Infrared Science Archive
(IRSA). Names are resolved with CDS Sesame (SIMBAD, NED, VizieR). Gaia DR3
astrometry and proper motions are provided directly by ESA Gaia TAP. NEOSSat
observations are retrieved from the Canadian Astronomy Data Centre (CADC) Argus TAP.
Built with Astropy, NumPy, SciPy, PyVO, FastAPI and React. More detail in
[docs/data.md](docs/data.md).
