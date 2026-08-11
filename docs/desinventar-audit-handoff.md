# DesInventar pipeline audit — handoff

**Status:** investigation complete, no fixes applied yet.
**Scope:** full local re-extraction of all 100 DesInventar country codes (7 Aug 2026 run).
**Everything below was measured, not estimated.** All database access was read-only.

---

## Why this was done

Two escalations from Algo8, who consume Montandon for forecasting work:

1. *"African DesInventar records collapse after 2023 — 202 events in 2024, 89 in 2025. Is this a
   reporting lag we should account for?"*
2. *"Collection counts don't reconcile."*

The job was to establish which reported problems are genuine source problems and which are our own
data-pulling gaps.

## Verdicts

| Claim | Verdict |
|---|---|
| Recent-year collapse in Africa | **Not real.** A fresh pull has **22,390** events for Africa 2024 against their 202. They were querying stale staging. DesInventar has **no cron entry** in `main/cronjobs.py`, so nothing has re-extracted it since the one-off historical run. |
| Counts don't reconcile | **True, and it is ours.** 39.1% of source rows never become events. |
| Niger over-represented | **Not a bug.** DesInventar stores one row per affected administrative unit; globally 2.5 rows per episode. Group by `corr_id` for disaster counts. |
| Sparse impact figures | **Not a bug.** 1.13 impact records per event out of 14 possible fields — the source records *that* a disaster happened far more often than *how much* damage it caused. |

## The headline

**908,446 source rows → 553,062 events.** 355,384 lost, of which **354,039 are our defects**, not
source problems. Every affected transform was marked `SUCCESS`.

Root enabler: `apps/etl/transform/sources/desinventar.py` overrides `handle_transformation` and calls
`mark_as_ended(SUCCESS)` unconditionally. It never applies the `TRANSFORM_SUCCESS_RATE` check that
the shared base handler uses (`apps/etl/transform/sources/handler.py:126`). That is why countries
losing 100% of their data still look healthy.

## The five defects

| # | Rows | Defect |
|---|---|---|
| 1 | 230,299 | Hazard names matched case- and space-sensitively against a 53-entry dict |
| 2 | 71,629 | Empty string `""` rejected as a float → Ecuador loses 100% |
| 3 | 41,121 | 11 countries downloaded but never dispatched to the transformer |
| 4 | 10,990 | One unreadable shapefile silently voids an entire country |
| 5 | 1,345 | Bad dates / missing XML fields (genuine source problems) |

### 1 — Hazard vocabulary (230,299 rows)

`hazard_mapping` in `libs/pystac-monty/pystac_monty/sources/desinventar.py` is an exact-match dict
on uppercase strings. The `nombre_en` field in the archives is free text entered independently by
each national agency over three decades, so the same hazard arrives as `FOREST FIRE`, `FORESTFIRE`,
`Forest fire`, `WILD FIRE`.

Three groups:

- **65,368 — pure formatting variants of keys that already exist.** `FORESTFIRE` (18,766),
  `STRONGWIND` (11,584), `FLOODS` (10,449), `LANDSLIDES` (6,069), plus title-case forms.
  Normalising the lookup recovers these with zero judgement calls. Lebanon loses 100% of its rows
  purely because its vocabulary is title-case.
- **132,200 — hazards genuinely absent from the taxonomy.** `MENINGITIS` (27,946), `ROAD ACCIDENT`,
  `ANIMAL ATTACK`, `MEASLE`. **Needs an IFRC/Algo8 decision, not a code change.**
- **32,706 — entries deliberately mapped to `None`** (`PLAGUE`, `POLLUTION`, `OTHER`, `PANIC`,
  `FAMINE`). Working as designed, but currently invisible.

### 2 — Empty numeric fields (71,629 rows — all of Ecuador)

`DataRow` in `libs/pystac-monty/pystac_monty/validators/desinventar.py` declares impact fields as
`float | None`. Ecuador writes `<reubicados></reubicados>` for unrecorded values; SAX yields `""`;
pydantic rejects `""` and will not coerce it to `None`. The `ValidationError` fires before any field
of the row is used.

It is 100% of the country because every Ecuadorian row has at least one blank numeric field. Other
countries write `0` instead — it is a per-country data-entry convention, so this is a landmine for
whoever formats their data this way.

### 3 — Never dispatched (41,121 rows)

11 countries have `resp_code = 200`, `status = SUCCESS`, and **no `Transform` row at all** — not
failed, never created: `tur tza vct vnm xkx yem zmb znz 019 033 005`. India's three regional
databases alone account for 30,488 events.

The dispatch code in `apps/etl/extraction/sources/desinventar/extract.py` looks correct, and these
are the tail of the run by extraction ID, with the queue backed up behind Sri Lanka (43 min) and
Niger (35 min). Most likely the transform queue was cut off mid-drain. **Mechanism inferred, not
proven.**

