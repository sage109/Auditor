"""
Data-quality validation for transactions coming from an upload, separate
from the VAT-rule validation that happens inside the calculator. This
catches malformed input early (bad currency codes, negative values where
they shouldn't be, missing required fields) so the calculator only ever
sees well-formed Transaction objects.
"""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# ISO 4217 codes we actively support conversion for. Kept as an explicit
# allowlist rather than validating against the full ISO list, since the app
# only meaningfully supports currencies Frankfurter can convert.
SUPPORTED_CURRENCIES = {"USD", "ZWG", "ZAR", "GBP", "EUR", "BWP", "ZMW"}

REQUIRED_COLUMNS = {
    "date", "description", "counterparty", "transaction_type",
    "vat_treatment", "value_excl_vat", "currency",
}


class RowValidationError(Exception):
    def __init__(self, row_number: int, message: str):
        self.row_number = row_number
        self.message = message
        super().__init__(f"Row {row_number}: {message}")


def validate_columns(columns: set[str]) -> list[str]:
    """Return a list of missing required columns (empty list = OK)."""
    return sorted(REQUIRED_COLUMNS - set(c.strip().lower() for c in columns))


def parse_date_cell(value, row_number: int) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise RowValidationError(row_number, f"Unrecognised date format: '{value}'")


def parse_decimal_cell(value, row_number: int, field_name: str) -> Decimal:
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        raise RowValidationError(row_number, f"'{field_name}' is not a valid number: '{value}'")


def validate_currency(code: str, row_number: int) -> str:
    code = code.strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise RowValidationError(
            row_number,
            f"Currency '{code}' is not supported (supported: {', '.join(sorted(SUPPORTED_CURRENCIES))})",
        )
    return code
