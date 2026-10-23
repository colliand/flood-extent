"""The published outputs for the first event: labelled, caveated, plain fields only, and plausible against FEMA."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "nooksack-2021-11"


def test_summary_is_consistent_and_caveated():
    s = json.loads((DATA / "summary.json").read_text())
    lo, hi = s["acres_range"]
    assert lo <= s["acres"] <= hi
    assert any("not for decisions about a property" in c.lower() for c in s["caveats"])


def test_estimate_has_only_plain_fields():
    f = json.loads((DATA / "estimate.geojson").read_text())["features"]
    assert len(f) == 1 and set(f[0]["properties"]) == {"what", "acres"}


def test_most_water_is_in_fema_zones():
    c = json.loads((DATA / "check.json").read_text())
    assert c["share_in_any_studied_zone_pct"] >= 75
