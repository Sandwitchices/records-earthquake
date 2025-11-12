from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import importlib.util
import sys
import os
import pandas
app = FastAPI(title="PHIVOLCS Earthquake Viewer", version="1.0.0")

# Templates directory (create templates/earthquakes.html)
os.makedirs("templates", exist_ok=True)
templates = Jinja2Templates(directory="templates")

# Adjust this if your submodule folder name is different
SUBMODULE_DIR = Path(__file__).parent / "phivolcs-earthquake-data-scraper"
SCRAPER_FILE = SUBMODULE_DIR / "scrape_phivolcs.py"  # common filename in that repo


def load_scraper_module():
    """Load the scraper module from the submodule path using importlib."""
    if not SCRAPER_FILE.exists():
        raise FileNotFoundError(f"Scraper file not found: {SCRAPER_FILE}")
    spec = importlib.util.spec_from_file_location("phivolcs_scraper", str(SCRAPER_FILE))
    module = importlib.util.module_from_spec(spec)
    sys.modules["phivolcs_scraper"] = module
    spec.loader.exec_module(module)
    return module


def fetch_earthquakes():
    """
    Call the scraper function inside the submodule.
    Tries several common function names and returns a list of dicts.
    """
    mod = load_scraper_module()

    # Try common function names used in scrapers
    for fn_name in ("scrape_phivolcs", "scrape", "get_earthquakes", "get_data"):
        fn = getattr(mod, fn_name, None)
        if callable(fn):
            return fn()

    # Fallback: maybe the module exposes a variable
    if hasattr(mod, "EARTHQUAKES"):
        return getattr(mod, "EARTHQUAKES")

    raise RuntimeError("No scraper function or data found in submodule")


@app.get("/api/earthquakes")
async def api_earthquakes():
    """Return JSON list of earthquakes (magnitude >= 3.0)."""
    try:
        data = fetch_earthquakes()
        filtered = []
        for eq in data:
            try:
                mag = float(eq.get("magnitude", 0))
            except (TypeError, ValueError):
                continue
            if mag >= 3.0:
                filtered.append({
                    "date": eq.get("date", ""),
                    "time": eq.get("time", ""),
                    "location": eq.get("location", "Unknown"),
                    "magnitude": mag,
                    "depth": eq.get("depth", "N/A")
                })
        return JSONResponse({"status": "success", "data": filtered})
    except Exception as e:
        # Log to stdout so Railway/GitHub Actions logs show it
        print("Error in /api/earthquakes:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the HTML page using templates/earthquakes.html."""
    try:
        data = fetch_earthquakes()
        # Filter and normalize for template
        filtered = []
        for eq in data:
            try:
                mag = float(eq.get("magnitude", 0))
            except (TypeError, ValueError):
                continue
            if mag >= 3.0:
                filtered.append({
                    "date": eq.get("date", ""),
                    "time": eq.get("time", ""),
                    "location": eq.get("location", "Unknown"),
                    "magnitude": mag,
                    "depth": eq.get("depth", "N/A")
                })
        return templates.TemplateResponse("earthquakes.html", {"request": request, "earthquakes": filtered})
    except Exception as e:
        print("Error in /:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))