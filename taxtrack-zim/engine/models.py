"""
Core data models for TaxTrack Zim.

Deliberately implemented with plain stdlib dataclasses (no pydantic/ORM)
so the calculation engine has zero third-party dependencies and can be
tested, read, and defended on its own, independent of the Streamlit layer.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import uuid4


class TransactionType(str, Enum):
    SALE = "sale"
    PURCHASE = "purchase"
    IMPORT = "import"
    ADJUSTMENT = "adjustment"


class VATTreatment(str, Enum):
    STANDARD = "standard"
    ZERO_RATED = "zero_rated"
    EXEMPT = "exempt"
    IMPORT = "import"
    ADJUSTMENT = "adjustment"


class AdjustmentTarget(str, Enum):
    """Which side of the return an adjustment affects."""
    OUTPUT_TAX = "output_tax"
    INPUT_TAX = "input_tax"


class AdjustmentReason(str, Enum):
    BAD_DEBT_WRITTEN_OFF = "bad_debt_written_off"
    BAD_DEBT_RECOVERED = "bad_debt_recovered"
    CREDIT_NOTE_ISSUED = "credit_note_issued"
    DEBIT_NOTE_ISSUED = "debit_note_issued"
    APPORTIONMENT_PRIVATE_USE = "apportionment_private_use"
    AGENT_WITHHELD_VAT = "agent_withheld_vat"
    RATE_TRANSITION_CORRECTION = "rate_transition_correction"
    OTHER = "other"


class ValidationSeverity(str, Enum):
    ERROR = "error"      # blocks the transaction from being claimed/counted as entered
    WARNING = "warning"  # allowed, but flagged (e.g. assumption applied)


@dataclass
class ValidationIssue:
    severity: ValidationSeverity
    code: str
    message: str


@dataclass
class Transaction:
    date: date
    description: str
    counterparty: str
    transaction_type: TransactionType
    vat_treatment: VATTreatment
    value_excl_vat: Decimal
    currency: str  # ISO 4217, e.g. "USD", "ZWG", "ZAR", "EUR", "GBP"
    has_valid_tax_invoice: bool = False
    customs_bill_of_entry_ref: str | None = None
    adjustment_target: AdjustmentTarget | None = None
    adjustment_reason: AdjustmentReason | None = None
    vat_amount_override: Decimal | None = None  # explicit override, e.g. for adjustments
    source: str = "manual"  # "manual" | "uploaded_file"
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        # Normalise types coming from CSV/dict ingestion.
        if isinstance(self.value_excl_vat, str):
            self.value_excl_vat = Decimal(self.value_excl_vat)
        if isinstance(self.vat_amount_override, str) and self.vat_amount_override != "":
            self.vat_amount_override = Decimal(self.vat_amount_override)
        if self.vat_amount_override == "":
            self.vat_amount_override = None
        if isinstance(self.transaction_type, str):
            self.transaction_type = TransactionType(self.transaction_type)
        if isinstance(self.vat_treatment, str):
            self.vat_treatment = VATTreatment(self.vat_treatment)
        if isinstance(self.adjustment_target, str) and self.adjustment_target:
            self.adjustment_target = AdjustmentTarget(self.adjustment_target)
        if isinstance(self.adjustment_reason, str) and self.adjustment_reason:
            self.adjustment_reason = AdjustmentReason(self.adjustment_reason)
        self.currency = self.currency.upper()


@dataclass
class AuditTrailEntry:
    """One line in the drill-down trail from a return total back to source data."""
    transaction_id: str
    description: str
    contribution_label: str       # e.g. "Output tax", "Input tax", "Output tax adjustment"
    original_amount: Decimal
    original_currency: str
    converted_amount: Decimal     # in reporting currency
    exchange_rate_used: Decimal
    rate_as_of: date | None       # None if a fallback/static rate was used
    rule_applied: str             # short description of which rule/rate was applied
    notes: list[str] = field(default_factory=list)


@dataclass
class VATReturnTotals:
    total_value_of_standard_supplies: Decimal
    total_value_of_zero_rated_supplies: Decimal
    total_value_of_exempt_supplies: Decimal
    output_tax: Decimal
    input_tax: Decimal
    output_tax_adjustments: Decimal
    input_tax_adjustments: Decimal
    net_payable_or_refundable: Decimal  # positive = payable, negative = refundable


@dataclass
class VATReturn:
    category: str  # "A" | "B" | "C" | "D"
    period_label: str
    reporting_currency: str
    totals: VATReturnTotals
    audit_trail: list[AuditTrailEntry]
    validation_issues: list[ValidationIssue]
    exchange_rates_used: dict[str, dict] = field(default_factory=dict)
    generated_at: str = ""
