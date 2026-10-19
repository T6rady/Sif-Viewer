"""Read-only totals for the records currently visible in the table."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from core.sif_parser import extended_list_price, numeric_value
from core.resource_limits import MAX_CALCULATED_CHARACTERS


@dataclass(frozen=True)
class TableSummary:
    count: int
    quantity: Decimal | None
    extended: Decimal | None
    quantity_missing: int
    extended_missing: int


def exact_sum(values):
    if not values:
        return None
    # Account for both integer and fractional digits without silently rounding.
    precision = max(v.adjusted() for v in values) - min(v.as_tuple().exponent for v in values)
    with localcontext() as context:
        context.prec = max(28, precision + len(str(len(values))) + 3)
        return sum(values, Decimal(0))


def summarize(records):
    quantities, extended = [], []
    for record in records:
        quantity = numeric_value(record.fields.get("QT", ""))
        price = numeric_value(extended_list_price(record), MAX_CALCULATED_CHARACTERS)
        if quantity is not None:
            quantities.append(quantity)
        if price is not None:
            extended.append(price)
    return TableSummary(len(records), exact_sum(quantities), exact_sum(extended),
                        len(records) - len(quantities), len(records) - len(extended))
