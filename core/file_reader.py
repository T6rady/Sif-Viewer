"""Decode text without replacement characters or newline translation.

No code in this module opens a source file for writing. Legacy encoding cannot
be identified conclusively: Windows-1252 is a labelled fallback, not a claim.
"""

from dataclasses import dataclass
from pathlib import Path
import codecs
import unicodedata
from core.resource_limits import ResourceLimitError, text_lines


MAX_FILE_BYTES = 64 * 1024 * 1024


class FileReadError(Exception):
    """An actionable, user-facing file error."""


@dataclass(frozen=True)
class TextFile:
    path: Path
    text: str
    size: int
    encoding: str
    line_count: int
    newline_style: str
    encoding_note: str = ""


def _ordinary_text(text: str) -> bool:
    # Permit tabs/newlines, but reject binary controls, NULs and Unicode
    # noncharacters. Do not strip or replace any input characters.
    return all(
        (ch in "\t\r\n" or unicodedata.category(ch) != "Cc")
        and not (0xD800 <= ord(ch) <= 0xDFFF)
        and not (0xFDD0 <= ord(ch) <= 0xFDEF)
        and (ord(ch) & 0xFFFF) not in (0xFFFE, 0xFFFF)
        for ch in text
    )


def decode_text(data: bytes) -> tuple[str, str, str]:
    """Return exact decoded text, encoding label and any ambiguity notice."""
    if not data:
        return "", "UTF-8 (empty)", ""
    # UTF-32 BOMs must be checked before UTF-16's prefix.
    for bom, codec, label in (
        (codecs.BOM_UTF32_LE, "utf-32", "UTF-32 LE (BOM)"),
        (codecs.BOM_UTF32_BE, "utf-32", "UTF-32 BE (BOM)"),
        (codecs.BOM_UTF8, "utf-8-sig", "UTF-8 (BOM)"),
        (codecs.BOM_UTF16_LE, "utf-16", "UTF-16 LE (BOM)"),
        (codecs.BOM_UTF16_BE, "utf-16", "UTF-16 BE (BOM)"),
    ):
        if data.startswith(bom):
            try:
                text = data.decode(codec, errors="strict")
            except UnicodeError as exc:
                raise FileReadError(f"The file has a {label} marker but invalid text data.") from exc
            if not _ordinary_text(text):
                raise FileReadError("The file contains binary or unsupported control characters.")
            return text, label, ""
    if b"\0" in data:
        raise FileReadError(
            "This appears to be binary or unmarked UTF-16/UTF-32 data. "
            "Raw View supports ordinary text; UTF-16/UTF-32 requires a byte-order marker."
        )
    try:
        text = data.decode("utf-8", errors="strict")
        label = "ASCII / UTF-8" if data.isascii() else "UTF-8"
        note = ""
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252", errors="strict")
        except UnicodeDecodeError as exc:
            raise FileReadError(
                "Unsupported encoding or binary file. Expected UTF-8, BOM-marked "
                "UTF-16/UTF-32, or Windows-1252 text. No characters were replaced."
            ) from exc
        label = "Windows-1252 (assumed)"
        note = (
            "Windows-1252 is assumed because the file is not valid UTF-8. "
            "Legacy encodings are ambiguous; verify accented characters against the source."
        )
    if not _ordinary_text(text):
        raise FileReadError("This is not ordinary text: binary or unsupported control characters were found.")
    return text, label, note


def read_file(path: str | Path, max_bytes: int = MAX_FILE_BYTES, cancelled=lambda: False) -> TextFile:
    """Read a bounded snapshot; preserve whitespace, order and line endings."""
    source = Path(path).expanduser().absolute()
    try:
        with source.open("rb") as stream:
            if stream.seek(0, 2) > max_bytes:
                raise FileReadError(f"File exceeds the {max_bytes // (1024 * 1024)} MiB viewing limit.")
            stream.seek(0)
            data = stream.read(max_bytes + 1)
    except OSError as exc:
        raise FileReadError(f"Cannot read {source.name}: {exc.strerror or str(exc)}") from exc
    if len(data) > max_bytes:
        raise FileReadError("The file grew beyond the viewing limit while being read.")
    text, encoding, note = decode_text(data)
    lines, endings = 0, set()
    try:
        for lines, _, ending in text_lines(text, cancelled):
            if ending:
                endings.add(ending)
    except ResourceLimitError as exc:
        raise FileReadError(str(exc)) from exc
    styles = {"\r\n": "CRLF", "\r": "CR", "\n": "LF"}
    newline_style = ", ".join(styles[e] for e in styles if e in set(endings)) or "None"
    return TextFile(source, text, len(data), encoding, lines, newline_style, note)
