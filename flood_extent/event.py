"""An event is one JSON file in events/: area, Sentinel-1 orbit track, the pre-flood dates that define "normal", the
flood date, and the county the estimate is clipped to (and whose FEMA flood zones it is checked against)."""
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Event:
    id: str
    name: str
    bbox: tuple[float, float, float, float]  # lon/lat: west, south, east, north
    track: int  # Sentinel-1 relative orbit: same track = same viewing geometry
    pre: list[str]  # YYYYMMDD pass dates before the flood
    post: str  # YYYYMMDD pass date during the flood
    moment: str  # when the flood pass was taken, in words
    county: dict  # {"state": FIPS, "name": TIGER basename, "dfirm": FEMA DFIRM_ID prefix}
    towns: dict  # name → [lon, lat]; share of open water within 2 km is reported
    zoom: tuple[float, float, float, float]  # lon/lat window for the radar figure

    @property
    def data(self) -> Path:
        return ROOT / "data" / self.id

    @property
    def cache(self) -> Path:
        return ROOT / "cache" / self.id


def load(event_id: str) -> Event:
    cfg = json.loads((ROOT / "events" / f"{event_id}.json").read_text())
    cfg["bbox"], cfg["zoom"] = tuple(cfg["bbox"]), tuple(cfg["zoom"])
    return Event(**cfg)