Regardless of cause, nothing recovers them: `trigger_pending_extraction` (`apps/etl/tasks.py`) only
re-fires *extractions* stuck in PENDING. Nothing anywhere looks for a successful extraction that has
no transform.

### 4 — One bad shapefile voids a country (10,990 rows)

In `libs/pystac-monty/pystac_monty/sources/desinventar.py`:

```python
@contextmanager
def with_xml_file(self):
    xml_file = None
    try:
        with ZipFile(...) as zf_ref:
            xml_file = zf_ref.open(f"DI_export_{self.country_code}.xml")
            yield xml_file        # the entire transform runs here
    except Exception:
        xml_file = None           # and every error it raises is swallowed here
```

Because the `yield` sits inside the `try`, any exception raised by the caller's body is thrown back
into the generator by `contextlib` and suppressed by the bare `except`. `get_stac_items` is itself a
generator, so it simply stops — 0 items, `{"total_rows": 0, "failed_rows": 0}`, marked `SUCCESS`.

What throws is `_generate_geo_data_mapping`, which has no per-level `try`, so the first bad admin
level kills the whole country — even though **level 0 loaded fine in every case**:

| Country | Rows lost | Trigger |
|---|---|---|
| `syr` | 7,326 | `Regions.shp` + `Sub_Regions.shp` have unclosed LinearRings → `GEOSException` |
| `mdv` | 2,825 | Archive ships no shapefiles *and* every `<filename>` is `""` |
| `som` | 1,374 | `som_admbnda_adm2_mohadm.shp` has a corrupt `.dbf` date → `ValueError: year -1` |
| `mar` | 735 | `<filename>` names `Regions.shp` etc., archive contains only the XML |

