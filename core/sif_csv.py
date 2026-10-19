"""Versioned, lossless text interchange; never serialize the table model."""

import codecs
import csv
import io
import os
from pathlib import Path
import re
import tempfile

from core.csv_exporter import ExportCancelled
from core.file_reader import MAX_FILE_BYTES, FileReadError, decode_text
from core.sif_parser import CODE_PATTERN


class ConversionError(Exception):
    """An actionable interchange error, distinct from SIF table warnings."""


HEADINGS = ("kind", "sequence", "item", "code", "value", "eol")
FORMAT = "ori-sif-csv/1"
MAX_CSV_BYTES = 256 * 1024 * 1024
ENDINGS = {"CRLF": "\r\n", "LF": "\n", "CR": "\r", "NONE": ""}
ENCODINGS = {
    "utf-8": codecs.BOM_UTF8,
    "utf-16-le": codecs.BOM_UTF16_LE,
    "utf-16-be": codecs.BOM_UTF16_BE,
    "utf-32-le": codecs.BOM_UTF32_LE,
    "utf-32-be": codecs.BOM_UTF32_BE,
    "cp1252": b"",
}
# CSV's default 128 KiB limit is smaller than a supported SIF field.
csv.field_size_limit(max(csv.field_size_limit(), MAX_FILE_BYTES))


def _check_cancelled(cancelled):
    if cancelled():
        raise ExportCancelled()


def _protect(path, source_paths, suffix):
    path = Path(path)
    if path.suffix.lower() != suffix:
        raise ConversionError(f"Choose a destination ending in {suffix}.")
    for source in source_paths:
        if source is None:
            continue
        source = Path(source)
        if path.resolve() == source.resolve() or (
                path.exists() and source.exists() and os.path.samefile(path, source)):
            raise ConversionError("The destination must differ from the source and the opened SIF, including file aliases.")


