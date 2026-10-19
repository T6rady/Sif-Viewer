"""Conservative support for the documented Design Manager / standard SIF dialect.

Reference: https://knowledge.designmanager.com/support/solutions/articles/22000201116--sif-file-specification
Only names in FIELD_DEFINITIONS are interpreted. Unknown codes are retained
verbatim. Extend that registry only with a documented definition and tests.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import re
from core.resource_limits import (MAX_PRODUCTS, MAX_UNKNOWN_CODES, MAX_PRODUCT_FIELDS,
    MAX_PRODUCT_CHARACTERS, MAX_HEADER_FIELDS, MAX_HEADER_CHARACTERS,
    MAX_NUMERIC_CHARACTERS, ResourceLimitError, text_lines)


@dataclass(frozen=True)
class FieldDefinition:
    label: str
    numeric: bool = False
    required: bool = False


FIELD_DEFINITIONS = {
    "PN": FieldDefinition("Product number", required=True),
    "PD": FieldDefinition("Description", required=True),
    "MC": FieldDefinition("Manufacturer code", required=True),
    # Herman Miller Order SIF mapping: GC is the catalog/product line code.
    # https://apidev.hermanmiller.com/om/quotetool/Content/HermanMillerQuoteTool040500OrderSIFMapping.pdf
    "GC": FieldDefinition("Catalog / product line code"),
    "QT": FieldDefinition("Quantity", numeric=True, required=True),
    "PL": FieldDefinition("List price", numeric=True, required=True),
    "TG": FieldDefinition("Side mark"),
    "S-": FieldDefinition("Sell discount %", numeric=True),
    "S%": FieldDefinition("Sell discount %", numeric=True),
    "P%": FieldDefinition("Purchase / buy %", numeric=True),
    "B%": FieldDefinition("Purchase / buy %", numeric=True),
    "PV": FieldDefinition("Picture path"),
}
REQUIRED = tuple(code for code, field in FIELD_DEFINITIONS.items() if field.required)
HEADERS = {"SF", "ST"}
PAIRS = {"ON": "OD", "AN": "AD"}
CODE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_%\-]{0,31}\Z")
NUMBER_PATTERN = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")


@dataclass(frozen=True)
class SifWarning:
    line: int
    message: str
    item: int = 0

    @property
    def text(self) -> str:
        return f"Item {self.item}: {self.message}"


@dataclass(frozen=True)
class SifRecord:
    line: int
    fields: dict[str, str]
    options: tuple[tuple[str, str], ...]
    attributes: tuple[tuple[str, str], ...]
    unknown: tuple[tuple[str, str], ...]
    warnings: tuple[SifWarning, ...] = ()
    item: int = 0
    tags: tuple[str, ...] = ()
    repeated_fields: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ParseResult:
    records: tuple[SifRecord, ...] = ()
    headers: tuple[tuple[str, str], ...] = ()
    unknown_codes: tuple[str, ...] = ()
    reason: str = ""

    @property
    def available(self) -> bool:
        return bool(self.records) and not self.reason

    @property
    def warnings(self) -> tuple[SifWarning, ...]:
        return tuple(warning for record in self.records for warning in record.warnings)


def numeric_value(value: str, max_characters=MAX_NUMERIC_CHARACTERS) -> Decimal | None:
    if len(value) > max_characters:
        return None
    candidate = value.strip()
    if not NUMBER_PATTERN.fullmatch(candidate):
        return None
    try:
        number = Decimal(candidate)
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def extended_list_price(record: SifRecord) -> str:
    """Exact QT × PL; missing operands stay blank, with no currency/rounding assumption."""
    quantity = numeric_value(record.fields.get("QT", ""))
    price = numeric_value(record.fields.get("PL", ""))
    if quantity is None or price is None:
        return ""
    with localcontext() as context:
        context.prec = max(28, len(quantity.as_tuple().digits) + len(price.as_tuple().digits) + 2)
        return format(quantity * price, "f")


def parse_sif(text: str, cancelled=lambda: False) -> ParseResult:
    try:
        return _parse_sif(text, cancelled)
    except ResourceLimitError as exc:
        return ParseResult(reason=f"Table View unavailable: {exc} Raw View remains available.")


def _parse_sif(text, cancelled) -> ParseResult:
    """Reject ambiguous grouping instead of inventing or silently dropping data."""
    headers: list[tuple[str, str]] = []
    records: list[SifRecord] = []
    fields: dict[str, str] = {}
    field_lines: dict[str, int] = {}
    options: list[tuple[str, str]] = []
    attributes: list[tuple[str, str]] = []
    unknown: list[tuple[str, str]] = []
    tags: list[str] = []
    repeated_fields: list[tuple[str, str]] = []
    scalar_values: dict[str, list[str]] = {}
    product_fields = product_characters = header_characters = 0
    unknown_codes: set[str] = set()
    start = 0
    pending: tuple[str, str, int] | None = None

    def failure(message: str) -> ParseResult:
        return ParseResult(reason=f"Table View unavailable: {message} Raw View remains available.")

    def finish() -> str:
        for code, values in scalar_values.items():
            if len(values) > 1:
                fields[code] = " | ".join(values)
        missing = [key for key in REQUIRED if key not in fields or not fields[key].strip()]
        warnings = list(
            SifWarning(field_lines.get(code, start),
                       f"{FIELD_DEFINITIONS[code].label} ({code}) is "
                       f"{'empty' if code in fields else 'missing'}.", len(records) + 1)
            for code in missing
        )
        for code, value in fields.items():
            if value.strip() and FIELD_DEFINITIONS[code].numeric and numeric_value(value) is None:
                warnings.append(SifWarning(field_lines[code],
                    (f"{code} exceeds the {MAX_NUMERIC_CHARACTERS}-character numeric limit" if len(value) > MAX_NUMERIC_CHARACTERS else f"{code} is not a plain decimal number")
                    + "; its source text is retained and calculations using it are unavailable.", len(records) + 1))
        records.append(SifRecord(start, fields.copy(), tuple(options), tuple(attributes), tuple(unknown), tuple(warnings), len(records) + 1, tuple(tags), tuple(repeated_fields)))
        return ""

    if not text.strip():
        return failure("the file is empty or contains only whitespace.")
    for line_number, line, _ in text_lines(text, cancelled):
        if not line.strip():
            continue
        code, separator, value = line.partition("=")
        if not separator or not CODE_PATTERN.fullmatch(code):
            return failure(f"line {line_number} is not a supported CODE=VALUE field.")
        if start and code != "PN":
            product_fields += 1
            product_characters += len(line)
            if product_fields > MAX_PRODUCT_FIELDS or product_characters > MAX_PRODUCT_CHARACTERS:
                raise ResourceLimitError(f"Item {len(records) + 1} exceeds the {MAX_PRODUCT_FIELDS:,}-field or {MAX_PRODUCT_CHARACTERS:,}-character product limit.")
        elif not start and code != "PN":
            header_characters += len(line)
            if len(headers) >= MAX_HEADER_FIELDS or header_characters > MAX_HEADER_CHARACTERS:
                raise ResourceLimitError("File metadata exceeds the header resource limits.")
        if pending:
            pending_code, pending_value, pending_line = pending
            if code != PAIRS[pending_code]:
                return failure(f"{pending_code} at line {pending_line} requires a following {PAIRS[pending_code]} field.")
            (options if pending_code == "ON" else attributes).append((pending_value, value))
            pending = None
            continue
        if code in HEADERS:
            if start:
                return failure(f"header field {code} appears inside a product at line {line_number}.")
            if any(key == code for key, _ in headers):
                return failure(f"header field {code} is repeated at line {line_number}.")
            headers.append((code, value))
        elif code == "PN":
            if start:
                error = finish()
                if error:
                    return failure(error)
            if len(records) >= MAX_PRODUCTS:
                raise ResourceLimitError(f"File exceeds the {MAX_PRODUCTS:,}-product table limit.")
            start = line_number
            fields = {"PN": value}
            scalar_values = {"PN": [value]}
            product_fields, product_characters = 1, len(line)
            field_lines = {"PN": line_number}
            options, attributes, unknown = [], [], []
            tags = []
            repeated_fields = []
        elif not start:
            # Exporters include additional file-level metadata (DT, TM, etc.).
            # Preserve it in order without guessing its meaning or assigning it
            # to the first product. Known product fields still signal ambiguity.
            if code in FIELD_DEFINITIONS or code in PAIRS or code in PAIRS.values():
                return failure(f"field {code} at line {line_number} occurs before a PN product boundary.")
            headers.append((code, value))
        elif code in PAIRS:
            pending = (code, value, line_number)
        elif code in PAIRS.values():
            return failure(f"unpaired {code} at line {line_number}.")
        elif code == "TG":
            tags.append(value)
            fields.setdefault(code, value)
            field_lines.setdefault(code, line_number)
        elif code in FIELD_DEFINITIONS:
            if code in fields:
                if len(scalar_values[code]) == 1:
                    repeated_fields.append((code, fields[code]))
                repeated_fields.append((code, value))
                # Joining makes ambiguous numeric fields nonnumeric, so totals
                # never silently select one of several supplied prices/quantities.
                scalar_values[code].append(value)
                continue
            fields[code] = value
            scalar_values[code] = [value]
            field_lines[code] = line_number
        else:
            unknown.append((code, value))
            unknown_codes.add(code)
            if len(unknown_codes) > MAX_UNKNOWN_CODES:
                raise ResourceLimitError(f"File exceeds the {MAX_UNKNOWN_CODES}-uninterpreted-column table limit.")
    if pending:
        return failure(f"{pending[0]} at line {pending[2]} has no paired description.")
    if not any(code in HEADERS for code, _ in headers):
        return failure("this dialect requires an SF or ST file header.")
    if not start:
        return failure("no PN product records were found.")
    error = finish()
    if error:
        return failure(error)
    return ParseResult(tuple(records), tuple(headers), tuple(sorted(unknown_codes)))
