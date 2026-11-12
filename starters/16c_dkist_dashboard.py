"""
Project 16 Thursday prototype: an interactive dashboard of DKIST's holdings.

It reads the dataset list that 16b_dkist_answer.py cached in data/, packs it
into a small JSON blob, and drops it into starters/16_dashboard_template.html.
The result is one self-contained web page you can open in any browser:

    dashboard/16_dkist_dashboard.html

In the page you can filter by instrument, seeing quality (Fried parameter r0),
target and public/embargoed status, and see when embargoed data become public.
Charts are drawn with plotly.js in the browser.

Run from the repo folder:
    python3 starters/16b_dkist_answer.py     # only needed once, downloads the list
    python3 starters/16c_dkist_dashboard.py

Data source: NSO DKIST Data Center, https://dkist.data.nso.edu
"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "data" / "dkist_inventory_full.csv"
TEMPLATE = REPO / "starters" / "16_dashboard_template.html"
OUT = REPO / "dashboard" / "16_dkist_dashboard.html"

# Same instrument order (and therefore colors) everywhere in the page.
INSTRUMENTS = ["VISP", "VBI", "CRYO-NIRSP", "DL-NIRSP"]

if not CACHE.exists():
    raise SystemExit(f"No cached data at {CACHE}. Run starters/16b_dkist_answer.py first.")

df = pd.read_csv(CACHE)
fetched = datetime.fromtimestamp(CACHE.stat().st_mtime, tz=timezone.utc)
print(f"Loaded {len(df)} datasets (list downloaded {fetched:%Y-%m-%d %H:%M} UTC)")

unknown = sorted(set(df.instrument) - set(INSTRUMENTS))
if unknown:
    raise SystemExit(f"New instrument(s) in the archive: {unknown}. Add them to INSTRUMENTS.")


def seeing_cm(fried_m):
    """Fried parameter in cm, or None when missing or impossible (a few archive rows hold placeholders)."""
    if fried_m is None or (isinstance(fried_m, float) and math.isnan(fried_m)) or not 0 < fried_m <= 1:
        return None
    return round(fried_m * 100, 1)


def first_line(lines):
    return lines.split("; ")[0] if isinstance(lines, str) else ""


rows = []
for r in df.itertuples():
    # Only keep an embargo end date for datasets the archive marks as embargoed.
    end = r.embargo_end if (r.embargoed and isinstance(r.embargo_end, str)) else None
    targets = "; ".join(t for t in str(r.target_types).split("; ") if t and t != "nan")
    rows.append([
        r.dataset_id,
        INSTRUMENTS.index(r.instrument),
        r.start[:19] + "Z",
        round(r.wavelength_nm, 2),
        seeing_cm(r.fried_m),
        end[:19] + "Z" if end else None,
        round(r.size_gb, 2),
        targets,
        first_line(r.spectral_lines),
    ])

data = {"fetched": fetched.isoformat(), "instruments": INSTRUMENTS, "rows": rows}
blob = json.dumps(data, separators=(",", ":"))

html = TEMPLATE.read_text().replace("/*DATA*/", blob)
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(html)
print(f"Wrote {OUT.relative_to(REPO)} ({len(html) / 1e6:.2f} MB). Open it in a web browser.")
