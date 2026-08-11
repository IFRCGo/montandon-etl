"""
Export DesInventar pipeline data to flat files for exploratory analysis.

READ-ONLY: this command never writes to the database. It deliberately does *not*
mark rows as loaded — unlike the STAC upload path, which flips
PyStacLoadData.status to SUCCESS as it drains the queue. Exporting for analysis
must not consume the load queue.

Usage (inside the container, so it can reach the DB and the stored archives):

    docker compose exec web python manage.py export_desinventar_eda

Writes to ./data/desinventar_eda/ (bind-mounted, so the files land on the host):

    pipeline.csv   one row per country code: extraction + transform outcome
    items.parquet  one row per STAC item, flattened for pandas
    items.csv      same, only when --csv is passed (large)
"""

import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.etl.models import ExtractionData, PyStacLoadData, Transform

DEFAULT_OUT = Path("data/desinventar_eda")

ITEM_COLUMNS = [
    "item_id",
    "collection_id",
    "item_type",
    "country_code",
    "iso3_meta",
    "monty_country_code",
    "corr_id",
    "src_event_id",
    "episode_number",
    "start_datetime",
    "year",
    "hazard_codes",
    "hazard_code_primary",
    "title",
    "has_geometry",
    "geometry_type",
    "bbox_minx",
    "bbox_miny",
    "bbox_maxx",
    "bbox_maxy",
    "impact_type",
    "impact_category",
    "impact_value",
    "impact_unit",
    "impact_estimate_type",
]


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _flatten(pystac_obj, country_code, iso3_meta):
    item = pystac_obj.item or {}
    props = item.get("properties") or {}
    geometry = item.get("geometry")
    bbox = item.get("bbox") or []
    impact = props.get("monty:impact_detail") or {}
    start = props.get("start_datetime") or props.get("datetime")

    year = None
    if isinstance(start, str) and len(start) >= 4 and start[:4].isdigit():
        year = int(start[:4])

    hazard_codes = props.get("monty:hazard_codes") or []

    return {
        "item_id": item.get("id"),
        "collection_id": pystac_obj.collection_id,
        "item_type": PyStacLoadData.ItemType(pystac_obj.item_type).label if pystac_obj.item_type else None,
        "country_code": country_code,
        "iso3_meta": iso3_meta,
        "monty_country_code": _first(props.get("monty:country_codes")),
        "corr_id": props.get("monty:corr_id"),
        "src_event_id": props.get("monty:src_event_id"),
        "episode_number": props.get("monty:episode_number"),
        "start_datetime": start,
        "year": year,
        "hazard_codes": "|".join(hazard_codes) if hazard_codes else None,
        "hazard_code_primary": hazard_codes[0] if hazard_codes else None,
        "title": props.get("title"),
        "has_geometry": geometry is not None,
        "geometry_type": (geometry or {}).get("type") if isinstance(geometry, dict) else None,
        "bbox_minx": bbox[0] if len(bbox) == 4 else None,
        "bbox_miny": bbox[1] if len(bbox) == 4 else None,
        "bbox_maxx": bbox[2] if len(bbox) == 4 else None,
        "bbox_maxy": bbox[3] if len(bbox) == 4 else None,
        "impact_type": impact.get("type"),
        "impact_category": impact.get("category"),
        "impact_value": impact.get("value"),
        "impact_unit": impact.get("unit"),
        "impact_estimate_type": impact.get("estimate_type"),
    }


