"""Unformatted record values shared by the table, clipboard, and CSV export."""

from core.sif_parser import extended_list_price


def record_value(record, code):
    if code == "TG" and record.tags:
        return " | ".join(record.tags)
    if code == "options_count":
        return str(len(record.options))
    if code == "extended_list":
        return extended_list_price(record)
    if code.startswith("raw:"):
        return " | ".join(value for key, value in record.unknown if key == code[4:])
    if code in ("option_codes", "option_descriptions", "attribute_codes", "attribute_descriptions"):
        pairs = record.options if code.startswith("option_") else record.attributes
        part = 0 if code.endswith("codes") else 1
        return " | ".join(pair[part] for pair in pairs)
    if code == "warnings":
        return " | ".join(warning.text for warning in record.warnings)
    if code in ("options", "attributes"):
        return " | ".join(f"{number} : {description}" for number, description in getattr(record, code))
    if code == "unknown":
        return " | ".join(f"{key}={value}" for key, value in record.unknown)
    return record.fields.get(code, "")
