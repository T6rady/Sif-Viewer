"""Qt tooltips use rich text: wrap escaped, bounded source text explicitly."""

from html import escape

MAX_TOOLTIP_CHARACTERS = 8192


def plain_tooltip(text):
    if len(text) > MAX_TOOLTIP_CHARACTERS:
        text = text[:MAX_TOOLTIP_CHARACTERS] + "\n… (tooltip truncated; full text remains in the document)"
    return '<qt><span style="white-space: pre-wrap">' + escape(text) + '</span></qt>'
