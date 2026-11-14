# Vercel entry point: the whole FastAPI backend runs as one Python function
import os
import sys
from pathlib import Path

# only /tmp is writable on Vercel
os.environ.setdefault("BLINK_CACHE", "/tmp/blink-cache")
os.environ.setdefault("BLINK_MAX_BYTES", "4000000")

# astropy wants a config and cache dir; it uses the XDG ones only if an astropy folder exists
for kind in ("config", "cache"):
    base = f"/tmp/.{kind}"
    os.makedirs(f"{base}/astropy", exist_ok=True)
    os.environ.setdefault(f"XDG_{kind.upper()}_HOME", base)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app  # noqa: E402,F401
