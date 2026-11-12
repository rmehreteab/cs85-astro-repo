"""
Project 16 Thursday prototype: an interactive "Sun explorer" for DKIST's holdings.

It reads the dataset list that 16b_dkist_answer.py cached in data/, packs it
into a small JSON blob, and drops it into starters/16_dashboard_template.html.
The result is one self-contained web page you can open in any browser:

    dashboard/16_dkist_dashboard.html

In the page:
  * every dataset is a box drawn where the telescope pointed on the Sun,
  * a time slider (with a play button) shows observations piling up since 2022
    and, past today, embargoed datasets unlocking on their release dates,
  * you can filter by instrument, target, seeing quality and public/locked status,
  * clicking a box explains that dataset in plain words and links its preview movie.

Run from the repo folder:
    python3 starters/16b_dkist_answer.py     # only needed once, downloads the list
    python3 starters/16c_dkist_dashboard.py

Data source: NSO DKIST Data Center, https://dkist.data.nso.edu
"""
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "data" / "dkist_inventory_full.csv"
TEMPLATE = REPO / "starters" / "16_dashboard_template.html"
OUT = REPO / "dashboard" / "16_dkist_dashboard.html"

# Same instrument order (and therefore colors) everywhere in the page.
INSTRUMENTS = ["VISP", "VBI", "CRYO-NIRSP", "DL-NIRSP"]

# Positions farther than this from the Sun's centre (in arcseconds) are not real
# pointings. A few archive rows have values of 100,000+, so we leave those off the map.
MAX_RADIUS_ARCSEC = 2000

if not CACHE.exists():
    raise SystemExit(f"No cached data at {CACHE}. Run starters/16b_dkist_answer.py first.")

df = pd.read_csv(CACHE)
if "bounding_box" not in df.columns:
    raise SystemExit("The cached list is from an older version of 16b. Delete it and rerun 16b_dkist_answer.py.")
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


def box(bbox):
    """'(x1,y1),(x2,y2)' in arcsec -> centre x, centre y, width, height. None if unusable."""
    nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", str(bbox))]
    if len(nums) != 4:
        return None
    x1, y1, x2, y2 = nums
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if math.hypot(cx, cy) > MAX_RADIUS_ARCSEC:
        return None
    return [round(cx), round(cy), round(abs(x1 - x2)), round(abs(y1 - y2))]


def vimeo_id(url):
    m = re.search(r"vimeo\.com/(\d+)", str(url))
    return m.group(1) if m else None


# Experiment descriptions are long and shared by many datasets, so store each once.
experiments = {}
for eid, text in df.groupby("experiment_id").experiment_description.first().items():
    experiments[eid] = " ".join(str(text).split()) if isinstance(text, str) else ""
exp_ids = sorted(experiments)

rows, no_position = [], 0
for r in df.itertuples():
    pos = box(r.bounding_box)
    if pos is None:
        no_position += 1
    end = r.embargo_end if (r.embargoed and isinstance(r.embargo_end, str)) else None
    targets = "; ".join(t for t in str(r.target_types).split("; ") if t and t != "nan")
    minutes = (pd.Timestamp(r.end) - pd.Timestamp(r.start)).total_seconds() / 60
    rows.append([
        r.dataset_id,                                   # 0 id
        INSTRUMENTS.index(r.instrument),                # 1 instrument index
        r.start[:19] + "Z",                             # 2 observation start
        round(minutes, 1),                              # 3 duration in minutes
        round(r.wavelength_nm, 2),                      # 4 wavelength
        r.spectral_lines.split("; ")[0] if isinstance(r.spectral_lines, str) else "",  # 5 line
        seeing_cm(r.fried_m),                           # 6 seeing r0 in cm
        end[:19] + "Z" if end else None,                # 7 embargo end (None = public)
        round(r.size_gb, 2),                            # 8 size in GB
        targets,                                        # 9 targets
        pos,                                            # 10 [x, y, w, h] arcsec, or None
        exp_ids.index(r.experiment_id),                 # 11 experiment index
        vimeo_id(r.preview_url),                        # 12 preview movie id
    ])

print(f"{len(rows) - no_position} datasets have a usable position; {no_position} are left off the map.")

data = {
    "fetched": fetched.isoformat(),
    "instruments": INSTRUMENTS,
    "experiments": [[e, experiments[e]] for e in exp_ids],
    "rows": rows,
}
blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")  # safe inside <script>

html = TEMPLATE.read_text().replace("/*DATA*/", blob)
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(html)
print(f"Wrote {OUT.relative_to(REPO)} ({len(html) / 1e6:.2f} MB). Open it in a web browser.")
