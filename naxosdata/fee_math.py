"""Fee and Breakeven Calculation Utilities for Prediction Markets."""

from __future__ import annotations

import math
from typing import Union
from naxosdata.models import KalshiBreakevenResult

POLYGON_L2_GAS_USD = 0.008


def ceil_cents(val_dollars: float) -> float:
    """Round up a dollar amount to the nearest whole cent ($0.01)."""
    if val_dollars <= 0.0:
        return 0.0
    cents = round(val_dollars * 100.0, 6)
    return math.ceil(cents) / 100.0


def calculate_kalshi_taker_fee(
    contracts: Union[int, float],
    price: float,
    round_to_cents: bool = True,
) -> float:
    """Calculate Kalshi taker fee for C contracts at price P.

    Formula: Fee = ceil_cents(0.07 * C * P * (1 - P))
    """
    if contracts <= 0 or price <= 0.0 or price >= 1.0:
        return 0.0

    raw_fee = 0.07 * float(contracts) * price * (1.0 - price)
    if round_to_cents:
        return ceil_cents(raw_fee)
    return raw_fee


def calculate_kalshi_breakeven_spread(
    poly_yes_price: float,
    target_roi_pct: float = 0.0,
    contracts: float = 100.0,
) -> KalshiBreakevenResult:
    """Calculate the maximum Kalshi NO price to break even or hit target ROI.

    A dual-leg arbitrage buys Polymarket YES at poly_yes_price and Kalshi NO at kalshi_no_price.
    Settlement payout is $1.00 per paired contract.
    Total cost = poly_yes_price + kalshi_no_price + poly_fee + kalshi_fee.
    To break even:
        Total Outlay <= 1.00 / (1 + target_roi_pct / 100)
    Kalshi NO is priced at P_no, where Kalshi fee is ceil_cents(0.07 * C * P_no * (1 - P_no)).

    Solves the exact quadratic equation:
        0.07 * P_no^2 - 1.07 * P_no + K >= 0
    where K = 1.0 / (1 + target_roi / 100) - poly_p - poly_fee.
    The exact analytical root is:
        P_no = (1.07 - sqrt(1.1449 - 0.28 * K)) / 0.14
    """
    c = max(1.0, float(contracts))
    poly_p = max(0.01, min(0.99, float(poly_yes_price)))
    poly_fee_per_contract = POLYGON_L2_GAS_USD / c
    target_multiple = 1.0 + (target_roi_pct / 100.0)
    max_total_outlay_per_contract = 1.0 / target_multiple

    k = max_total_outlay_per_contract - poly_p - poly_fee_per_contract
    best_kalshi_no = 0.0

    if k > 0.0:
        disc = 1.1449 - 0.28 * k
        if disc >= 0.0:
            p_no_analytic = (1.07 - math.sqrt(disc)) / 0.14
            test_no = min(0.99, max(0.001, p_no_analytic))
            test_no = math.floor(test_no * 10000.0) / 10000.0
            while test_no >= 0.001:
                fee_usd = calculate_kalshi_taker_fee(c, test_no, round_to_cents=True)
                fee_per_contract = fee_usd / c
                outlay = poly_p + test_no + poly_fee_per_contract + fee_per_contract
                if outlay <= max_total_outlay_per_contract + 1e-7:
                    best_kalshi_no = test_no
                    break
                test_no = round(test_no - 0.0001, 4)

    kalshi_fee_usd = calculate_kalshi_taker_fee(c, best_kalshi_no, round_to_cents=True) if best_kalshi_no > 0 else 0.0
    kalshi_fee_contract = kalshi_fee_usd / c if best_kalshi_no > 0 else 0.0
    combined_cost = poly_p + best_kalshi_no + poly_fee_per_contract + kalshi_fee_contract
    gross_edge_cents = (1.0 - (poly_p + best_kalshi_no)) * 100.0 if best_kalshi_no > 0 else 0.0
    net_edge_cents = (1.0 - combined_cost) * 100.0 if best_kalshi_no > 0 else 0.0

    return KalshiBreakevenResult(
        poly_yes_price=round(poly_p, 4),
        target_roi_pct=round(target_roi_pct, 2),
        max_kalshi_no_price=round(best_kalshi_no, 4),
        kalshi_fee_cents=round(kalshi_fee_contract * 100.0, 3),
        poly_fee_cents=round(poly_fee_per_contract * 100.0, 3),
        gross_edge_cents=round(gross_edge_cents, 2),
        net_edge_cents=round(net_edge_cents, 2),
        total_cost_per_pair=round(combined_cost, 4),
    )


# Alias for convenience matching public docs
calculate_kalshi_breakeven = calculate_kalshi_breakeven_spread
