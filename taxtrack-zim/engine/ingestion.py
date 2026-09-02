"""
Parses a transaction CSV (uploaded or the bundled sample) into a list of
validated Transaction objects, applying the data-quality checks in
engine/validators.py before anything reaches the calculator.
"""
from __future__ import annotations
import csv
import io
from decimal import Decimal

from engine.models import Transaction, TransactionType, VATTreatment, AdjustmentTarget, AdjustmentReason
from engine.validators import (
    validate_columns, parse_date_cell, parse_decimal_cell, validate_currency, RowValidationError,
)


def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _bool_cell(value) -> bool:
    return _clean(value).upper() in ("TRUE", "1", "YES", "Y")


def parse_transactions_csv(file_like) -> tuple[list[Transaction], list[RowValidationError]]:
    """
    file_like: a file object or path opened in text mode, or an io.StringIO.
    Returns (transactions, errors). Rows with errors are skipped from the
    returned list but reported so the UI can show them.
    """
    if isinstance(file_like, (str, bytes)):
        text = file_like.decode("utf-8") if isinstance(file_like, bytes) else file_like
        reader = csv.DictReader(io.StringIO(text))
    else:
        reader = csv.DictReader(file_like)

    missing = validate_columns(set(reader.fieldnames or []))
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    transactions: list[Transaction] = []
    errors: list[RowValidationError] = []

    for i, raw in enumerate(reader, start=2):  # row 1 is the header
        try:
            txn_date = parse_date_cell(raw["date"], i)
            value = parse_decimal_cell(raw["value_excl_vat"], i, "value_excl_vat")
            currency = validate_currency(raw["currency"], i)

            override_raw = _clean(raw.get("vat_amount_override"))
            override = parse_decimal_cell(override_raw, i, "vat_amount_override") if override_raw else None

            adj_target_raw = _clean(raw.get("adjustment_target"))
            adj_reason_raw = _clean(raw.get("adjustment_reason"))

            txn = Transaction(
                date=txn_date,
                description=_clean(raw["description"]),
                counterparty=_clean(raw["counterparty"]),
                transaction_type=TransactionType(_clean(raw["transaction_type"])),
                vat_treatment=VATTreatment(_clean(raw["vat_treatment"])),
                value_excl_vat=value,
                currency=currency,
                has_valid_tax_invoice=_bool_cell(raw.get("has_valid_tax_invoice")),
                customs_bill_of_entry_ref=_clean(raw.get("customs_bill_of_entry_ref")) or None,
                adjustment_target=AdjustmentTarget(adj_target_raw) if adj_target_raw else None,
                adjustment_reason=AdjustmentReason(adj_reason_raw) if adj_reason_raw else None,
                vat_amount_override=override,
                source="uploaded_file",
            )
            transactions.append(txn)
        except (RowValidationError,) as e:
            errors.append(e)
        except (ValueError, KeyError) as e:
            errors.append(RowValidationError(i, str(e)))

    return transactions, errors
