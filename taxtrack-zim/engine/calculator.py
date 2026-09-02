"""
VAT calculation engine.

Design goal: every number in the final return must be traceable back to the
source transaction(s) that produced it. `calculate_return()` returns both
the totals AND a full audit trail — the trail is not an afterthought, it's
built alongside the totals in the same pass.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    Transaction,
    TransactionType,
    VATTreatment,
    AdjustmentTarget,
    ValidationIssue,
    ValidationSeverity,
    AuditTrailEntry,
    VATReturnTotals,
    VATReturn,
)
from .rules import standard_rate_on, RATE_TRANSITION_WINDOW


TWO_DP = Decimal("0.01")


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class FXRateProvider:
    """
    Minimal interface the calculator needs from an FX source.
    services/fx.py implements this against the Frankfurter API; tests use a
    simple in-memory fake. Keeping this as a narrow interface means the
    calculator has no direct dependency on network code.
    """

    def get_rate(self, currency: str, as_of: date, reporting_currency: str) -> tuple[Decimal, date | None]:
        """
        Return (rate, rate_date). `rate` converts 1 unit of `currency` into
        `reporting_currency`. `rate_date` is None if a fallback/static rate
        was used (so the caller can flag it in the audit trail).
        """
        raise NotImplementedError


class StaticFXRateProvider(FXRateProvider):
    """Fixed-rate provider — used for tests and as an offline fallback."""

    def __init__(self, rates: dict[str, Decimal]):
        # rates: {"USD": Decimal("1"), "ZWG": Decimal("0.0375"), ...}
        # i.e. 1 unit of currency -> reporting-currency value
        self.rates = rates

    def get_rate(self, currency: str, as_of: date, reporting_currency: str):
        if currency == reporting_currency:
            return Decimal("1"), None
        if currency not in self.rates:
            raise ValueError(f"No static rate configured for {currency}")
        return self.rates[currency], None


def _validate_transaction(txn: Transaction) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if txn.vat_treatment == VATTreatment.STANDARD and not txn.has_valid_tax_invoice:
        if txn.transaction_type == TransactionType.PURCHASE:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="MISSING_TAX_INVOICE",
                message=(
                    f"Purchase '{txn.description}' is standard-rated but has no "
                    "valid tax invoice — input tax cannot be claimed (VAT is an "
                    "invoice-based tax under ZIMRA rules)."
                ),
            ))

    if txn.transaction_type == TransactionType.IMPORT and not txn.customs_bill_of_entry_ref:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="MISSING_BILL_OF_ENTRY",
            message=(
                f"Import '{txn.description}' has no bill of entry reference — "
                "import input tax cannot be claimed without one."
            ),
        ))

    if txn.transaction_type == TransactionType.ADJUSTMENT and txn.adjustment_target is None:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="MISSING_ADJUSTMENT_TARGET",
            message=f"Adjustment '{txn.description}' does not specify output_tax or input_tax.",
        ))

    if txn.transaction_type == TransactionType.ADJUSTMENT and txn.adjustment_reason is None:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="MISSING_ADJUSTMENT_REASON",
            message=f"Adjustment '{txn.description}' has no reason code recorded.",
        ))

    if RATE_TRANSITION_WINDOW[0] <= txn.date <= RATE_TRANSITION_WINDOW[1]:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            code="RATE_TRANSITION_WINDOW",
            message=(
                f"Transaction dated {txn.date} falls in the Dec 2025/Jan 2026 "
                "rate-transition window. This engine applies the rate in force "
                "on the transaction date; ZIMRA's actual Category A combined-"
                "return mechanic grosses down the value of supply instead. "
                "Treat as an assumption for transactions in this window — see "
                "ASSUMPTIONS.md."
            ),
        ))

    return issues


def _line_vat(txn: Transaction) -> Decimal:
    """Compute the VAT amount for a single transaction, before currency conversion."""
    if txn.vat_amount_override is not None:
        return txn.vat_amount_override

    if txn.vat_treatment in (VATTreatment.ZERO_RATED,):
        return Decimal("0")

    if txn.vat_treatment == VATTreatment.EXEMPT:
        return Decimal("0")

    if txn.vat_treatment in (VATTreatment.STANDARD, VATTreatment.IMPORT):
        rate_period = standard_rate_on(txn.date)
        return _round(txn.value_excl_vat * rate_period.rate)

    if txn.vat_treatment == VATTreatment.ADJUSTMENT:
        # Adjustments must carry an explicit amount via vat_amount_override;
        # if absent, treat the transaction value itself as the adjustment amount.
        return txn.value_excl_vat

    return Decimal("0")


def calculate_return(
    transactions: list[Transaction],
    category: str,
    period_label: str,
    reporting_currency: str,
    fx_provider: FXRateProvider,
) -> VATReturn:
    total_standard = Decimal("0")
    total_zero_rated = Decimal("0")
    total_exempt = Decimal("0")
    output_tax = Decimal("0")
    input_tax = Decimal("0")
    output_adjustments = Decimal("0")
    input_adjustments = Decimal("0")

    audit_trail: list[AuditTrailEntry] = []
    all_issues: list[ValidationIssue] = []
    rates_used: dict[str, dict] = {}

    for txn in transactions:
        issues = _validate_transaction(txn)
        all_issues.extend(issues)
        blocking = [i for i in issues if i.severity == ValidationSeverity.ERROR]

        rate, rate_date = fx_provider.get_rate(txn.currency, txn.date, reporting_currency)
        converted_value = _round(txn.value_excl_vat * rate)
        rates_used.setdefault(txn.currency, {"rate": str(rate), "as_of": str(rate_date) if rate_date else "fallback"})

        vat_native = _line_vat(txn)
        vat_converted = _round(vat_native * rate)

        notes = [i.message for i in issues]

        # --- Value-of-supply totals (informational, mirrors VAT7 structure) ---
        if txn.transaction_type == TransactionType.SALE:
            if txn.vat_treatment == VATTreatment.STANDARD:
                total_standard += converted_value
            elif txn.vat_treatment == VATTreatment.ZERO_RATED:
                total_zero_rated += converted_value
            elif txn.vat_treatment == VATTreatment.EXEMPT:
                total_exempt += converted_value

        # --- Output tax ---
        if txn.transaction_type == TransactionType.SALE and txn.vat_treatment in (
            VATTreatment.STANDARD, VATTreatment.ZERO_RATED
        ):
            output_tax += vat_converted
            audit_trail.append(AuditTrailEntry(
                transaction_id=txn.id,
                description=txn.description,
                contribution_label="Output tax",
                original_amount=vat_native,
                original_currency=txn.currency,
                converted_amount=vat_converted,
                exchange_rate_used=rate,
                rate_as_of=rate_date,
                rule_applied=f"{txn.vat_treatment.value} rate on sale",
                notes=notes,
            ))

        # --- Input tax (standard purchases + imports), gated on validity ---
        if txn.transaction_type == TransactionType.PURCHASE and txn.vat_treatment == VATTreatment.STANDARD:
            if not blocking:
                input_tax += vat_converted
            audit_trail.append(AuditTrailEntry(
                transaction_id=txn.id,
                description=txn.description,
                contribution_label="Input tax" if not blocking else "Input tax (NOT claimed — see issues)",
                original_amount=vat_native,
                original_currency=txn.currency,
                converted_amount=vat_converted if not blocking else Decimal("0"),
                exchange_rate_used=rate,
                rate_as_of=rate_date,
                rule_applied="standard rate on purchase, requires valid tax invoice",
                notes=notes,
            ))

        if txn.transaction_type == TransactionType.IMPORT:
            if not blocking:
                input_tax += vat_converted
            audit_trail.append(AuditTrailEntry(
                transaction_id=txn.id,
                description=txn.description,
                contribution_label="Input tax (import)" if not blocking else "Input tax (import, NOT claimed — see issues)",
                original_amount=vat_native,
                original_currency=txn.currency,
                converted_amount=vat_converted if not blocking else Decimal("0"),
                exchange_rate_used=rate,
                rate_as_of=rate_date,
                rule_applied="import VAT on customs value, requires bill of entry",
                notes=notes,
            ))

        # Purchases against exempt supplies: value tracked, no input tax.
        if txn.transaction_type == TransactionType.PURCHASE and txn.vat_treatment == VATTreatment.EXEMPT:
            audit_trail.append(AuditTrailEntry(
                transaction_id=txn.id,
                description=txn.description,
                contribution_label="Input tax (blocked — exempt-related purchase)",
                original_amount=Decimal("0"),
                original_currency=txn.currency,
                converted_amount=Decimal("0"),
                exchange_rate_used=rate,
                rate_as_of=rate_date,
                rule_applied="no input tax on purchases used to make exempt supplies",
                notes=notes,
            ))

        # --- Adjustments ---
        if txn.transaction_type == TransactionType.ADJUSTMENT:
            if not blocking:
                if txn.adjustment_target == AdjustmentTarget.OUTPUT_TAX:
                    output_adjustments += vat_converted
                elif txn.adjustment_target == AdjustmentTarget.INPUT_TAX:
                    input_adjustments += vat_converted
            reason = txn.adjustment_reason.value if txn.adjustment_reason else "unspecified"
            target = txn.adjustment_target.value if txn.adjustment_target else "unresolved"
            audit_trail.append(AuditTrailEntry(
                transaction_id=txn.id,
                description=txn.description,
                contribution_label=f"Adjustment ({target})" if not blocking else "Adjustment (NOT applied — see issues)",
                original_amount=vat_native,
                original_currency=txn.currency,
                converted_amount=vat_converted if not blocking else Decimal("0"),
                exchange_rate_used=rate,
                rate_as_of=rate_date,
                rule_applied=f"adjustment reason: {reason}",
                notes=notes,
            ))

    net = _round(
        (output_tax + output_adjustments) - (input_tax + input_adjustments)
    )

    totals = VATReturnTotals(
        total_value_of_standard_supplies=_round(total_standard),
        total_value_of_zero_rated_supplies=_round(total_zero_rated),
        total_value_of_exempt_supplies=_round(total_exempt),
        output_tax=_round(output_tax),
        input_tax=_round(input_tax),
        output_tax_adjustments=_round(output_adjustments),
        input_tax_adjustments=_round(input_adjustments),
        net_payable_or_refundable=net,
    )

    return VATReturn(
        category=category,
        period_label=period_label,
        reporting_currency=reporting_currency,
        totals=totals,
        audit_trail=audit_trail,
        validation_issues=all_issues,
        exchange_rates_used=rates_used,
    )
