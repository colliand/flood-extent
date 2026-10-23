"""Radar images for the event's zoom window, for reading the method by eye (data/EVENT/radar-*.jpg):

  normal      the median of the pre-flood passes
  flood       the flood pass
  estimate    the flood pass with the estimate in teal

Grey scale: −25 dB (black) to 0 dB (white). Water is black in both; floodwater is what turned black."""
import numpy as np
from PIL import Image
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from .estimate import Scene
from .event import Event

LO, HI = -25.0, 0.0
TEAL = np.array([14, 138, 158])


def grey(db: np.ndarray) -> np.ndarray:
    g = (np.clip((db - LO) / (HI - LO), 0, 1) * 255).astype("uint8")
    return np.stack([g] * 3, axis=-1)


def run(e: Event) -> None:
    s = Scene(e)
    flood = np.load(e.cache / "flood.npy")
    w = from_bounds(*transform_bounds("EPSG:4326", s.crs, *e.zoom), transform=s.grid).round_offsets().round_lengths()
    w = w.intersection(from_bounds(*transform_bounds("EPSG:4326", s.crs, *e.bbox), transform=s.grid).round_offsets())
    sl = w.toslices()
    est = grey(s.post[sl]).astype(float)
    est[flood[sl]] = 0.35 * est[flood[sl]] + 0.65 * TEAL
    for name, rgb in [("normal", grey(s.normal[sl])), ("flood", grey(s.post[sl])), ("estimate", est.astype("uint8"))]:
        im = Image.fromarray(rgb)
        im.thumbnail((1000, 1000))
        im.save(e.data / f"radar-{name}.jpg", quality=82)
    print(f"wrote radar-*.jpg ({sl[1].stop - sl[1].start} × {sl[0].stop - sl[0].start} px at 10 m)")
