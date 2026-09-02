"""
ZIMRA VAT rules used by the calculation engine.

Every constant here is dated and tagged as either:
  - CONFIRMED: taken from a cited ZIMRA source / gazetted legislation
  - ASSUMPTION: a simplification or a figure where sources conflict

Keeping these in one module (instead of scattered through calculation code)
means the whole rule set can be reviewed, cited, and defended in one place —
and updated in one place if ZIMRA changes something again.

See ASSUMPTIONS.md at the repo root for the full register with sources.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VATRatePeriod:
    """A VAT rate that applied from `effective_from` (inclusive) onward."""
    rate: Decimal
    effective_from: date
    label: str
    status: str  # "CONFIRMED" or "ASSUMPTION"
    source: str


# Historical + current standard VAT rate. New periods should be appended,
# never mutated, so the engine can correctly rate transactions dated in the
# past (e.g. sample data spanning the Jan 2026 rate change).
STANDARD_RATE_HISTORY: list[VATRatePeriod] = [
    VATRatePeriod(
        rate=Decimal("0.15"),
        effective_from=date(2020, 1, 1),  # 15% was the long-standing rate
        label="15% (pre-2026)",
        status="CONFIRMED",
        source="ZIMRA 'Taxable and Exempt supplies' — standard rate 15%",
    ),
    VATRatePeriod(
        rate=Decimal("0.155"),
        effective_from=date(2026, 1, 1),
        label="15.5% (Finance Act No. 7 of 2025)",
        status="CONFIRMED",
        source=(
            "Finance Act (No. 7) of 2025, amending the VAT Act "
            "[Chapter 23:12]; ZIMRA Public Notice 7 of 2026 sets out the "
            "Category A transitional mechanics for the Dec 2025/Jan 2026 "
            "combined return."
        ),
    ),
]

ZERO_RATE = Decimal("0.00")


def standard_rate_on(as_of: date) -> VATRatePeriod:
    """Return the VATRatePeriod in effect on a given date."""
    applicable = [p for p in STANDARD_RATE_HISTORY if p.effective_from <= as_of]
    if not applicable:
        raise ValueError(f"No standard VAT rate defined before {as_of}")
    return max(applicable, key=lambda p: p.effective_from)


# NB: ZIMRA's actual Category-A transitional mechanic for the Dec 2025/Jan
# 2026 combined return is more involved than "pick the rate for the date" —
# it grosses down the value of supply so TaRMS computes the right tax at
# 15.5% even for Dec-2025-rated supplies declared in that combined return.
# This engine implements the simpler "rate applicable on transaction date"
# approach and flags it as an ASSUMPTION for any transaction dated in that
# transition window. See ASSUMPTIONS.md.
RATE_TRANSITION_WINDOW = (date(2025, 12, 1), date(2026, 1, 31))


# ---------------------------------------------------------------------------
# VAT treatment categories
# ---------------------------------------------------------------------------

VAT_TREATMENTS = {
    "standard": {
        "description": "Standard-rated supply/purchase — taxed at the standard rate.",
        "output_taxable": True,
        "input_claimable": True,
        "status": "CONFIRMED",
    },
    "zero_rated": {
        "description": (
            "Zero-rated supply (e.g. basic foodstuffs, agricultural inputs, "
            "exports excl. un-beneficiated chrome) — taxed at 0%, but input "
            "tax on related purchases remains claimable."
        ),
        "output_taxable": True,  # taxable at 0%, still counts as a taxable supply
        "input_claimable": True,
        "status": "CONFIRMED",
        "source": "ZIMRA 'Taxable and Exempt supplies'",
    },
    "exempt": {
        "description": (
            "Exempt supply — no VAT chargeable at all, and input tax on "
            "purchases used to make exempt supplies cannot be claimed."
        ),
        "output_taxable": False,
        "input_claimable": False,
        "status": "CONFIRMED",
        "source": "ZIMRA 'Taxable and Exempt supplies'",
    },
    "import": {
        "description": (
            "Imported goods/services — import VAT charged on customs value, "
            "claimable as input tax if supported by a customs bill of entry "
            "(not a tax invoice)."
        ),
        "output_taxable": False,
        "input_claimable": True,
        "status": "CONFIRMED",
    },
    "adjustment": {
        "description": (
            "Adjustment to output or input tax — bad debts written off, "
            "credit/debit notes, apportionment, agent-withheld VAT, etc. "
            "Signed amount with a mandatory reason."
        ),
        "output_taxable": None,  # depends on adjustment_target
        "input_claimable": None,
        "status": "CONFIRMED",
    },
}

# ASSUMPTION: exact current item-by-item First Schedule split (as amended by
# SI 15 of 2024) between zero-rated and exempt is not verified line-by-line
# here. Sample data uses illustrative categories only. See ASSUMPTIONS.md.
FIRST_SCHEDULE_CLASSIFICATION_STATUS = "ASSUMPTION"


# ---------------------------------------------------------------------------
# VAT categories (filing frequency)
# ---------------------------------------------------------------------------

VAT_CATEGORIES = {
    "A": {
        "description": "Bi-monthly: periods ending Jan/Mar/May/Jul/Sep/Nov",
        "period_end_months": [1, 3, 5, 7, 9, 11],
        "status": "CONFIRMED",
    },
    "B": {
        "description": "Bi-monthly: periods ending Feb/Apr/Jun/Aug/Oct/Dec",
        "period_end_months": [2, 4, 6, 8, 10, 12],
        "status": "CONFIRMED",
    },
    "C": {
        "description": "Monthly: every calendar month",
        "period_end_months": list(range(1, 13)),
        "status": "CONFIRMED",
    },
    "D": {
        "description": "Special period approved by the Commissioner",
        "period_end_months": None,
        "status": "CONFIRMED",
    },
}

RETURN_DUE_DAY_OF_FOLLOWING_MONTH = 25  # VAT7 due by 25th of following month

# ASSUMPTION: registration threshold — sources conflict (US$60,000/year in
# older material vs US$25,000/year in a source describing 2024-effective
# rules). Kept configurable rather than hard-coded. Not used in the return
# calculation itself (this app assumes the user is already registered) —
# surfaced only for informational/report purposes.
REGISTRATION_THRESHOLD_USD_PER_YEAR_ASSUMPTION = Decimal("25000")

# Refunds below this are held as credit rather than paid out immediately.
MINIMUM_REFUND_PAYOUT_USD = Decimal("60")
MINIMUM_REFUND_PAYOUT_STATUS = "CONFIRMED"
