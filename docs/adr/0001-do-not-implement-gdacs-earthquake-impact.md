---
status: proposed
date: 2026-07-05
deciders: [Ranjan Shrestha]
---

# 0001. Do not implement GDACS earthquake impact ingestion

## Context and Problem Statement

`GDACSTransformer.make_impact_items` (`libs/pystac-monty/pystac_monty/sources/gdacs.py`)
builds impact STAC items per hazard type: `HazardType.TC` reads a numeric
`pop` field off each `TCImpactItem`, and `HazardType.WF` reads a `POPAFFECTED`
scalar out of the population (`POP`) datum group. `HazardType` itself
(same file) only defines `TC` and `WF`, with a `# TODO: Fill in with more
hazard types` comment, and `make_impact_items` has no `case` for earthquakes
(`EQ`) — so GDACS earthquake events currently produce only event and hazard
items, never impact items.

Before adding an `EQ` branch, we checked whether GDACS's earthquake data
actually carries a usable "people affected" figure, the way TC and WF do:

- Event data (`geteventdata?eventtype=EQ&eventid=1526507`) has an `impacts`
  object with a `source` and a `resource` dict of links (`impact`,
  `shake_preliminary`, `shakemap`) — no numeric affected-population field
  lives on the event payload itself. The only population numbers present are
  in `earthquakedetails` (`shakepop`, `rapidpop`), which are modeled
  population *exposed to a shaking intensity level*, not an assessed
  affected/casualty count.
- The `impact` resource link resolves to the impact export
  (`export/getimpact?id=736987`). That payload is a set of per-province,
  per-alert-zone, per-city, and per-airport `datum` records. It does contain
  `POP_AFFECTED`-shaped scalars, but in the sampled event every one of them
  was `0` — consistent with this being pre-event/predictive exposure
  modeling output rather than a reported impact figure.

So, unlike TC's `pop` and WF's `POPAFFECTED`, GDACS does not expose a field
for earthquakes that represents an actual assessed number of people affected.
EM-DAT (`libs/pystac-monty/pystac_monty/sources/emdat.py`) and USGS
(`libs/pystac-monty/pystac_monty/sources/usgs.py`) already ingest earthquake
hazard/impact data independently of GDACS, so this gap does not leave
earthquakes without any impact-numbers source in the pipeline overall.

## Considered Options

- Implement `HazardType.EQ` using `shakepop`/`rapidpop` as a proxy for people
  affected.
- Implement `HazardType.EQ` by consuming the `impact` resource link and
  taking whatever `POP_AFFECTED`-shaped scalar is present, when non-zero.
- Do not implement GDACS earthquake impact ingestion for now.

## Decision Outcome

Chosen: **Do not implement GDACS earthquake impact ingestion**, because
neither `shakepop`/`rapidpop` nor the `impact` export's `POP_AFFECTED`-shaped
scalars represent an assessed people-affected count — the former is
shaking-intensity population exposure and the latter was `0` in the data we
checked. Populating `ImpactDetail.value` from either would present modeled
exposure or an empty placeholder as if it were a real impact figure, which is
inconsistent with how `ImpactDetail` is populated for every other hazard type
in this transformer (Sendai entries, TC's `pop`, WF's `POPAFFECTED` are all
reported or model-estimated values tied to an actual impact indicator).

## Consequences

- Good: GDACS-sourced STAC items never claim an earthquake impact number that
  isn't backed by real impact data.
- Good: no impact-parsing code path is added and maintained for a field that,
  in the data observed, cannot be populated with a meaningful value.
- Bad: GDACS earthquake events surface only as event/hazard items, with no
  GDACS-sourced impact item — total impact coverage for earthquakes depends
  on the EM-DAT and USGS transformers rather than GDACS.
- Revisit if: GDACS starts publishing an earthquake field that represents an
  assessed affected/casualty count (a populated `POP_AFFECTED`, or an
  equivalent field on the `impact` resource) rather than shaking-exposure
  modeling output.
