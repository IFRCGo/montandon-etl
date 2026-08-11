"""
Audit the DesInventar source archives against the transformer's own decision path.

READ-ONLY: reads the stored extraction archives and the database; writes nothing back.

The database only records `total_rows` / `failed_rows` per country. That tells you
*how many* rows were dropped, never *why*. This command re-parses each stored
archive with a streaming SAX pass and replays the exact branches the transformer
uses -- parse_row_data(), DataRow.event_start_date, and the hazard_mapping lookup
-- so every dropped row is attributed to the branch that actually rejected it.

Usage:

    docker compose exec web python manage.py audit_desinventar_source

Writes to ./data/desinventar_eda/:

    source_audit.csv      per country: rows, kept, and each failure reason
    hazard_unmapped.csv   every unmatched hazard name, with a normalisation hint
"""

import collections
import csv
import re
import xml.sax
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.etl.models import ExtractionData

DEFAULT_OUT = Path("data/desinventar_eda")


def _norm(name: str) -> str:
    """Case/space/punctuation-insensitive key used to spot recoverable variants."""
    return re.sub(r"[^A-Z]", "", str(name).upper())


class _AuditHandler(xml.sax.ContentHandler):
    """Streams <fichas> rows without holding the (up to 1.2 GB) document in memory."""

    SECTIONS = ("eventos", "fichas", "level_maps")

    def __init__(self, iso3, parse_row_data, hazard_mapping):
        self.iso3 = iso3
        self._parse_row_data = parse_row_data
        self._hazard_mapping = hazard_mapping

        self.section = ""
        self.element = ""
        self.buffer = ""
        self.current = {}

        self.eventos = {}
        self.reasons = collections.Counter()
        self.unmapped = collections.Counter()
        self.years = collections.Counter()
        self.n_rows = 0

    def startElement(self, name, attrs):
        if name in self.SECTIONS:
            self.section = name
        elif name == "TR":
            self.current = {}
        else:
            self.element = name
            self.buffer = ""

    def characters(self, content):
        self.buffer += content

    def endElement(self, name):
        if name == "TR":
            if self.section == "eventos":
                self.eventos[str(self.current.get("nombre"))] = str(self.current.get("nombre_en"))
            elif self.section == "fichas":
                self.n_rows += 1
                self._classify(self.current)
            self.current = {}
        elif name in self.SECTIONS:
            self.section = ""
        elif self.element:
            self.current[self.element] = self.buffer.strip()
            self.buffer = ""
            self.element = ""

    def _classify(self, row):
        year = (row.get("fechano") or "").strip()
        self.years[int(year) if year.isdigit() else -1] += 1
        try:
            parsed = self._parse_row_data(row, self.eventos, self.iso3, None)
            if parsed is None:
                self.reasons["skipped_no_serial_or_event"] += 1
            elif not parsed.event_start_date:
                self.reasons["bad_date"] += 1
            elif parsed.event is None:
                self.reasons["event_none"] += 1
            elif self._hazard_mapping.get(parsed.event) is None:
                self.reasons["hazard_unmapped"] += 1
                self.unmapped[parsed.event] += 1
            else:
                self.reasons["kept"] += 1
        except Exception as exc:  # mirrors the transformer's own catch-all
            self.reasons[f"exception_{type(exc).__name__}"] += 1


class Command(BaseCommand):
    help = "Attribute every dropped DesInventar row to its cause (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(DEFAULT_OUT))
        parser.add_argument("--country", action="append", help="Limit to specific country codes")

    def handle(self, *args, **options):
        from pystac_monty.sources.desinventar import hazard_mapping, parse_row_data

        out_dir = Path(options["out"])
        out_dir.mkdir(parents=True, exist_ok=True)
        norm_index = {_norm(k): k for k in hazard_mapping}

        qs = ExtractionData.objects.filter(source=ExtractionData.Source.DESINVENTAR).exclude(resp_data="").order_by("id")

        rows = []
        unmapped_all = collections.Counter()

        for ext in qs:
            params = (ext.metadata or {}).get("params") or {}
            country_code = params.get("country_code")
            if options["country"] and country_code not in options["country"]:
                continue

            record = {"country_code": country_code, "iso3_meta": params.get("iso3"), "error": ""}
            try:
                with ext.resp_data.open("rb") as fh:
                    archive = zipfile.ZipFile(fh)
                    xml_name = next((n for n in archive.namelist() if n.lower().endswith(".xml")), None)
                    if xml_name is None:
                        record["error"] = "no xml entry in archive"
                        rows.append(record)
                        continue
                    handler = _AuditHandler(str(country_code).upper(), parse_row_data, hazard_mapping)
                    with archive.open(xml_name) as xml_fh:
                        try:
                            xml.sax.parse(xml_fh, handler)
                        except Exception as exc:
                            record["error"] = f"{type(exc).__name__}: {exc}"
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                rows.append(record)
                continue

            recoverable = sum(n for name, n in handler.unmapped.items() if _norm(name) in norm_index)
            record.update(
                {
                    "source_rows": handler.n_rows,
                    "kept": handler.reasons.get("kept", 0),
                    "hazard_unmapped": handler.reasons.get("hazard_unmapped", 0),
                    "recoverable_by_normalisation": recoverable,
                    "bad_date": handler.reasons.get("bad_date", 0),
                    "skipped_no_serial_or_event": handler.reasons.get("skipped_no_serial_or_event", 0),
                    "shapefile_levels": len(handler.eventos),
                    "rows_year_pre_1900_or_future": sum(
                        n for y, n in handler.years.items() if y != -1 and (y < 1900 or y > 2026)
                    ),
                }
            )
            for reason, n in handler.reasons.items():
                if reason.startswith("exception_"):
                    record[reason] = n
            for name, n in handler.unmapped.items():
                unmapped_all[name] += n
            rows.append(record)

            kept = record.get("kept", 0)
            total = record.get("source_rows", 0)
            loss = f"{100 * (total - kept) / total:.0f}%" if total else "-"
            self.stdout.write(f"  {country_code:6} rows={total:>7,} kept={kept:>7,} loss={loss:>5} {record['error']}")

        fields = sorted({k for r in rows for k in r})
        preferred = [
            "country_code",
            "iso3_meta",
            "source_rows",
            "kept",
            "hazard_unmapped",
            "recoverable_by_normalisation",
            "bad_date",
        ]
        fields = preferred + [f for f in fields if f not in preferred]
        with open(out_dir / "source_audit.csv", "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        with open(out_dir / "hazard_unmapped.csv", "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["hazard_name", "rows", "normalises_to", "classification"])
            for name, n in unmapped_all.most_common():
                key = _norm(name)
                alt = key[:-1] if key.endswith("S") else key + "S"
                target = norm_index.get(key) or norm_index.get(alt)
                if name in hazard_mapping:
                    classification = "explicitly_mapped_to_none"
                elif target:
                    classification = "recoverable_by_normalisation"
                else:
                    classification = "missing_from_taxonomy"
                writer.writerow([name, n, target or "", classification])

        total_rows = sum(r.get("source_rows", 0) or 0 for r in rows)
        total_kept = sum(r.get("kept", 0) or 0 for r in rows)
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{total_rows:,} source rows -> {total_kept:,} kept "
                f"({100 * (total_rows - total_kept) / total_rows:.1f}% lost)"
                if total_rows
                else "\nno rows"
            )
        )
        self.stdout.write(f"Done -> {out_dir.resolve()}  (nothing written to the database)")
