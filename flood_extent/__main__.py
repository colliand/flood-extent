"""python -m flood_extent <command> <event>

    read       EVENT   Sentinel-1 passes, HAND and JRC water on one 10 m grid → cache/EVENT/ (gitignored), data/EVENT/inputs.json
    estimate   EVENT   open floodwater → data/EVENT/estimate.geojson, summary.json (range, steps, sensitivity)
    check      EVENT   FEMA flood zones and towns → data/EVENT/check.json, fema_zones.geojson
    quicklook  EVENT   radar images of the zoom window → data/EVENT/radar-*.jpg
"""
import sys

from . import check, estimate, quicklook, read
from .event import load


def main(argv):
    if len(argv) != 2 or argv[0] not in ("read", "estimate", "check", "quicklook"):
        raise SystemExit(__doc__)
    {"read": read.run, "estimate": estimate.run, "check": check.run, "quicklook": quicklook.run}[argv[0]](load(argv[1]))


if __name__ == "__main__":
    main(sys.argv[1:])
