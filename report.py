#!/usr/bin/env python3
"""
Отчёт по авансам и остаткам по договорам и работам.
Считает на указанную дату (по умолчанию 2026-11-10).
Деньги — через Decimal, до копейки.
"""

import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"
REPORT_DATE = datetime(2026, 11, 10).date()


def parse_date(s: str):
    if not s or not s.strip():
        return None
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def money(s: str) -> Decimal:
    return Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def load_csv(name: str):
    path = DATA_DIR / name
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    contracts = load_csv("contracts.csv")
    works = load_csv("works.csv")
    payments = load_csv("payments.csv")

    # --- Собираем данные ---
    works_by_contract = defaultdict(list)
    for w in works:
        works_by_contract[w["contract_id"]].append(w)

    # Платежи, которые реально ушли до даты отчёта
    paid_payments = []
    for p in payments:
        if p["status"] != "paid":
            continue
        paid_at = parse_date(p["paid_at"])
        if paid_at and paid_at <= REPORT_DATE:
            paid_payments.append(p)

    # Прямые платежи по работам
    direct_paid = defaultdict(lambda: Decimal("0.00"))
    for p in paid_payments:
        if p["work_id"]:
            direct_paid[p["work_id"]] += money(p["amount"])

    # Общие платежи по договорам (без work_id)
    unallocated = defaultdict(lambda: Decimal("0.00"))
    for p in paid_payments:
        if not p["work_id"]:
            unallocated[p["contract_id"]] += money(p["amount"])

    # --- Расчёт по работам ---
    report_lines = []
    contract_totals = defaultdict(lambda: {
        "price": Decimal("0.00"),
        "paid": Decimal("0.00"),
        "left": Decimal("0.00"),
    })

    for contract in contracts:
        cid = contract["contract_id"]
        active_works = [
            w for w in works_by_contract[cid]
            if w["status"] != "cancelled"
        ]
        total_active_price = sum(money(w["price"]) for w in active_works)

        # Распределяем общие платежи пропорционально ценам активных работ
        allocated = {}
        remaining_unallocated = unallocated[cid]
        if total_active_price > 0 and remaining_unallocated > 0:
            for w in active_works:
                share = (money(w["price"]) / total_active_price * remaining_unallocated)
                share = share.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                allocated[w["work_id"]] = share
            # Корректируем копейки на последней работе
            distributed = sum(allocated.values())
            if distributed != remaining_unallocated and active_works:
                last = active_works[-1]["work_id"]
                allocated[last] += remaining_unallocated - distributed

        for w in works_by_contract[cid]:
            wid = w["work_id"]
            price = money(w["price"]) if w["status"] != "cancelled" else Decimal("0.00")
            paid = direct_paid[wid] + allocated.get(wid, Decimal("0.00"))
            left = price - paid

            report_lines.append({
                "type": "work",
                "contract_id": cid,
                "work_id": wid,
                "title": w["title"],
                "status": w["status"],
                "price": price,
                "paid": paid,
                "left": left,
            })

            contract_totals[cid]["price"] += price
            contract_totals[cid]["paid"] += paid
            contract_totals[cid]["left"] += left

    # --- Вывод ---
    print(f"Отчёт на дату: {REPORT_DATE.isoformat()}")
    print("=" * 80)
    print(f"{'Тип':<6} {'Договор':<8} {'Работа':<8} {'Название':<30} {'Цена':>12} {'Выплачено':>12} {'Осталось':>12}")
    print("-" * 80)

    current_contract = None
    for line in report_lines:
        if line["contract_id"] != current_contract:
            if current_contract:
                tot = contract_totals[current_contract]
                print(f"{'ИТОГ':<6} {current_contract:<8} {'':<8} {'':<30} {tot['price']:>12} {tot['paid']:>12} {tot['left']:>12}")
                print("-" * 80)
            current_contract = line["contract_id"]

        print(
            f"{'работа':<6} {line['contract_id']:<8} {line['work_id']:<8} "
            f"{line['title'][:28]:<30} {line['price']:>12} {line['paid']:>12} {line['left']:>12}"
        )

    if current_contract:
        tot = contract_totals[current_contract]
        print(f"{'ИТОГ':<6} {current_contract:<8} {'':<8} {'':<30} {tot['price']:>12} {tot['paid']:>12} {tot['left']:>12}")

    print("=" * 80)


if __name__ == "__main__":
    main()
