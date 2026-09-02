"""
Test suite for the VAT calculation engine.

Structured so each ZIMRA-defined transaction type (standard, zero-rated,
exempt, imported, adjustment) has its own test, plus a handful of edge
cases that are the kind of thing an examiner/marker would probe in a demo.

Run with: python3 -m unittest discover -s tests -v   (from repo root)
"""
import sys
import os
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.models import (
    Transaction, TransactionType, VATTreatment, AdjustmentTarget, AdjustmentReason,
)
from engine.calculator import calculate_return, StaticFXRateProvider


USD_ONLY_FX = StaticFXRateProvider(rates={"USD": Decimal("1")})


def usd_provider_with(extra: dict) -> StaticFXRateProvider:
    rates = {"USD": Decimal("1")}
    rates.update(extra)
    return StaticFXRateProvider(rates=rates)


class TestStandardRated(unittest.TestCase):
    def test_standard_sale_charges_output_tax_at_current_rate(self):
        txn = Transaction(
            date=date(2026, 3, 1),
            description="Sale of office furniture",
            counterparty="Acme Traders",
            transaction_type=TransactionType.SALE,
            vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("1000"),
            currency="USD",
        )
        result = calculate_return([txn], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.output_tax, Decimal("155.00"))  # 15.5%
        self.assertEqual(result.totals.total_value_of_standard_supplies, Decimal("1000.00"))
        self.assertEqual(result.totals.net_payable_or_refundable, Decimal("155.00"))

    def test_standard_sale_uses_pre_2026_rate_for_older_transaction(self):
        txn = Transaction(
            date=date(2025, 6, 1),
            description="Sale before rate change",
            counterparty="Acme Traders",
            transaction_type=TransactionType.SALE,
            vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("1000"),
            currency="USD",
        )
        result = calculate_return([txn], "C", "June 2025", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.output_tax, Decimal("150.00"))  # 15%

    def test_standard_purchase_requires_valid_tax_invoice_to_claim_input_tax(self):
        with_invoice = Transaction(
            date=date(2026, 3, 1), description="Stock purchase", counterparty="Supplier A",
            transaction_type=TransactionType.PURCHASE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("500"), currency="USD", has_valid_tax_invoice=True,
        )
        without_invoice = Transaction(
            date=date(2026, 3, 1), description="Stock purchase, no invoice", counterparty="Supplier B",
            transaction_type=TransactionType.PURCHASE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("500"), currency="USD", has_valid_tax_invoice=False,
        )
        result = calculate_return([with_invoice, without_invoice], "C", "March 2026", "USD", USD_ONLY_FX)
        # Only the invoiced purchase's input tax should be claimed.
        self.assertEqual(result.totals.input_tax, Decimal("77.50"))  # 500 * 15.5%
        errors = [i for i in result.validation_issues if i.code == "MISSING_TAX_INVOICE"]
        self.assertEqual(len(errors), 1)


class TestZeroRated(unittest.TestCase):
    def test_zero_rated_sale_has_no_output_tax_but_counts_as_taxable_supply(self):
        txn = Transaction(
            date=date(2026, 3, 1), description="Sale of mealie-meal", counterparty="Retail Customer",
            transaction_type=TransactionType.SALE, vat_treatment=VATTreatment.ZERO_RATED,
            value_excl_vat=Decimal("2000"), currency="USD",
        )
        result = calculate_return([txn], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.output_tax, Decimal("0.00"))
        self.assertEqual(result.totals.total_value_of_zero_rated_supplies, Decimal("2000.00"))

    def test_input_tax_still_claimable_on_purchases_feeding_zero_rated_sales(self):
        purchase = Transaction(
            date=date(2026, 3, 1), description="Packaging for zero-rated goods", counterparty="Supplier C",
            transaction_type=TransactionType.PURCHASE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("300"), currency="USD", has_valid_tax_invoice=True,
        )
        result = calculate_return([purchase], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.input_tax, Decimal("46.50"))  # 300 * 15.5%