def _atomic_write(path, source_paths, suffix, write, cancelled):
    path = Path(path)
    temporary = None
    try:
        _protect(path, source_paths, suffix)
        _check_cancelled(cancelled)
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".sif-convert-", suffix=".tmp",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            count = write(stream)
        _check_cancelled(cancelled)
        # Recheck aliases just before committing the completed file.
        _protect(path, source_paths, suffix)
        os.replace(temporary, path)
        temporary = None
        return count
    except (OSError, UnicodeError, csv.Error, FileReadError) as exc:
        raise ConversionError(f"Conversion failed: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _encoding(document):
    label = document.encoding
    if label.startswith("UTF-16") or label.startswith("UTF-32"):
        return label[:6].lower() + "-" + label[7:9].lower(), "present"
    if label.startswith("Windows-1252"):
        return "cp1252", "none"
    return "utf-8", "present" if "(BOM)" in label else "none"


def _field(line):
    code, separator, value = line.partition("=")
    if separator and CODE_PATTERN.fullmatch(code):
        return code, value
    return "", line


def export_reversible_csv(path, document, cancelled=lambda: False):
    """Export the complete immutable loaded snapshot, independent of table state."""
    def write(binary):
        encoding, bom = _encoding(document)
        # Detach so the binary stream remains owned by the atomic writer.
        stream = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        count = 0
        try:
            class BoundedWriter:
                size = len(codecs.BOM_UTF8)

                def write(self, value):
                    self.size += len(value.encode("utf-8"))
                    if self.size > MAX_CSV_BYTES:
                        raise ConversionError("The reversible CSV exceeds the 256 MiB conversion limit.")
                    return stream.write(value)

            writer = csv.writer(BoundedWriter(), lineterminator="\r\n")
            writer.writerow(HEADINGS)
            for code, value in (("format", FORMAT), ("encoding", encoding), ("bom", bom)):
                writer.writerow(("meta", "", "", code, value, ""))
            if document.encoding_note:
                writer.writerow(("meta", "", "", "encoding_note", document.encoding_note, ""))
            item = 0
            for match in re.finditer(r"([^\r\n]*)(\r\n|\r|\n)|([^\r\n]+)$", document.text):
                _check_cancelled(cancelled)
                line = match[1] if match[1] is not None else match[3]
                ending = match[2] or ""
                code, value = _field(line)
                if code == "PN":
                    item += 1
                count += 1
                eol = next(key for key, text in ENDINGS.items() if text == ending)
                writer.writerow(("field" if code else "text", count, item or "", code, value, eol))
            stream.flush()
        finally:
            stream.detach()
        return count

    return _atomic_write(path, (document.path,), ".csv", write, cancelled)


def _positive(value, label):
    if not re.fullmatch(r"[1-9][0-9]*", value) or len(value) > 10:
        raise ConversionError(f"{label} must be a positive integer without leading zeros.")
    return int(value)


def _decode_csv(data, cancelled):
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        if next(reader, None) != list(HEADINGS):
            raise ConversionError("This is not a reversible SIF CSV. The readable table export cannot be converted to SIF.")
        metadata, rows = {}, {}
        for row in reader:
            _check_cancelled(cancelled)
            if len(row) != len(HEADINGS):
                raise ConversionError("Every CSV record must contain exactly six columns.")
            kind, sequence, item, code, value, eol = row
            if kind == "meta":
                if sequence or item or eol or code not in {"format", "encoding", "bom", "encoding_note"} or code in metadata:
                    raise ConversionError("Invalid, repeated, or unknown CSV metadata.")
                metadata[code] = value
                continue
            number = _positive(sequence, "Sequence")
            if number in rows:
                raise ConversionError(f"Sequence {number} is repeated.")
            if kind not in {"field", "text"} or eol not in ENDINGS:
                raise ConversionError(f"Invalid row kind or line ending at sequence {number}.")
            if any(ch in code + value for ch in "\r\n"):
                raise ConversionError(f"Sequence {number} contains an embedded SIF line break. Use separate rows.")
            if kind == "field":
                if not CODE_PATTERN.fullmatch(code):
                    raise ConversionError(f"Invalid field code at sequence {number}.")
                line = code + "=" + value
            else:
                if code or _field(value)[0] or (not value and eol == "NONE"):
                    raise ConversionError(f"Invalid literal text at sequence {number}.")
                line = value
            rows[number] = (item, code, line, eol)
        if metadata.get("format") != FORMAT:
            raise ConversionError("Missing or unsupported reversible CSV format version.")
        encoding, bom = metadata.get("encoding"), metadata.get("bom")
        if encoding not in ENCODINGS or bom not in {"none", "present"}:
            raise ConversionError("Missing or unsupported SIF encoding/BOM metadata.")
        if (encoding.startswith(("utf-16", "utf-32")) and bom != "present") or (encoding == "cp1252" and bom != "none"):
            raise ConversionError("This encoding requires different BOM metadata.")
        output = bytearray(ENCODINGS[encoding] if bom == "present" else b"")
        item_number = 0
        for expected, number in enumerate(sorted(rows), 1):
            _check_cancelled(cancelled)
            if number != expected:
                raise ConversionError("Sequence numbers must be contiguous, starting at 1.")
            item, code, line, eol = rows[number]
            if code == "PN":
                item_number += 1
            if item != (str(item_number) if item_number else ""):
                raise ConversionError(f"Item reference at sequence {number} does not match the PN boundaries (expected item {item_number or 'blank'}).")
            if eol == "NONE" and number != len(rows):
                raise ConversionError("Only the last SIF line may have line ending NONE.")
            try:
                output.extend((line + ENDINGS[eol]).encode(encoding, errors="strict"))
            except UnicodeEncodeError as exc:
                location = f"Item {item_number}" if item_number else "File text before the first item"
                raise ConversionError(f"{location}: text cannot be represented in {encoding}. No characters were replaced.") from exc
            if len(output) > MAX_FILE_BYTES:
                raise ConversionError("The reconstructed SIF exceeds the 64 MiB limit.")
        # Reject unsupported controls and invalid text even in literal rows.
        decode_text(bytes(output))
        return bytes(output), len(rows)
    except (UnicodeError, csv.Error, FileReadError) as exc:
        raise ConversionError(f"Invalid reversible CSV: {exc}") from exc


def import_reversible_csv(source, path, protected_source=None, cancelled=lambda: False):
    """Validate completely, then write a separate SIF. Missing SIF fields stay missing."""
    source = Path(source)

    def write(stream):
        with source.open("rb") as csv_stream:
            if csv_stream.seek(0, 2) > MAX_CSV_BYTES:
                raise ConversionError("The CSV exceeds the 256 MiB conversion limit.")
            csv_stream.seek(0)
            data = csv_stream.read(MAX_CSV_BYTES + 1)
        if len(data) > MAX_CSV_BYTES:
            raise ConversionError("The CSV grew beyond the conversion limit while being read.")
        data, count = _decode_csv(data, cancelled)
        _check_cancelled(cancelled)
        stream.write(data)
        return count

    return _atomic_write(path, (source, protected_source), ".sif", write, cancelled)
