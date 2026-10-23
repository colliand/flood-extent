"""Plausibility checks of the estimate (there is no flood map to check against, so these are checks, not validation):

  - how much of it lies inside FEMA's studied flood zones (National Flood Hazard Layer, effective), dissolved into
    four plain classes and saved clipped to the event box (data/EVENT/fema_zones.geojson, public domain);
  - the share of the 2 km circle around each named town that the estimate calls open water (the whole circle,
    including any part across the border, as on whatcom.land)."""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry
import shapely
from rasterio import features

from .estimate import Scene
from .event import Event

NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
ZONES = [  # (class, test on FLD_ZONE / ZONE_SUBTY); floodway first, since it is also zone AE
    ("floodway", lambda z, s: z == "AE" and s == "FLOODWAY"),
    ("coastal", lambda z, s: z in ("VE", "V")),
    ("high", lambda z, s: z in ("A", "AE", "AH", "AO", "AR", "A99")),
    ("moderate", lambda z, s: z == "X" and bool(s) and "0.2 PCT" in s),
]


def fema_zones(e: Event) -> gpd.GeoDataFrame:
    w, s, east, n = e.bbox
    http = requests.Session()  # FEMA's server drops connections now and then
    http.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=10, allowed_methods=None)))
    frames, offset = [], 0
    while True:
        r = http.get(NFHL, timeout=180, params={
            "where": f"DFIRM_ID LIKE '{e.county['dfirm']}%'", "outFields": "FLD_ZONE,ZONE_SUBTY",
            "geometry": f"{w},{s},{east},{n}", "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "maxAllowableOffset": 0.00005, "geometryPrecision": 6,
            "f": "geojson", "resultOffset": offset, "resultRecordCount": 200})
        r.raise_for_status()
        body = r.json()
        if body.get("error"):
            raise SystemExit(f"NFHL error: {body['error']}")
        feats = body.get("features", [])
        if feats:
            frames.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
        if not (body.get("exceededTransferLimit") or body.get("properties", {}).get("exceededTransferLimit")
                or len(feats) == 200):
            break
        offset += len(feats)
    z = pd.concat(frames, ignore_index=True)
    z["cls"] = [next((k for k, t in ZONES if t(a, b)), None) for a, b in zip(z.FLD_ZONE, z.ZONE_SUBTY)]
    z = z[z.cls.notna()]
    box = shapely.box(*e.bbox)
    rows = [{"cls": k, "geometry": shapely.set_precision(
                z[z.cls == k].geometry.make_valid().union_all().intersection(box).simplify(0.00005), 1e-6)}
            for k, _ in ZONES if (z.cls == k).any()]
    return gpd.GeoDataFrame(rows, crs=4326)


def run(e: Event) -> None:
    s = Scene(e)
    flood = np.load(e.cache / "flood.npy")
    zones = fema_zones(e)
    zones.to_file(e.data / "fema_zones.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    zu = zones.to_crs(s.crs)
    share = {}
    for cls, g in zip(zu.cls, zu.geometry):
        m = features.geometry_mask([g], out_shape=flood.shape, transform=s.grid, invert=True)
        share[cls] = round(100 * float((flood & m).sum()) / max(1, flood.sum()), 1)
    towns = {}
    for name, (lon, lat) in e.towns.items():
        p = gpd.GeoSeries([shapely.Point(lon, lat)], crs=4326).to_crs(s.crs).iloc[0]
        m = features.geometry_mask([p.buffer(2000)], out_shape=flood.shape, transform=s.grid, invert=True)
        towns[name] = round(100 * float((flood & m).sum()) / float(m.sum()), 1)
    out = {"share_in_fema_zones_pct": share, "share_in_any_studied_zone_pct": round(sum(share.values()), 1),
           "open_water_within_2km_of_town_pct": towns,
           "towns": e.towns,
           "fema": {"source": "FEMA National Flood Hazard Layer (effective), layer 28", "url": NFHL.rsplit("/", 1)[0]}}
    (e.data / "check.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