class TestExempt(unittest.TestCase):
    def test_exempt_sale_has_no_output_tax(self):
        txn = Transaction(
            date=date(2026, 3, 1), description="Exempt educational service", counterparty="Student",
            transaction_type=TransactionType.SALE, vat_treatment=VATTreatment.EXEMPT,
            value_excl_vat=Decimal("800"), currency="USD",
        )
        result = calculate_return([txn], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.output_tax, Decimal("0.00"))
        self.assertEqual(result.totals.total_value_of_exempt_supplies, Decimal("800.00"))

    def test_input_tax_blocked_on_purchases_for_exempt_supplies(self):
        purchase = Transaction(
            date=date(2026, 3, 1), description="Materials for exempt service", counterparty="Supplier D",
            transaction_type=TransactionType.PURCHASE, vat_treatment=VATTreatment.EXEMPT,
            value_excl_vat=Decimal("400"), currency="USD", has_valid_tax_invoice=True,
        )
        result = calculate_return([purchase], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.input_tax, Decimal("0.00"))
        blocked_lines = [a for a in result.audit_trail if "blocked" in a.contribution_label]
        self.assertEqual(len(blocked_lines), 1)


class TestImports(unittest.TestCase):
    def test_import_with_bill_of_entry_claims_input_tax(self):
        txn = Transaction(
            date=date(2026, 3, 1), description="Imported machinery", counterparty="Overseas Supplier",
            transaction_type=TransactionType.IMPORT, vat_treatment=VATTreatment.IMPORT,
            value_excl_vat=Decimal("10000"), currency="USD",
            customs_bill_of_entry_ref="BOE-2026-000123",
        )
        result = calculate_return([txn], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.input_tax, Decimal("1550.00"))  # 10000 * 15.5%

    def test_import_without_bill_of_entry_blocks_input_tax_claim(self):
        txn = Transaction(
            date=date(2026, 3, 1), description="Imported goods, no BOE", counterparty="Overseas Supplier",
            transaction_type=TransactionType.IMPORT, vat_treatment=VATTreatment.IMPORT,
            value_excl_vat=Decimal("5000"), currency="USD",
        )
        result = calculate_return([txn], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.input_tax, Decimal("0.00"))
        errors = [i for i in result.validation_issues if i.code == "MISSING_BILL_OF_ENTRY"]
        self.assertEqual(len(errors), 1)

    def test_import_in_foreign_currency_is_converted_to_reporting_currency(self):
        fx = usd_provider_with({"ZAR": Decimal("0.055")})  # illustrative rate
        txn = Transaction(
            date=date(2026, 3, 1), description="Imported goods from SA", counterparty="SA Supplier",
            transaction_type=TransactionType.IMPORT, vat_treatment=VATTreatment.IMPORT,
            value_excl_vat=Decimal("10000"), currency="ZAR",
            customs_bill_of_entry_ref="BOE-2026-000456",
        )
        result = calculate_return([txn], "C", "March 2026", "USD", fx)
        # 10000 ZAR * 15.5% = 1550 ZAR VAT, converted at 0.055 -> 85.25 USD
        self.assertEqual(result.totals.input_tax, Decimal("85.25"))