**This is not intended behaviour.** The code explicitly supports a missing shapefile: there is an
`else: shapefile_data = None` branch, and the consumer `_get_geojson_and_bbox_from_row` handles
`gfd is None` by returning `(None, None)` and continuing. The author guarded `file_path is None` but
never anticipated `""` or a file that exists and won't parse. The proof it is unintended is the
inconsistency — the same condition currently produces four different outcomes: continue cleanly
(`None`), silently load the **wrong** layer (`""` where the archive has layers — Somalia's level 2
loaded level 0's shapefile), or crash in two different ways.

> ### ⚠️ Defects 3 and 4 must be fixed together
> `019` (India, 12,746 valid rows) and `xkx` (Kosovo, 1,510) ship **no shapefiles at all**. They
> escaped defect 4 only because defect 3 meant they were never processed. **Fixing dispatch alone
> silently destroys 14,256 more events** — and worse, they would then look like they had worked.
>
> Verified across all 96 archives: only `019`, `blr`, `mar`, `mdv`, `xkx` have no shapefiles, and
> `blr` has no rows anyway. The other nine never-dispatched countries load cleanly.

### 5 — Genuine source problems (1,345 rows)

- **1,142 unparseable dates.** `DataRow.year` has no bounds validation; the source year range spans
  **0 to 2310**, and 6,099 rows sit outside 1900–2026.
- **203 `KeyError`s.** `parse_row_data` uses direct indexing (`event_data["di_comments"]`), so a
  `<TR>` that omits a tag raises.
- Myanmar's XML is malformed (`not well-formed`, line 7139) and yields nothing. Belarus and Laos
  publish empty databases.

## Fix order

| # | Fix | Recovers | Notes |
|---|---|---|---|
| 1 | Coerce `""` → `None` on `DataRow` numeric fields | 71,629 | Trivial |
| 2 | Normalise hazard lookup (case / space / plural) | 65,368 | Trivial |
| 3 | Dispatch the 11 skipped countries | 41,121 | **Do together with #4** |
| 4 | Guard empty `filename`; `try/except` per admin level | 10,990 (+14,256 protected) | **Do together with #3** |
| 5 | Stop swallowing exceptions in `with_xml_file` | — | Move the `yield` out of the `try` |
| 6 | Apply `TRANSFORM_SUCCESS_RATE` to DesInventar | — | Stops the next regression hiding |
| 7 | Extend hazard taxonomy (421 names) | 132,200 | **Needs IFRC/Algo8 decision** |
| 8 | Bounds-check `DataRow.year` | 6,099 flagged | Trivial |

Items 1–4 are mechanical and recover **189,108 rows — a 34% increase** on the current collection,
with no taxonomy judgement required.

Also outstanding:

- Four permanently-404 country codes: `prt`, `etm`, `mal`, `sy11`.
- `apps/etl/etl_tasks/desinventar.py:143` passes `country_code` where the mapped `iso3` belongs, so
  India's regional exports get `iso3="019"` / `"033"` / `"005"` instead of `IND`. The unpacked
  `iso3` loop variable is never used.
- The site publishes `lao2` (28 MB) while the pipeline pulls `lao` (1.4 MB) — likely a superseded
  database. `ar2` and `ng_oy` are also published and not fetched.

## Geometry — read before touching the fallback

A country-level fallback was added to `_create_event_item_from_row`: when the per-row admin lookup
finds nothing, it falls back to `get_geometry_from_iso3(self.data_source.iso3)`.

**It works, and it is now load-bearing: 351,498 of 553,062 events (63.6%) carry a whole-country
polygon.** 42 of 73 countries are 100% on it; zero events have null geometry. Verified two ways — a
no-op-geocoder run agrees with a largest-bbox analysis on 17 of 18 countries, exact to the row.

Two consequences:

1. **It fires far more than intended.** `DataRow.lowest_level` tests `is not None`, but the XML
   supplies empty strings, so it almost always claims `"level2"` and hunts for a level-2 shapefile
   that frequently does not exist. Fixing that would return a large share of these events to real
   admin geometry.
2. **It is a single point of failure.** `TheirGeocoder._request` has no exception handling, so a
   geocoder outage raises `ConnectionError` into the transformer's catch-all and the row is counted
   as *failed*. The geocoder was reachable during the 7 Aug run and is down now — re-running today
   would turn those 351,498 events into failures rather than merely imprecise ones. **Wrap the call
   so an outage degrades to "no geometry" instead of "no data",** and consider tagging
   fallback-derived items so consumers can tell a national outline from a real location.

## Warnings for anyone modelling this data

- **Do not read trends from the current collection.** Retention rises from 44% (2015) to 89% (2024),
  because older records disproportionately use the unmatched hazard vocabularies. That gradient
  manufactures a strong upward trend in disaster counts that is purely our artefact.
- **Do not treat locations as precise** — roughly 64% are whole-country polygons (see above).

## How to reproduce

Two **read-only** management commands (neither writes to the database):

```bash
docker compose exec web python manage.py export_desinventar_eda      # ~15 min, 1.18M items
docker compose exec web python manage.py audit_desinventar_source    # ~9 min, re-parses 7.3 GB XML
```

Output lands in `data/desinventar_eda/`:

| File | Grain |
|---|---|
| `pipeline.csv` | one row per country code — extraction and transform outcome |
| `items.parquet` | one row per STAC item (1.18M), flattened from `PyStacLoadData.item` |
| `source_audit.csv` | one row per country — rows, kept, and each failure reason |
| `hazard_unmapped.csv` | every unmatched hazard name, with a normalisation hint |

`audit_desinventar_source` is the important one. The database only records `total_rows` /
`failed_rows`, so it can tell you *how many* rows died but never *why*. The command re-parses each
stored archive with a streaming SAX pass and replays the transformer's own decision path
(`parse_row_data` → `event_start_date` → `hazard_mapping`), attributing every dropped row to the
branch that actually rejected it.

> **Do not reuse the in-house STAC upload script for exports.** It flips `PyStacLoadData.status` to
> `SUCCESS` as it writes, which is correct when draining the load queue but would mark 1.18M items
> as loaded to eoAPI when they never were. The export command here deliberately omits that write.

### Notebooks

- `notebooks/desinventar_eda.ipynb` — working notebook, full analysis. Includes an `assert` that the
  loss categories reconcile exactly to the database count, so it fails loudly if anything drifts.
- `notebooks/desinventar_findings.ipynb` — stakeholder version, 8 charts, story-led.

Neither the host nor the container ships jupyter:

```bash
cd notebooks
uv run --no-project --python 3.12 --with pandas --with pyarrow --with matplotlib \
  --with jupyterlab jupyter lab

# to share without showing code:
jupyter nbconvert --to html --no-input desinventar_findings.ipynb
```

## Environment notes

- The container writes as root, so `data/desinventar_eda/` is root-owned. `chown` it before the
  notebook needs write access there.
- All 1,179,421 items sit at `status = PENDING` because `EOAPI_STAC_API_INTERNAL` is unset locally.
  **That is a local-only artefact, not a finding** — nothing is pushed to staging or production from
  a dev box.
- `main/cronjobs.py` on the sandbox branch has most schedules commented out deliberately, to stop
  beat firing every source during testing. **Do not merge that upstream** — the file's own comment
  notes that removing entries deletes the `PeriodicTask` rows from the database.

## Open questions

1. **Does staging show the same defects?** Everything here is from a local run. Algo8 seeing 54
   countries against our 73 strongly suggests yes, but it is unverified.
2. **Root cause of defect 3** — queue cut-off is inferred from the ID ordering, not proven.
3. **Taxonomy decision on the 421 unmapped hazard names** — does this collection include road
   accidents, animal attacks, meningitis and measles outbreaks? This blocks 132,200 rows and is not
   ours to decide.
