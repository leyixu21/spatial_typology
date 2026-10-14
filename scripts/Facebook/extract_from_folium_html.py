"""Recover tabular data embedded in folium-generated HTML maps.

The files in spatial_typologies/data are folium map exports, i.e.
visualizations. The underlying data is embedded in the JavaScript:

- FI_fine_home_locations.html: `var data = [[lat, lon, color, popup_html], ...]`
- FI_mobility_*.html: one `L.polyline([[o_lat,o_lon],[d_lat,d_lon]], {...})`
  per flow, with attributes in a popup HTML div that follows it.

This script parses both formats and writes CSV files next to the HTML files.
"""

import html as html_mod
import json
import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def extract_fine_home_locations(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"var data = (\[.*?\]);", text, re.DOTALL)
    if not m:
        raise ValueError(f"no 'var data = [...]' block found in {path}")
    rows = json.loads(m.group(1))  # \u003c-style escapes are valid JSON

    records = []
    for lat, lon, color, popup in rows:
        popup = html_mod.unescape(popup)
        fields = dict(
            re.findall(r"<br\s*/?>\s*([^:<]+):\s*([^<]+)", "<br>" + popup)
        )
        records.append(
            {
                "lat": lat,
                "lon": lon,
                "color": color,
                "region": re.search(r"<b>(.*?)</b>", popup).group(1),
                "gadm_id": fields.get("GADM", "").strip(),
                "day_prob_sum": float(fields["Day probability sum"]),
                "night_prob_sum": float(fields["Night probability sum"]),
                "day_destinations": int(fields["Day destinations"]),
                "night_destinations": int(fields["Night destinations"]),
            }
        )
    return pd.DataFrame(records)


FLOW_RE = re.compile(
    r"L\.polyline\(\s*"
    r"\[\s*\[([\d.\-]+),\s*([\d.\-]+)\],\s*\[([\d.\-]+),\s*([\d.\-]+)\]\s*\]\s*,\s*"
    r"(\{.*?\})\s*\)"  # options dict (single line in folium output)
    r".{0,2000}?popup.*?setContent"  # skip ahead to the popup content
    r".{0,2000}?<b>Origin:</b>\s*(.*?)<br>\s*"
    r"<b>Destination:</b>\s*(.*?)<br>\s*"
    r"<b>Origin ID:</b>\s*(.*?)<br>\s*"
    r"<b>Destination ID:</b>\s*(.*?)<br>\s*"
    r"<b>Week start:</b>\s*(.*?)<br>\s*"
    r"<b>Daypart:</b>\s*(.*?)<br>\s*"
    r"<b>Recorded mobility fraction:</b>\s*(.*?)<br>\s*"
    r"<b>Source rows aggregated:</b>\s*(\d+)",
    re.DOTALL,
)


def extract_flows(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8")
    records = []
    for m in FLOW_RE.finditer(text):
        opts = json.loads(m.group(5))
        records.append(
            {
                "origin_lat": float(m.group(1)),
                "origin_lon": float(m.group(2)),
                "dest_lat": float(m.group(3)),
                "dest_lon": float(m.group(4)),
                "line_weight": opts.get("weight"),
                "color": opts.get("color"),
                "origin": html_mod.unescape(m.group(6)).strip(),
                "destination": html_mod.unescape(m.group(7)).strip(),
                "origin_id": m.group(8).strip(),
                "dest_id": m.group(9).strip(),
                "week_start": m.group(10).strip(),
                "daypart": m.group(11).strip(),
                "mobility_fraction": float(m.group(12)),
                "source_rows": int(m.group(13)),
            }
        )
    if not records:
        raise ValueError(f"no L.polyline flows parsed from {path}")
    return pd.DataFrame(records)


def main():
    out1 = DATA_DIR / "FI_fine_home_locations.csv"
    df1 = extract_fine_home_locations(DATA_DIR / "FI_fine_home_locations.html")
    df1.to_csv(out1, index=False)
    print(f"{out1.name}: {len(df1)} rows, columns {list(df1.columns)}")

    out2 = DATA_DIR / "FI_mobility_2024-07-29_day_20_origins.csv"
    df2 = extract_flows(DATA_DIR / "FI_mobility_2024-07-29_day_20_origins.html")
    df2.to_csv(out2, index=False)
    print(f"{out2.name}: {len(df2)} rows, columns {list(df2.columns)}")


if __name__ == "__main__":
    main()
