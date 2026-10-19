"""Conservative support for the documented Design Manager / standard SIF dialect.

Reference: https://knowledge.designmanager.com/support/solutions/articles/22000201116--sif-file-specification
Only names in FIELD_DEFINITIONS are interpreted. Unknown codes are retained
verbatim. Extend that registry only with a documented definition and tests.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import re


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
CODE_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_%\-]{0,31}\Z")
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


def numeric_value(value: str) -> Decimal | None:
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


def parse_sif(text: str) -> ParseResult:
    """Reject ambiguous grouping instead of inventing or silently dropping data."""
    headers: list[tuple[str, str]] = []
    records: list[SifRecord] = []
    fields: dict[str, str] = {}
    field_lines: dict[str, int] = {}
    options: list[tuple[str, str]] = []
    attributes: list[tuple[str, str]] = []
    unknown: list[tuple[str, str]] = []
    unknown_codes: set[str] = set()
    start = 0
    pending: tuple[str, str, int] | None = None

    def failure(message: str) -> ParseResult:
        return ParseResult(reason=f"Table View unavailable: {message} Raw View remains available.")

    def finish() -> str:
        missing = [key for key in REQUIRED if key not in fields or not fields[key].strip()]
        warnings = tuple(
            SifWarning(field_lines.get(code, start),
                       f"{FIELD_DEFINITIONS[code].label} ({code}) is "
                       f"{'empty' if code in fields else 'missing'}.", len(records) + 1)
            for code in missing
        )
        for code, value in fields.items():
            if value.strip() and FIELD_DEFINITIONS[code].numeric and numeric_value(value) is None:
                return f"{code} at product line {start} is not a plain decimal number."
        records.append(SifRecord(start, fields.copy(), tuple(options), tuple(attributes), tuple(unknown), warnings, len(records) + 1))
        return ""

    if not text.strip():
        return failure("the file is empty or contains only whitespace.")
    for line_number, line in enumerate(re.split(r"\r\n|\r|\n", text), 1):
        if not line.strip():
            continue
        code, separator, value = line.partition("=")
        if not separator or not CODE_PATTERN.fullmatch(code):
            return failure(f"line {line_number} is not a supported CODE=VALUE field.")
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
            start = line_number
            fields = {"PN": value}
            field_lines = {"PN": line_number}
            options, attributes, unknown = [], [], []
        elif not start:
            return failure(f"field {code} at line {line_number} occurs before a PN product boundary.")
        elif code in PAIRS:
            pending = (code, value, line_number)
        elif code in PAIRS.values():
            return failure(f"unpaired {code} at line {line_number}.")
        elif code in FIELD_DEFINITIONS:
            if code in fields:
                return failure(f"field {code} is repeated in the product at line {start}.")
            fields[code] = value
            field_lines[code] = line_number
        else:
            unknown.append((code, value))
            unknown_codes.add(code)
    if pending:
        return failure(f"{pending[0]} at line {pending[2]} has no paired description.")
    if not headers:
        return failure("this dialect requires an SF or ST file header.")
    if not start:
        return failure("no PN product records were found.")
    error = finish()
    if error:
        return failure(error)
    return ParseResult(tuple(records), tuple(headers), tuple(sorted(unknown_codes)))
