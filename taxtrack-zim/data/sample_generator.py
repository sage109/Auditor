"""
Generates a realistic, entirely simulated transaction dataset covering
standard-rated, zero-rated, exempt, imported, and adjustment transactions,
spanning both sides of the Jan 2026 rate change so the transition logic
has something real to chew on in the demo.

No real company or individual data is used anywhere in this file.

Run: python3 data/sample_generator.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # reproducible sample data

OUTPUT_PATH = Path(__file__).resolve().parent / "sample_transactions.csv"

FIELDS = [
    "date", "description", "counterparty", "transaction_type", "vat_treatment",
    "value_excl_vat", "currency", "has_valid_tax_invoice",
    "customs_bill_of_entry_ref", "adjustment_target", "adjustment_reason",
    "vat_amount_override",
]

STANDARD_GOODS = [
    "Office furniture", "Laptops and IT equipment", "Cement", "Paint and hardware",
    "Motor vehicle spares", "Printing services", "Security services", "Cleaning services",
]
ZERO_RATED_GOODS = [
    "Mealie-meal (10kg bags)", "Cooking oil", "Fertiliser (Compound D)", "Maize seed",
    "Export of tobacco leaf", "Export of horticultural produce", "Milk (fresh)",
]
EXEMPT_SERVICES = [
    "Tuition fees", "Medical consultation fees", "Public transport fares", "Rental of residential property",
]
IMPORTED_GOODS = [
    "Industrial machinery from South Africa", "Packaging material from Zambia",
    "Refrigeration equipment from UAE", "Raw materials from China",
]
COUNTERPARTIES = [
    "Mbare Wholesalers (Pvt) Ltd", "Highfield Retail Traders", "Bulawayo Steel Fabricators",
    "Chinhoyi Agro Supplies", "Harare North Logistics", "Gweru Construction Co",
    "Mutare Border Traders", "Masvingo Farmers Co-op", "Victoria Falls Tourism Group",
    "Kwekwe Manufacturing Ltd",
]
CURRENCIES_FOR_LOCAL = ["USD", "ZWG"]


def random_date_in(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def build_rows() -> list[dict]:
    rows = []

    periods = [
        (date(2025, 11, 1), date(2025, 12, 31)),  # pre rate-change
        (date(2026, 1, 1), date(2026, 3, 31)),    # post rate-change, incl. transition window
    ]

    for start, end in periods:
        # Standard-rated sales
        for _ in range(10):
            rows.append({
                "date": random_date_in(start, end),
                "description": random.choice(STANDARD_GOODS),
                "counterparty": random.choice(COUNTERPARTIES),
                "transaction_type": "sale",
                "vat_treatment": "standard",
                "value_excl_vat": round(random.uniform(150, 8000), 2),
                "currency": random.choice(CURRENCIES_FOR_LOCAL),
                "has_valid_tax_invoice": "",
                "customs_bill_of_entry_ref": "",
                "adjustment_target": "",
                "adjustment_reason": "",
                "vat_amount_override": "",
            })

        # Standard-rated purchases (mostly with invoices, a couple deliberately without,
        # to demonstrate the validation logic in the demo)
        for i in range(8):
            has_invoice = "FALSE" if i == 7 else "TRUE"
            rows.append({
                "date": random_date_in(start, end),
                "description": random.choice(STANDARD_GOODS),
                "counterparty": random.choice(COUNTERPARTIES),
                "transaction_type": "purchase",
                "vat_treatment": "standard",
                "value_excl_vat": round(random.uniform(100, 6000), 2),
                "currency": random.choice(CURRENCIES_FOR_LOCAL),
                "has_valid_tax_invoice": has_invoice,
                "customs_bill_of_entry_ref": "",
                "adjustment_target": "",
                "adjustment_reason": "",
                "vat_amount_override": "",
            })

        # Zero-rated sales
        for _ in range(6):
            rows.append({
                "date": random_date_in(start, end),
                "description": random.choice(ZERO_RATED_GOODS),
                "counterparty": random.choice(COUNTERPARTIES),
                "transaction_type": "sale",
                "vat_treatment": "zero_rated",
                "value_excl_vat": round(random.uniform(500, 15000), 2),
                "currency": random.choice(CURRENCIES_FOR_LOCAL),
                "has_valid_tax_invoice": "",
                "customs_bill_of_entry_ref": "",
                "adjustment_target": "",
                "adjustment_reason": "",
                "vat_amount_override": "",
            })

        # Purchases feeding zero-rated sales (input tax still claimable)
        for _ in range(3):
            rows.append({
                "date": random_date_in(start, end),
                "description": "Packaging materials for export produce",
                "counterparty": random.choice(COUNTERPARTIES),
                "transaction_type": "purchase",
                "vat_treatment": "standard",
                "value_excl_vat": round(random.uniform(200, 2000), 2),
                "currency": "USD",
                "has_valid_tax_invoice": "TRUE",
                "customs_bill_of_entry_ref": "",
                "adjustment_target": "",
                "adjustment_reason": "",
                "vat_amount_override": "",
            })

        # Exempt sales
        for _ in range(4):
            rows.append({
                "date": random_date_in(start, end),
                "description": random.choice(EXEMPT_SERVICES),
                "counterparty": random.choice(COUNTERPARTIES),
                "transaction_type": "sale",
                "vat_treatment": "exempt",
                "value_excl_vat": round(random.uniform(300, 5000), 2),
                "currency": "USD",
                "has_valid_tax_invoice": "",
                "customs_bill_of_entry_ref": "",
                "adjustment_target": "",
                "adjustment_reason": "",
                "vat_amount_override": "",
            })

        # Purchases for exempt activities (input tax blocked)
        for _ in range(2):
            rows.append({
                "date": random_date_in(start, end),
                "description": "Textbooks and teaching materials",
                "counterparty": random.choice(COUNTERPARTIES),
                "transaction_type": "purchase",
                "vat_treatment": "exempt",
                "value_excl_vat": round(random.uniform(300, 1500), 2),
                "currency": "USD",
                "has_valid_tax_invoice": "TRUE",
                "customs_bill_of_entry_ref": "",
                "adjustment_target": "",
                "adjustment_reason": "",
                "vat_amount_override": "",
            })

        # Imports (mostly with bill of entry, one without to demonstrate validation)
        for i in range(4):
            has_boe = "" if i == 3 else f"BOE-{start.year}-{1000 + i}"
            rows.append({
                "date": random_date_in(start, end),
                "description": random.choice(IMPORTED_GOODS),
                "counterparty": "Overseas Supplier",
                "transaction_type": "import",
                "vat_treatment": "import",
                "value_excl_vat": round(random.uniform(2000, 25000), 2),
                "currency": random.choice(["ZAR", "USD", "EUR"]),
                "has_valid_tax_invoice": "",
                "customs_bill_of_entry_ref": has_boe,
                "adjustment_target": "",
                "adjustment_reason": "",
                "vat_amount_override": "",
            })

        # Adjustments
        rows.append({
            "date": random_date_in(start, end),
            "description": "Bad debt written off — 120+ days overdue",
            "counterparty": random.choice(COUNTERPARTIES),
            "transaction_type": "adjustment",
            "vat_treatment": "adjustment",
            "value_excl_vat": 0,
            "currency": "USD",
            "has_valid_tax_invoice": "",
            "customs_bill_of_entry_ref": "",
            "adjustment_target": "output_tax",
            "adjustment_reason": "bad_debt_written_off",
            "vat_amount_override": round(-random.uniform(20, 200), 2),
        })
        rows.append({
            "date": random_date_in(start, end),
            "description": "Credit note issued for returned goods",
            "counterparty": random.choice(COUNTERPARTIES),
            "transaction_type": "adjustment",
            "vat_treatment": "adjustment",
            "value_excl_vat": 0,
            "currency": "USD",
            "has_valid_tax_invoice": "",
            "customs_bill_of_entry_ref": "",
            "adjustment_target": "output_tax",
            "adjustment_reason": "credit_note_issued",
            "vat_amount_override": round(-random.uniform(10, 80), 2),
        })
        rows.append({
            "date": random_date_in(start, end),
            "description": "Private-use apportionment on company vehicle fuel",
            "counterparty": "N/A",
            "transaction_type": "adjustment",
            "vat_treatment": "adjustment",
            "value_excl_vat": 0,
            "currency": "USD",
            "has_valid_tax_invoice": "",
            "customs_bill_of_entry_ref": "",
            "adjustment_target": "input_tax",
            "adjustment_reason": "apportionment_private_use",
            "vat_amount_override": round(-random.uniform(15, 60), 2),
        })

    rows.sort(key=lambda r: r["date"])
    return rows


def main():
    rows = build_rows()
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["date"] = row["date"].isoformat()
            writer.writerow(row)
    print(f"Wrote {len(rows)} simulated transactions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