class TestAdjustments(unittest.TestCase):
    def test_bad_debt_written_off_reduces_output_tax(self):
        txn = Transaction(
            date=date(2026, 3, 15), description="Bad debt written off — Customer X", counterparty="Customer X",
            transaction_type=TransactionType.ADJUSTMENT, vat_treatment=VATTreatment.ADJUSTMENT,
            value_excl_vat=Decimal("0"), currency="USD",
            adjustment_target=AdjustmentTarget.OUTPUT_TAX,
            adjustment_reason=AdjustmentReason.BAD_DEBT_WRITTEN_OFF,
            vat_amount_override=Decimal("-50.00"),  # negative = reduces output tax
        )
        sale = Transaction(
            date=date(2026, 3, 1), description="Original sale", counterparty="Customer X",
            transaction_type=TransactionType.SALE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("1000"), currency="USD",
        )
        result = calculate_return([sale, txn], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.output_tax, Decimal("155.00"))
        self.assertEqual(result.totals.output_tax_adjustments, Decimal("-50.00"))
        self.assertEqual(result.totals.net_payable_or_refundable, Decimal("105.00"))

    def test_credit_note_reduces_output_tax(self):
        txn = Transaction(
            date=date(2026, 3, 20), description="Credit note issued", counterparty="Customer Y",
            transaction_type=TransactionType.ADJUSTMENT, vat_treatment=VATTreatment.ADJUSTMENT,
            value_excl_vat=Decimal("0"), currency="USD",
            adjustment_target=AdjustmentTarget.OUTPUT_TAX,
            adjustment_reason=AdjustmentReason.CREDIT_NOTE_ISSUED,
            vat_amount_override=Decimal("-31.00"),
        )
        result = calculate_return([txn], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.output_tax_adjustments, Decimal("-31.00"))
        self.assertEqual(result.totals.net_payable_or_refundable, Decimal("-31.00"))

    def test_adjustment_without_target_is_flagged_and_not_applied(self):
        txn = Transaction(
            date=date(2026, 3, 1), description="Unclear adjustment", counterparty="N/A",
            transaction_type=TransactionType.ADJUSTMENT, vat_treatment=VATTreatment.ADJUSTMENT,
            value_excl_vat=Decimal("0"), currency="USD",
            vat_amount_override=Decimal("100"),
        )
        result = calculate_return([txn], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertEqual(result.totals.output_tax_adjustments, Decimal("0"))
        self.assertEqual(result.totals.input_tax_adjustments, Decimal("0"))
        errors = [i for i in result.validation_issues if i.code == "MISSING_ADJUSTMENT_TARGET"]
        self.assertEqual(len(errors), 1)


class TestNetPosition(unittest.TestCase):
    def test_net_refundable_when_input_exceeds_output(self):
        sale = Transaction(
            date=date(2026, 3, 1), description="Small sale", counterparty="Customer",
            transaction_type=TransactionType.SALE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("100"), currency="USD",
        )
        purchase = Transaction(
            date=date(2026, 3, 1), description="Large capital purchase", counterparty="Supplier",
            transaction_type=TransactionType.PURCHASE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("5000"), currency="USD", has_valid_tax_invoice=True,
        )
        result = calculate_return([sale, purchase], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertLess(result.totals.net_payable_or_refundable, Decimal("0"))

    def test_rate_transition_window_flags_a_warning(self):
        txn = Transaction(
            date=date(2026, 1, 15), description="January transition-window sale", counterparty="Customer",
            transaction_type=TransactionType.SALE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("1000"), currency="USD",
        )
        result = calculate_return([txn], "A", "Dec 2025/Jan 2026", "USD", USD_ONLY_FX)
        warnings = [i for i in result.validation_issues if i.code == "RATE_TRANSITION_WINDOW"]
        self.assertEqual(len(warnings), 1)
        # Still computed (at the Jan rate for a Jan-dated transaction), just flagged.
        self.assertEqual(result.totals.output_tax, Decimal("155.00"))


class TestAuditTrail(unittest.TestCase):
    def test_every_output_and_input_line_traces_back_to_a_transaction_id(self):
        sale = Transaction(
            date=date(2026, 3, 1), description="Traceable sale", counterparty="Customer",
            transaction_type=TransactionType.SALE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("1000"), currency="USD",
        )
        result = calculate_return([sale], "C", "March 2026", "USD", USD_ONLY_FX)
        self.assertTrue(any(a.transaction_id == sale.id for a in result.audit_trail))

    def test_audit_trail_records_exchange_rate_used(self):
        fx = usd_provider_with({"ZWG": Decimal("0.0375")})
        sale = Transaction(
            date=date(2026, 3, 1), description="ZiG sale", counterparty="Local Customer",
            transaction_type=TransactionType.SALE, vat_treatment=VATTreatment.STANDARD,
            value_excl_vat=Decimal("10000"), currency="ZWG",
        )
        result = calculate_return([sale], "C", "March 2026", "USD", fx)
        line = [a for a in result.audit_trail if a.transaction_id == sale.id][0]
        self.assertEqual(line.exchange_rate_used, Decimal("0.0375"))


if __name__ == "__main__":
    unittest.main()
