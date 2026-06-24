# Reproducing the Texty Kyiv strike heatmap

## What the original visual actually measures

The supplied graphic is from Texty.org.ua's article [“Понад три роки під обстрілами. Де і коли в Києві прилітає найбільше”](https://texty.org.ua/articles/115345/kyyiv-ponad-try-roky-pid-obstrilom-de-i-koly-prylitaye-najbilshe/), published 23 June 2025.

It maps documented Kyiv locations damaged by UAVs, cruise and ballistic missiles, and debris between 24 February 2022 and 23 June 2025. The article says that only officially reported impacts are represented. The graphic cites the Ukrainian Wikipedia article [“Обстріли Києва”](https://uk.wikipedia.org/wiki/%D0%9E%D0%B1%D1%81%D1%82%D1%80%D1%96%D0%BB%D0%B8_%D0%9A%D0%B8%D1%94%D0%B2%D0%B0) plus Texty's calculations.

This is **not an air-alert map**. The downloaded alert CSV contains alert time intervals and administrative geography, but no impact coordinates or damage records. It can support a related map of alert frequency/duration, not the point heatmap shown in the reference.

## Two useful reproduction targets

### A. Faithful reconstruction of Texty's analysis

Use a second incident table containing one row per documented damage location:

```text
incident_id
attack_datetime_local
latitude
longitude
kyiv_district
weapon_type
damage_description
killed
injured
source_url
source_confidence
```

The Wikipedia article already contains yearly tables with date, place, coordinates, weapon, casualties, damage and citations. To match the 2025 graphic, begin from the last article revision available before publication: [revision 45504336 from 18 June 2025](https://uk.wikipedia.org/w/index.php?title=%D0%9E%D0%B1%D1%81%D1%82%D1%80%D1%96%D0%BB%D0%B8_%D0%9A%D0%B8%D1%94%D0%B2%D0%B0&oldid=45504336), then verify and supplement the final days against sources cited by Texty.

Recommended pipeline:

1. Fetch and archive the fixed Wikipedia revision rather than the changing current page.
2. Parse the yearly HTML tables.
3. Normalize timestamps to `Europe/Kyiv` and decimal coordinates to WGS84.
4. Split rows that describe multiple distinct locations; do not multiply one location merely because several buildings were damaged there.
5. Classify weapons into UAV, cruise missile, ballistic missile, debris, artillery/other and unknown.
6. Retain only records meeting the chosen definition of a documented Kyiv impact/damage location.
7. Manually audit ambiguous coordinates and duplicate reports from the same attack.
8. Save a clean incident CSV plus a rejected/ambiguous-record log.
9. Render black incident points and a red kernel-density layer over a muted Kyiv basemap.
10. Validate totals by date, district and weapon class against the article's charts and narrative.

### B. A new alert-intensity visual using our downloaded CSV

This would answer a different question: where and when alerts occurred most frequently or lasted longest.

Possible metrics:

- count of alert intervals;
- total alert hours;
- share of time under alert;
- alerts per month;
- median alert duration;
- change before/after the December 2025 shift toward raion-level reporting.

Because the CSV identifies oblasts, raions and hromadas rather than exact points, this should be a choropleth or administrative-area heatmap. Placing every alert at an area centroid would create false geographic precision and should be avoided.

## Visual recipe

For a static graphic close to the reference, use Python with GeoPandas, Matplotlib, SciPy/Datashader and a legally reusable basemap.

- Projection: calculate density in a metric CRS such as UTM zone 36N (`EPSG:32636`), then render in the basemap's CRS.
- Marks: black circles, approximately 2–4 px at final output size.
- Density: Gaussian KDE, initially test bandwidths around 750 m, 1 km and 1.5 km; select one before looking at the final narrative conclusions.
- Color: transparent pale coral through saturated red/dark crimson; keep zero-density areas fully transparent.
- Basemap: near-white land, very light gray roads/buildings, slightly darker gray water; no colorful commercial tiles.
- Layout: large Ukrainian serif headline and subtitle at top; small sans-serif source, legend and caveat text at the bottom.
- Output: render both SVG/PDF for editing and a 2× PNG for publication.

The heat layer should be based on counts of documented locations. Casualties, damaged-building counts and weapon counts should remain separate variables unless the legend explicitly says they are used as weights.

## Accuracy traps

1. A hotspot is a concentration of **documented reports**, not necessarily a true attack probability surface.
2. Official reporting is incomplete and spatially selective; sensitive targets may be omitted or generalized.
3. Multiple records from one attack can describe separate impacts, repeated reporting of one impact, or one broad damage zone. Deduplication rules must be explicit.
4. KDE bandwidth materially changes the apparent hotspots. Publish the value and perform a sensitivity check.
5. Exact public coordinates of recent damage may carry safety concerns. For a current publication, consider aggregation, coarser cells or a time delay.
6. Do not join alert intervals to strike points as if every alert caused a documented impact. At most, test temporal association with a stated matching window.

## Reuse and attribution

Texty states that its material is available under CC BY and asks reusers to place a hyperlink in the first or second paragraph. Wikipedia content is separately licensed under CC BY-SA. A reproduced graphic should attribute Texty, the fixed Wikipedia revision, the original incident sources and the basemap provider; any share-alike obligations should be checked for the particular distributed artifact/data extract.

## Recommended next implementation

Build the faithful incident pipeline first, producing:

```text
data/raw/kyiv_shelling_wikipedia_45504336.html
data/processed/kyiv_strike_locations.csv
reports/kyiv_strike_heatmap.png
reports/kyiv_strike_heatmap.svg
```

Then build a separate alert analysis from `data/raw/official_data_en.csv`. Keeping the two analyses separate avoids making the attractive but incorrect claim that alert frequency equals impact density.
