"""Read every input onto one 10 m UTM grid over the event's bounding box and cache it (cache/EVENT/inputs.npz):

  - Sentinel-1 RTC VV backscatter (terrain-corrected, from the Planetary Computer, no login) for each pass date, both
    frames of each pass stitched, converted to dB, speckle reduced with a 5 × 5 median filter;
  - HAND, height above nearest drainage (ASF GLO-30, from the Copernicus DEM);
  - JRC Global Surface Water occurrence (% of months with water, 1984–2020).

The scene list goes to data/EVENT/inputs.json so the run can be traced to the exact scenes."""
import json
import math
import urllib.parse
from datetime import datetime, timezone

import numpy as np
import rasterio
import requests
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from scipy.ndimage import median_filter

from .event import Event

PC = "https://planetarycomputer.microsoft.com/api"
HAND_URL = "https://glo-30-hand.s3.amazonaws.com/v1/2021/Copernicus_DSM_COG_10_N{lat:02d}_00_W{lon:03d}_00_HAND.tif"
JRC_URL = ("https://ai4edataeuwest.blob.core.windows.net/jrcglobalwater/occurrence/"
           "occurrence_{lon}W_{lat}Nv1_3_2020cog.tif")  # 10° tiles named by their north-west corner
GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",  # a stalled connection once hung a read for 40 min
            "GDAL_HTTP_TIMEOUT": 60, "GDAL_HTTP_MAX_RETRY": 5, "GDAL_HTTP_RETRY_DELAY": 5}
SPECKLE = 5


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


def search(e: Event) -> list[dict]:
    dates = sorted(e.pre + [e.post])
    lo = f"{dates[0][:4]}-{dates[0][4:6]}-{dates[0][6:]}"
    hi = f"{dates[-1][:4]}-{dates[-1][4:6]}-{dates[-1][6:]}T23:59:59Z"
    r = requests.post(f"{PC}/stac/v1/search", timeout=120, json={
        "collections": ["sentinel-1-rtc"], "bbox": list(e.bbox), "datetime": f"{lo}/{hi}", "limit": 200,
        "query": {"sat:relative_orbit": {"eq": e.track}}})
    r.raise_for_status()
    return r.json()["features"]


def vv_stack(e: Event, used: list) -> tuple[dict, rasterio.Affine, tuple, str]:
    """VV in dB for each date on one 10 m grid; frames of one pass are stitched (the first frame wins overlaps)."""
    items = search(e)
    tok = requests.get(f"{PC}/sas/v1/token/sentinel-1-rtc", timeout=60).json()["token"]
    out, grid, shape, crs = {}, None, None, None
    for d in e.pre + [e.post]:
        frames = sorted([i for i in items if d in i["id"]], key=lambda i: i["id"], reverse=True)
        if not frames:
            raise SystemExit(f"No Sentinel-1 scene for {d} on track {e.track}")
        a = None
        for it in frames:
            with rasterio.Env(**GDAL_ENV), rasterio.open(it["assets"]["vv"]["href"] + "?" + tok) as r:
                if grid is None:
                    b = transform_bounds("EPSG:4326", r.crs, *e.bbox)
                    w = from_bounds(*b, transform=r.transform).round_offsets().round_lengths()
                    grid, shape, crs = r.window_transform(w), (int(w.height), int(w.width)), r.crs.to_string()
                w2 = from_bounds(grid.c, grid.f - shape[0] * 10, grid.c + shape[1] * 10, grid.f,
                                 transform=r.transform).round_offsets().round_lengths()
                x = r.read(1, window=w2, boundless=True, fill_value=0, out_shape=shape).astype("float32")
            a = x if a is None else np.where(a > 0, a, x)
            used.append({"id": it["id"], "date": d, "fetched": now(),
                         "url": f"{PC}/stac/v1/collections/sentinel-1-rtc/items/{it['id']}"})
        cover = float((a > 0).mean())
        a[a <= 0] = np.nan
        out[d] = median_filter(np.nan_to_num(10 * np.log10(a), nan=-30.0), size=SPECKLE)
        print(f"{d}: {len(frames)} frames, {cover:.0%} covered")
    return out, grid, shape, crs


def on_grid(url: str, grid, shape, crs, resampling) -> np.ndarray:
    dst = np.full(shape, np.nan, "float32")
    with rasterio.Env(**GDAL_ENV), rasterio.open(url) as r:
        reproject(rasterio.band(r, 1), dst, dst_transform=grid, dst_crs=crs, dst_nodata=np.nan, resampling=resampling)
    return dst


def hand(e: Event, grid, shape, crs) -> np.ndarray:
    """HAND from every 1° tile the box touches (tiles are named by their south-west corner)."""
    w, s, east, n = e.bbox
    h = np.full(shape, np.nan, "float32")
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(east) + 1):
            tile = on_grid("/vsicurl/" + HAND_URL.format(lat=lat, lon=-lon), grid, shape, crs, Resampling.bilinear)
            h = np.where(np.isnan(h), tile, h)
    if np.isnan(h).mean() > 0.01:
        raise SystemExit("HAND does not cover the area")
    return h


def occurrence(e: Event, grid, shape, crs) -> tuple[np.ndarray, str]:
    """JRC occurrence; the asset needs the Planetary Computer's sign endpoint (the collection token gives 403)."""
    w, _, _, n = e.bbox
    url = JRC_URL.format(lon=10 * math.ceil(-w / 10), lat=10 * math.ceil(n / 10))
    signed = requests.get(f"{PC}/sas/v1/sign", params={"href": url}, timeout=60).json()["href"]
    occ = on_grid(signed, grid, shape, crs, Resampling.nearest)
    occ[(occ > 100) | np.isnan(occ)] = 0
    return occ, url


def run(e: Event) -> None:
    used: list[dict] = []
    vv, grid, shape, crs = vv_stack(e, used)
    h = hand(e, grid, shape, crs)
    occ, jrc = occurrence(e, grid, shape, crs)
    e.cache.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(e.cache / "inputs.npz", hand=h, occ=occ, transform=np.array(grid)[:6], crs=crs,
                        **{f"vv_{d}": a for d, a in vv.items()})
    e.data.mkdir(parents=True, exist_ok=True)
    (e.data / "inputs.json").write_text(json.dumps({
        "grid": {"crs": crs, "transform": list(grid)[:6], "shape": list(shape), "pixel_m": 10},
        "sentinel1_rtc": used,
        "hand": {"url": "https://glo-30-hand.s3.amazonaws.com/", "fetched": now()},
        "jrc_occurrence": {"url": jrc, "fetched": now()},
    }, indent=2))
    print(f"cached {e.cache / 'inputs.npz'} ({shape[1]} × {shape[0]} px)")


def cached(e: Event) -> tuple[dict, np.ndarray, np.ndarray, rasterio.Affine, str]:
    z = np.load(e.cache / "inputs.npz")
    vv = {k[3:]: z[k] for k in z.files if k.startswith("vv_")}
    return vv, z["hand"], z["occ"], rasterio.Affine(*z["transform"]), str(z["crs"])
