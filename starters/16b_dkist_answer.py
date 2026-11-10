"""
Project 16: What has the Inouye Solar Telescope (DKIST) observed since 2022,
and how much of it is public yet?

Data source: NSO DKIST Data Center, https://dkist.data.nso.edu,
searched anonymously with the `dkist` Python package (through sunpy's Fido).

What this script does:
  1. Downloads the archive's list of every Level-1 dataset (only the list,
     not the images) and caches it in data/dkist_inventory_full.csv.
  2. Prints a summary that answers the question.
  3. Saves three plots to plots/.

Run it from the repo folder:  python3 starters/16b_dkist_answer.py
Delete the CSV in data/ if you want to fetch a fresh copy.
"""
from pathlib import Path
from collections import Counter

import pandas as pd
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "data" / "dkist_inventory_full.csv"
PLOTS = REPO / "plots"
PLOTS.mkdir(exist_ok=True)
CACHE.parent.mkdir(exist_ok=True)

INSTRUMENT_COLORS = {"VBI": "#2a9d8f", "VISP": "#e76f51",
                     "CRYO-NIRSP": "#264653", "DL-NIRSP": "#e9c46a"}


# ---------------------------------------------------------------- 1. download
def download_inventory():
    """Ask the DKIST archive for every dataset, 300 at a time."""
    import dkist.net                      # registers DKIST with Fido (no login needed)
    from sunpy.net import Fido, attrs as a

    rows = []
    for page in range(1, 100):
        t = Fido.search(a.Time("2022-01-01", "2026-12-31"),
                        a.dkist.Page(page), a.dkist.PageSize(300))[0]
        if len(t) == 0:
            break
        for r in t:
            end = r["Embargo End Date"]
            rows.append(dict(
                dataset_id=r["Dataset ID"],
                instrument=r["Instrument"],
                start=r["Start Time"].isot,
                end=r["End Time"].isot,
                wavelength_nm=r["Wavelength"][0].to_value("nm"),
                spectral_lines="; ".join(r["Spectral Lines"] or []),
                target_types="; ".join(r["Target Types"]),
                proposal=r["Primary Proposal ID"],
                size_gb=r["Dataset Size"].to_value("GB"),
                fried_m=r["Average Fried Parameter"],   # seeing: bigger = steadier air
                embargoed=bool(r["Embargoed"]),
                embargo_end=str(getattr(end, "isot", end)) if end is not None else None,
            ))
        print(f"  page {page}: {len(rows)} datasets so far")
        if len(rows) >= t.total_available_results:
            break
    df = pd.DataFrame(rows)
    df.to_csv(CACHE, index=False)
    return df


if CACHE.exists():
    print(f"Using cached inventory: {CACHE}")
    df = pd.read_csv(CACHE)
else:
    print("Downloading the DKIST inventory (list only, a few MB)...")
    df = download_inventory()

for col in ["start", "end", "embargo_end"]:
    df[col] = pd.to_datetime(df[col], utc=True, format="ISO8601")
df["hours"] = (df["end"] - df["start"]).dt.total_seconds() / 3600
df["year"] = df["start"].dt.year


# ---------------------------------------------------------------- 2. summary
print("\n=== What has DKIST observed? ===")
print(f"Datasets: {len(df)}  from {df.start.min():%Y-%m-%d} to {df.start.max():%Y-%m-%d}")
print(f"Observing time covered: {df.hours.sum():,.0f} hours")
print(f"Total data volume: {df.size_gb.sum() / 1000:,.1f} TB")
print(f"Separate science proposals: {df.proposal.nunique()}")

print("\nDatasets per year and instrument:")
print(df.pivot_table(index="year", columns="instrument", values="dataset_id",
                     aggfunc="count", fill_value=0))

# A dataset can have several target types, so count each one.
targets = Counter(t.strip() for s in df.target_types.fillna("") for t in s.split(";") if t.strip())
print("\nWhat the telescope was pointed at (a dataset can list several):")
for name, n in targets.most_common(15):
    print(f"  {name:25s} {n}")

lines = Counter(t.strip() for s in df.spectral_lines.fillna("") for t in s.split(";") if t.strip())
print("\nMost-used spectral lines (which atoms' light was recorded):")
for name, n in lines.most_common(10):
    print(f"  {name:25s} {n}")

