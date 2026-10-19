"""Write a table snapshot as UTF-8 CSV without altering the source SIF."""

import csv
import os
from pathlib import Path
import tempfile

from core.table_data import record_value


class CsvExportError(Exception):
    pass


class ExportCancelled(Exception):
    pass


def export_csv(path, headings, columns, records, source_path, cancelled=lambda: False):
    """Return exported row count. Only a complete export replaces the destination.

    Headings, columns, and records must be a snapshot in displayed order, with
    no Qt objects. Values are CSV-quoted but otherwise retain their source text.
    This is a readable table export, not a reversible SIF interchange format.
    """
    path, source_path = Path(path), Path(source_path)
    temporary = None
    try:
        if path.suffix.lower() != ".csv":
            raise CsvExportError("Choose a destination ending in .csv. SIF files cannot be overwritten.")
        if path.resolve() == source_path.resolve() or (path.exists() and source_path.exists()
                                                      and os.path.samefile(path, source_path)):
            raise CsvExportError("The CSV destination must be different from the opened source file.")
        if not columns or len(columns) != len(headings):
            raise CsvExportError("Choose at least one visible table column before exporting.")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="",
                                         prefix=".sif-csv-", suffix=".tmp", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream, lineterminator="\r\n")
            writer.writerow(("Item", *headings))
            count = 0
            for record in records:
                if cancelled():
                    raise ExportCancelled()
                writer.writerow((record.item, *(record_value(record, code) for code in columns)))
                count += 1
        if cancelled():
            raise ExportCancelled()
        os.replace(temporary, path)
        temporary = None
        return count
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CsvExportError(f"Could not write the CSV file: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
