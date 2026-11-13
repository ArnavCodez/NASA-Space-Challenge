# Data notes

## Where the images come from

All images are SPHEREx Level 2 spectral images from the NASA/IPAC Infrared
Science Archive (IRSA).

- **Releases.** DR1 covers the first two all-sky surveys. QR3 is the weekly
  quick release from survey 3 onwards. QR2 has been retired and is skipped. If
  an exposure is in both DR1 and QR3, the DR1 file is used.
- **Search.** IRSA TAP (`https://irsa.ipac.caltech.edu/TAP`), joining
  `spherex.artifact` to `spherex.plane` with
  `CONTAINS(POINT('ICRS', ra, dec), plane.poly) = 1`. The detector comes from the
  file name (`..._D<n>_spx_...`) and the time from `time_bounds_lower`/`upper`
  (MJD).
- **Pixels.** Files are read straight from IRSA's `ibe` file server with HTTP
  `Range` requests. The server allows up to 200 ranges per request, so we send
  at most 120.

## What is in a Level 2 file

| HDU | Used for |
|---|---|
| `IMAGE` | Surface brightness in MJy/sr, 2040×2040, 6.15″ pixels. Celestial WCS with SIP distortion. |
| `FLAGS` | Per-pixel bit flags, stored as a RICE_1 tile-compressed table, one tile per row. Bit names are in the `MSKN*` header keywords. |
| `VARIANCE`, `ZODI`, `EPSF` | Not read. |
| `WCS-WAVE` | Lookup table behind the spectral WCS (`key="W"`). Gives the central wavelength and bandwidth at any pixel. |

## Flags

| Group | SPHEREx flag names | What we do |
|---|---|---|
| bad | `SUR_ERROR`, `NONFUNC`, `MISSING_DATA`, `HOT`, `COLD`, `PERSIST`, `OUTLIER` | Pixel set to NaN before anything else |
| saturated | `OVERFLOW`, `NONLINEAR` | Tinted red; photometry point flagged |
| artifact | `GHOST`, `GHOST_FPA`, `GHOST_EXT`, `STREAK`, `BLOOM`, `SNOWBALL`, `HALO`, `CROSSTALK` | Tinted orange; photometry point flagged |
| transient | `TRANSIENT` | Tinted blue; left out of visit stacks |
| source | `SOURCE` | Kept out of background estimates |

## Units

Images stay in MJy/sr. Spectrum points are converted to mJy by multiplying
by the pixel solid angle, (6.15″)², which is 0.889 mJy per MJy/sr. They are
plain aperture sums inside 2 pixels (12.3″) with the background taken from a
4–7 pixel annulus. No aperture correction is applied.

## Positions

Preset positions, proper motions and parallaxes are from SIMBAD (J2000, epoch
2000.0). Other names go through CDS Sesame. Positions are moved linearly along
the proper motion to 2026.0 for centring, and to each exposure's own date for
photometry.

## Acknowledgements

SPHEREx is a NASA mission. Caltech leads it and JPL manages it. IRSA is funded
by NASA and operated by Caltech/IPAC. Please cite SPHEREx and IRSA as their
data policies ask if you use anything this tool produces in a publication. Name
resolution uses the CDS Sesame service (CDS, Strasbourg).