print("\n=== How much is public? ===")
public = (~df.embargoed).sum()
print(f"Public: {public} of {len(df)} datasets ({public / len(df):.0%})")
print(f"By data volume: {df.loc[~df.embargoed, 'size_gb'].sum() / df.size_gb.sum():.0%} public")
print(df.groupby("instrument").embargoed.agg(public=lambda s: (~s).sum(), embargoed="sum"))

emb = df[df.embargoed].dropna(subset=["embargo_end"])
if len(emb):
    print(f"\nEmbargoed datasets with a release date: {len(emb)} of {df.embargoed.sum()}")
    print(f"  first release: {emb.embargo_end.min():%Y-%m-%d}   last release: {emb.embargo_end.max():%Y-%m-%d}")
    print("  releases per quarter:")
    print(emb.groupby(emb.embargo_end.dt.tz_localize(None).dt.to_period("Q")).size().to_string())

print(f"Oldest embargoed observation: {df.loc[df.embargoed, 'start'].min():%Y-%m-%d} "
      "(everything observed before that is public)")

# A handful of datasets have impossible seeing values (thousands of km), which look
# like placeholders in the archive, and about a quarter have none. Keep 0-1 m only.
good = df.fried_m.between(0, 1)
print(f"\nSeeing quality (Fried parameter r0; bigger = steadier air), {good.sum()} datasets with a valid value:")
print((df.loc[good, "fried_m"] * 100).describe().round(1).rename(lambda k: k + " (cm)" if k != "count" else k).to_string())


# ---------------------------------------------------------------- 3. plots
# Plot A: what kinds of solar features were observed
fig, ax = plt.subplots(figsize=(9, 5.5))
top = targets.most_common(12)[::-1]
ax.barh([t for t, _ in top], [n for _, n in top], color="#e76f51")
for i, (_, n) in enumerate(top):
    ax.text(n, i, f" {n}", va="center", fontsize=9)
ax.set(xlabel="Number of datasets", title="What DKIST has pointed at, 2022–2026\n(a dataset can list more than one target)")
ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, "Data: NSO DKIST Data Center (dkist.data.nso.edu)", fontsize=8, color="gray")
fig.tight_layout()
fig.savefig(PLOTS / "16_dkist_target_types.png", dpi=150)

# Plot B: datasets per year, public vs. embargoed
fig, ax = plt.subplots(figsize=(9, 5))
by_year = df.groupby(["year", "embargoed"]).size().unstack(fill_value=0)
ax.bar(by_year.index, by_year.get(False, 0), color="#2a9d8f", label="Public")
ax.bar(by_year.index, by_year.get(True, 0), bottom=by_year.get(False, 0), color="#adb5bd", label="Embargoed")
for yr, row in by_year.iterrows():
    total = row.sum()
    ax.text(yr, total, f"{row.get(False, 0) / total:.0%} public", ha="center", va="bottom", fontsize=9)
ax.set(xlabel="Year observed", ylabel="Number of datasets", title="DKIST datasets by year: how much is public?")
ax.set_xticks(by_year.index)
ax.legend(frameon=False)
ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, "Data: NSO DKIST Data Center (dkist.data.nso.edu)", fontsize=8, color="gray")
fig.tight_layout()
fig.savefig(PLOTS / "16_dkist_public_vs_embargoed_by_year.png", dpi=150)

# Plot C: when do embargoed datasets become public?
if len(emb):
    fig, ax = plt.subplots(figsize=(9, 5))
    month = emb.embargo_end.dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    counts = emb.assign(month=month).groupby(["month", "instrument"]).size().unstack(fill_value=0)
    bottom = 0
    for inst in counts.columns:
        ax.bar(counts.index, counts[inst], width=25, bottom=bottom,
               color=INSTRUMENT_COLORS.get(inst), label=inst)
        bottom = bottom + counts[inst]
    ax.set(xlabel="Month the embargo ends", ylabel="Datasets becoming public",
           title="When will today's embargoed DKIST data become public?")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.01, "Data: NSO DKIST Data Center (dkist.data.nso.edu)", fontsize=8, color="gray")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PLOTS / "16_dkist_embargo_release_schedule.png", dpi=150)

print("\nSaved plots to", PLOTS)