class Command(BaseCommand):
    help = "Export DesInventar pipeline data to flat files for EDA (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory")
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--limit", type=int, default=None, help="Cap items exported (for a quick smoke run)")
        parser.add_argument("--csv", action="store_true", help="Also write items.csv (large)")

    def handle(self, *args, **options):
        out_dir = Path(options["out"])
        out_dir.mkdir(parents=True, exist_ok=True)
        source = ExtractionData.Source.DESINVENTAR

        self._export_pipeline(out_dir, source)
        self._export_items(out_dir, source, options)

        self.stdout.write(self.style.SUCCESS(f"\nDone -> {out_dir.resolve()}"))
        self.stdout.write("No database rows were modified.")

    # -- per-country pipeline outcome -------------------------------------
    def _export_pipeline(self, out_dir, source):
        path = out_dir / "pipeline.csv"
        rows = []
        extractions = ExtractionData.objects.filter(source=source).order_by("id")
        transforms = {t.extraction_id: t for t in Transform.objects.filter(extraction__source=source)}

        for ext in extractions:
            params = (ext.metadata or {}).get("params") or {}
            transform = transforms.get(ext.id)
            summary = ((transform.metadata or {}).get("summary") or {}) if transform else {}
            total = summary.get("total_rows") or 0
            failed = summary.get("failed_rows") or 0
            rows.append(
                {
                    "country_code": params.get("country_code"),
                    "iso3_meta": params.get("iso3"),
                    "url": ext.url,
                    "extraction_status": ExtractionData.Status(ext.status).label if ext.status else None,
                    "resp_code": ext.resp_code,
                    "has_transform": transform is not None,
                    "transform_status": Transform.Status(transform.status).label if transform else None,
                    "total_rows": total,
                    "failed_rows": failed,
                    "kept_rows": max(total - failed, 0),
                    "loss_pct": round(100 * failed / total, 2) if total else None,
                }
            )

        with open(path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["country_code"])
            writer.writeheader()
            writer.writerows(rows)

        never = sum(1 for r in rows if not r["has_transform"])
        self.stdout.write(f"pipeline.csv    {len(rows)} country codes ({never} without a transform)")

    # -- one row per STAC item --------------------------------------------
    def _export_items(self, out_dir, source, options):
        batch_size = options["batch_size"]
        limit = options["limit"]

        country_by_transform = {}
        for transform in Transform.objects.filter(extraction__source=source).select_related("extraction"):
            params = (transform.extraction.metadata or {}).get("params") or {}
            country_by_transform[transform.id] = (params.get("country_code"), params.get("iso3"))

        qs = PyStacLoadData.objects.filter(transform_id__in=country_by_transform.keys()).order_by("id")
        total = qs.count() if limit is None else min(qs.count(), limit)
        self.stdout.write(f"items           exporting {total:,} items...")

        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            pa = pq = None
            self.stdout.write(self.style.WARNING("pyarrow missing - writing JSONL instead of parquet"))

        writer = None
        jsonl = None
        csv_writer = None
        csv_fh = None
        buffer = []
        written = 0

        if pq is None:
            jsonl = open(out_dir / "items.jsonl", "w")
        if options["csv"]:
            csv_fh = open(out_dir / "items.csv", "w", newline="")
            csv_writer = csv.DictWriter(csv_fh, fieldnames=ITEM_COLUMNS)
            csv_writer.writeheader()

        def flush():
            nonlocal buffer, writer
            if not buffer:
                return
            if pq is not None:
                table = pa.Table.from_pylist(buffer)
                if writer is None:
                    writer = pq.ParquetWriter(out_dir / "items.parquet", table.schema)
                writer.write_table(table)
            buffer = []

        for pystac_obj in qs.iterator(chunk_size=batch_size):
            if limit is not None and written >= limit:
                break
            country_code, iso3_meta = country_by_transform.get(pystac_obj.transform_id_id, (None, None))
            record = _flatten(pystac_obj, country_code, iso3_meta)
            buffer.append(record)
            if csv_writer:
                csv_writer.writerow(record)
            if jsonl:
                jsonl.write(json.dumps(record, default=str) + "\n")
            written += 1
            if len(buffer) >= batch_size:
                flush()
                pct = 100 * written / total if total else 0
                print(f" - exporting ({written:,}/{total:,}) ({pct:.1f}%)", end="\r")

        flush()
        if writer:
            writer.close()
        if jsonl:
            jsonl.close()
        if csv_fh:
            csv_fh.close()

        print("")
        target = "items.parquet" if pq is not None else "items.jsonl"
        self.stdout.write(f"{target:15} {written:,} items")
