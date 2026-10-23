# Nooksack River flood, 16 November 2021

The first event, and the method behind the November 2021 view on [whatcom.land](https://whatcom.land/floods), first
built there on 2026-10-10 and moved here on 2026-10-23. Note: [notes.colliand.com](https://notes.colliand.com/nooksack-flood-2021/).

## The pass

Sentinel-1B, relative orbit 13 (descending), 16 Nov 2021 14:20 UTC (06:20 PST). The river had peaked at North
Cedarville (Everson) the day before and was near its record height at Ferndale. Normal = the median of the six passes
on the same track, 5 Sep – 4 Nov 2021. Both frames of each pass are stitched, or Sumas, at the border, falls off the edge.

## Result

About **8,600 acres** (34.6 km²) of open floodwater in Whatcom County; 6,500–10,200 with the water threshold at
−19 / −17 dB. whatcom.land's original run (2026-10-10) gave the same 8,600 and 6,500–10,300; the 100-acre difference at
the loose end is within rounding.

What each test leaves (acres): dark on the flood pass 26,015 → 3 dB darker than normal 16,314 → not permanent water
8,816 → HAND < 10 m 8,804 → patches ≥ 0.5 ha 8,557. The change test and the permanent-water mask do most of the work;
HAND removes little in these lowlands.

Sensitivity, one setting at a time (acres): change −2 / −4 dB → 8,600 / 8,500; HAND 5 / 15 m → 8,500 / 8,600; smallest
patch 10 / 200 px → 8,800 / 8,000. Only the water threshold moves the answer much.

## Checks

- 91.4% of the estimate inside FEMA's studied zones: floodway 37.5%, high risk 52.4%, moderate 1.5% (same as
  whatcom.land).
- Open water within 2 km of each town: Everson 3.8%, Nooksack 5.1%, Sumas 6.8%, Lynden 12.0%, Ferndale 8.8%. Low in the
  worst-hit towns: radar misses water among buildings (double bounce makes flooded streets bright), and Everson had
  begun to drain by 06:20.
- By eye (`radar-*.jpg`): the overflow band from Everson north-east to Sumas is caught; ponds south-west of Everson,
  dark on every pass, are correctly left out.

No official flood extent was published. USGS STN (event 314) has no high-water marks for this flood. FEMA zones are a
plausibility check only.

## Pitfalls met

- The first permanent-water mask let bays and lakes through. Fixed with: dark on ANY pre-flood pass (the minimum of the
  stack, for calm days) OR JRC Global Surface Water occurrence ≥ 50%.
- The JRC COG returns 403 with the collection token; sign the asset URL with the Planetary Computer sign endpoint.
- Dark hillsides are radar shadow, not water: the HAND limit removes them.
- GDAL reads need an HTTP timeout: on 2026-10-23 one stalled connection held a read for 40 minutes. The Planetary
  Computer served ~0.2 MB/s that afternoon, so `read` took 38 minutes; FEMA's NFHL dropped a connection, hence retries.

## Not done

The 20 Nov pass (recession) and the second flood of 28 Nov 2021. Water among buildings (double bounce).
