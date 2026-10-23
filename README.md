# flood-extent

Open floodwater from Sentinel-1 radar, by change detection, checked against FEMA flood zones. One config file per
event (`events/<id>.json`). Built for [whatcom.land](https://whatcom.land/floods), whose Floods tab shows the November
2021 Nooksack flood. Events so far:

- `nooksack-2021-11`: the Nooksack River flood of 16 November 2021, Whatcom County, Washington
  ([methods/nooksack-2021-11.md](methods/nooksack-2021-11.md); note:
  [notes.colliand.com](https://notes.colliand.com/nooksack-flood-2021/)).

Floods come with cloud, and radar sees through cloud. Calm open water reflects the radar pulse away from the satellite
like a mirror, so it looks dark; fields, forest and towns scatter some of it back. A field that was bright on every pass
before the flood and is dark on the flood pass has most likely gone under water.

    uv run python -m flood_extent read nooksack-2021-11       # radar, HAND, JRC water on a 10 m grid → cache/ (gitignored)
    uv run python -m flood_extent estimate nooksack-2021-11   # → data/nooksack-2021-11/estimate.geojson, summary.json
    uv run python -m flood_extent check nooksack-2021-11      # FEMA zones and towns → check.json, fema_zones.geojson
    uv run python -m flood_extent quicklook nooksack-2021-11  # radar images of the worst-hit area → radar-*.jpg

**Method** (`flood_extent/estimate.py`): Sentinel-1 RTC (terrain-corrected backscatter, VV, 10 m) from one orbit track,
5 × 5 median filter for speckle. "Normal" is the median of the pre-flood passes. Floodwater = VV < −18 dB on the flood
pass AND at least 3 dB darker than normal AND not permanent water (dark on any pre-flood pass, or JRC occurrence ≥ 50%)
AND less than 10 m above the nearest stream (HAND), inside the county; patches under 0.5 ha dropped. The estimate is
repeated at −19 and −17 dB for a range, and each other setting is moved one step on its own (`sensitivity_acres` in
`summary.json`).

**What it is not**: a flood map. Radar misses water among buildings and under trees, and one pass is one moment. The
FEMA check (`check.json`) asks whether the water fell where floods are expected; it is a plausibility check, not
validation.

Data: Sentinel-1 RTC by Catalyst via Microsoft Planetary Computer (contains modified Copernicus Sentinel data; CC BY
4.0); ASF GLO-30 HAND from the Copernicus DEM GLO-30; JRC Global Surface Water v1.3 (Pekel et al. 2016); FEMA National
Flood Hazard Layer (public domain); US Census TIGERweb county boundaries (public domain).

## Licence

Open and permissively shared:

- **Code** (`flood_extent/`): [MIT](LICENSE).
- **Data, figures and text** made here (`data/`, `methods/`, this README):
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Reuse freely with credit.
- Inputs keep their own terms: Sentinel-1 RTC (CC BY 4.0, "contains modified Copernicus Sentinel data"); Copernicus
  DEM GLO-30 (© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the
  European Union and ESA); JRC Global Surface Water (CC BY 4.0); FEMA NFHL and TIGERweb (public domain).
  `data/*/fema_zones.geojson` is FEMA's layer, dissolved into four classes and clipped to the event box.

Cite as: Colliander, J. (2026). *flood-extent: open floodwater from Sentinel-1 radar by change detection.*
https://github.com/colliand/flood-extent
