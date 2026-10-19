"""Shared bounds for untrusted text, table structure, and decimal work."""

import re

MAX_TEXT_LINES = 500_000
MAX_LINE_CHARACTERS = 256 * 1024
MAX_PRODUCTS = 50_000
MAX_UNKNOWN_CODES = 128
MAX_PRODUCT_FIELDS = 4096
MAX_PRODUCT_CHARACTERS = 1024 * 1024
MAX_HEADER_FIELDS = 4096
MAX_HEADER_CHARACTERS = 1024 * 1024
MAX_NUMERIC_CHARACTERS = 256
MAX_CALCULATED_CHARACTERS = 1024


class ResourceLimitError(ValueError):
    pass


class ProcessingCancelled(Exception):
    pass


def text_lines(text, cancelled=lambda: False):
    """Yield physical lines without allocating a list of every source line."""
    for number, match in enumerate(re.finditer(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", text), 1):
        if cancelled():
            raise ProcessingCancelled()
        if number > MAX_TEXT_LINES:
            raise ResourceLimitError(f"File exceeds the {MAX_TEXT_LINES:,} physical-line limit.")
        start, end = match.span()
        ending = ""
        if text[max(start, end - 2):end] == "\r\n":
            ending = "\r\n"
        elif text[end - 1:end] in ("\r", "\n"):
            ending = text[end - 1:end]
        content_end = end - len(ending)
        if content_end - start > MAX_LINE_CHARACTERS:
            raise ResourceLimitError(f"Line {number:,} exceeds the {MAX_LINE_CHARACTERS:,}-character limit.")
        yield number, text[start:content_end], ending
