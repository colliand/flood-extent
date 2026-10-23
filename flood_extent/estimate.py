"""Open floodwater by change detection, from the cached inputs (read.py).

Calm open water reflects the radar pulse away from the satellite like a mirror, so it looks DARK; fields, forest and
towns scatter some energy back. Floodwater is a pixel that is

    dark on the flood date            VV < −18 dB
    AND much darker than normal       at least 3 dB below the median of the pre-flood dates
    AND not permanent water           not dark on ANY pre-flood date (calm days), and JRC occurrence < 50%
    AND near a stream                 HAND < 10 m: dark hillsides facing away from the radar are shadow, not water
    AND inside the county

Patches under 0.5 ha (50 px) are dropped as speckle. The water threshold is the judgement call that matters most, so
the estimate is repeated at −19 and −17 dB and the range reported; each other setting is also moved one step on its own
(sensitivity), so it is clear which choices move the answer."""
import json

import geopandas as gpd
import numpy as np
import requests
import shapely
from rasterio import features

from .event import Event
from .read import cached

WATER_DB, CHANGE_DB, HAND_MAX_M, MIN_PATCH = -18.0, -3.0, 10.0, 50
PERM_JRC = 50
RANGE_DB = (-19.0, -17.0)
SIMPLIFY_M = 10.0
M2_PER_ACRE = 4046.8564224
COUNTY_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query"
SENSITIVITY = {  # one setting moved at a time, the rest at their defaults
    "water_db": (-19.0, -17.0), "change_db": (-2.0, -4.0), "hand_max_m": (5.0, 15.0), "min_patch_px": (10, 200)}


def county(e: Event) -> gpd.GeoDataFrame:
    """The county boundary from the US Census (TIGERweb), in WGS84."""
    r = requests.get(COUNTY_URL, timeout=60, params={
        "where": f"STATE='{e.county['state']}' AND BASENAME='{e.county['name']}'", "outFields": "NAME",
        "outSR": 4326, "f": "geojson"})
    r.raise_for_status()
    return gpd.GeoDataFrame.from_features(r.json()["features"], crs=4326)


class Scene:
    """The cached inputs plus the fixed masks, ready to classify with any settings."""

    def __init__(self, e: Event):
        vv, self.hand, occ, self.grid, self.crs = cached(e)
        pre = np.stack([vv[d] for d in e.pre])
        self.normal, self.post = np.median(pre, axis=0), vv[e.post]
        self.pre_min, self.occ = pre.min(axis=0), occ
        g = county(e).to_crs(self.crs).geometry.iloc[0]
        self.inside = features.geometry_mask([g], out_shape=self.post.shape, transform=self.grid, invert=True)

    def flood(self, water_db=WATER_DB, change_db=CHANGE_DB, hand_max_m=HAND_MAX_M, min_patch_px=MIN_PATCH) -> np.ndarray:
        perm = (self.pre_min < water_db) | (self.occ >= PERM_JRC)
        f = ((self.post < water_db) & ((self.post - self.normal) < change_db) & ~perm
             & (self.hand < hand_max_m) & self.inside)
        return features.sieve(f.astype("uint8"), size=min_patch_px, connectivity=8).astype(bool)

    def explain(self) -> dict:
        """Acres removed by each test, in order: what the method throws away, and why."""
        dark = (self.post < WATER_DB) & self.inside
        steps, m = {"dark on the flood date": dark}, dark
        for name, keep in [("and 3 dB darker than normal", (self.post - self.normal) < CHANGE_DB),
                           ("and not permanent water", ~((self.pre_min < WATER_DB) | (self.occ >= PERM_JRC))),
                           ("and less than 10 m above a stream", self.hand < HAND_MAX_M)]:
            m = m & keep
            steps[name] = m
        steps["and in patches of 0.5 ha or more"] = self.flood()
        return {k: round(acres(v)) for k, v in steps.items()}


def acres(m: np.ndarray) -> float:
    return float(m.sum() * 100 / M2_PER_ACRE)  # 10 m pixels


def run(e: Event) -> None:
    s = Scene(e)
    flood = s.flood()
    sens = {k: {str(v): round(acres(s.flood(**{k: v})), -2) for v in vals} for k, vals in SENSITIVITY.items()}
    polys = [shapely.geometry.shape(g) for g, v in
             features.shapes(flood.astype("uint8"), mask=flood, transform=s.grid) if v == 1]
    geom = shapely.union_all(polys).simplify(SIMPLIFY_M, preserve_topology=True)
    gdf = gpd.GeoDataFrame([{"what": "open floodwater (estimate)", "acres": round(acres(flood)), "geometry": geom}],
                           geometry="geometry", crs=s.crs).to_crs(4326)
    gdf["geometry"] = shapely.set_precision(gdf.geometry.values, 1e-5)
    np.save(e.cache / "flood.npy", flood)
    summary = {
        "event": e.name, "moment": e.moment,
        "acres": round(acres(flood), -2),
        "acres_range": [round(acres(s.flood(water_db=d)), -2) for d in RANGE_DB],
        "km2": round(acres(flood) * M2_PER_ACRE / 1e6, 1),
        "steps_acres": s.explain(),
        "sensitivity_acres": sens,
        "method": {"water_db": WATER_DB, "change_db": CHANGE_DB, "hand_max_m": HAND_MAX_M, "min_patch_ha": MIN_PATCH / 100,
                   "permanent_water": f"dark on any pre-flood date, or JRC occurrence >= {PERM_JRC}%",
                   "speckle": "5x5 median", "pre_dates": e.pre, "post_date": e.post, "track": e.track,
                   "range_water_db": list(RANGE_DB)},
        "caveats": ["Open water only: water among buildings and under trees is missed by radar.",
                    "One moment: water had drained from some places and was still rising in others.",
                    "Not FEMA's or the county's map, and not for decisions about a property."],
    }
    (e.data / "estimate.geojson").write_text(gdf.to_json(drop_id=True, separators=(",", ":")))
    (e.data / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"{summary['acres']:,.0f} acres (range {summary['acres_range']})\nsteps {summary['steps_acres']}\n"
          f"sensitivity {sens}")
