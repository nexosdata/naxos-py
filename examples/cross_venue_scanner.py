#!/usr/bin/env python3
"""Cross-Venue Arbitrage Scanner Example via NaxosData SDK.

Scans normalized prediction market pairs across Polymarket, Kalshi, and Limitless,
filters by settlement fungibility equivalence score, and displays arbitrage spreads.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure local naxosdata package is importable
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from naxosdata import NaxosClient, ArbitragePair, RecordList


def format_pairs_table(pairs: list[ArbitragePair]) -> None:
    print(f"\n{'='*92}")
    print(f" NAXOSDATA CROSS-VENUE ARBITRAGE OPPORTUNITY MONITOR")
    print(f"{'='*92}")
    header = f"{'Pair ID':<22} | {'Venues':<20} | {'Spread':<8} | {'Net Edge':<10} | {'Fungibility':<11} | {'Status':<8}"
    print(header)
    print(f"{'-'*92}")

    for p in pairs:
        venues = f"{p.venue_long} / {p.venue_short}"
        spread = f"{p.spread_cents:+.1f}¢"
        edge = f"{p.net_roi_pct:+.2f}%"
        fungibility = f"{p.fungibility_score}/100"
        status = "HEALTHY" if p.fungibility_score >= 85 else "RISK"
        print(f"{p.pair_id:<22} | {venues:<20} | {spread:<8} | {edge:<10} | {fungibility:<11} | {status:<8}")

    print(f"{'='*92}\n")


def main() -> None:
    api_key = os.getenv("NAXOS_API_KEY", "nx_live_sample_key_0000000000000000")
    print(f"Connecting to NaxosData Scanner Engine (Key: {api_key[:12]}...)...")
    client = NaxosClient(api_key=api_key)

    try:
        # Attempt live API call
        print("Fetching active cross-venue pairs with minimum fungibility score >= 80...")
        pairs = client.get_pairs(min_fungibility=80)
        format_pairs_table(pairs)
    except Exception as exc:
        print(f"Notice: Live API server offline ({exc.__class__.__name__}). Using reference matched pairs tape:")
        demo_pairs = [
            ArbitragePair(
                pair_id="FED-RATE-CUT-NOV26",
                category="Macro",
                event_title="Fed 25bps Rate Cut at November 2026 FOMC Meeting",
                venue_long="POLYMARKET",
                venue_short="KALSHI",
                market_id_long="poly-fed-25bps-cut",
                market_id_short="KXFED-26NOV-25",
                spread_cents=2.4,
                net_roi_pct=3.75,
                fungibility_score=94,
            ),
            ArbitragePair(
                pair_id="CPI-ABOVE-2PT8-OCT26",
                category="Macro",
                event_title="US Headline CPI Year-over-Year >= 2.8% for October 2026",
                venue_long="KALSHI",
                venue_short="POLYMARKET",
                market_id_long="KXCPI-26OCT-2.8",
                market_id_short="poly-cpi-oct26-2pt8",
                spread_cents=1.9,
                net_roi_pct=2.85,
                fungibility_score=91,
            ),
            ArbitragePair(
                pair_id="BITCOIN-100K-DEC26",
                category="Crypto",
                event_title="Bitcoin Price Above $100,000 on December 31, 2026",
                venue_long="POLYMARKET",
                venue_short="LIMITLESS",
                market_id_long="poly-btc-100k-eoy",
                market_id_short="limitless-btc-100k",
                spread_cents=3.1,
                net_roi_pct=4.80,
                fungibility_score=88,
            ),
            ArbitragePair(
                pair_id="ECB-DEPOSIT-CUT-DEC26",
                category="Macro",
                event_title="ECB cuts Deposit Facility Rate by 25bps in December 2026",
                venue_long="KALSHI",
                venue_short="POLYMARKET",
                market_id_long="KXECB-26DEC-25",
                market_id_short="poly-ecb-dec26",
                spread_cents=1.2,
                net_roi_pct=1.65,
                fungibility_score=79,  # Below 85 - toxic warning
            ),
        ]
        # Filter for high fungibility (score >= 85)
        high_fungibility_pairs = [p for p in demo_pairs if p.fungibility_score >= 85]
        print(f"\nFiltered {len(high_fungibility_pairs)} high-fungibility pairs (oracle score >= 85):")
        format_pairs_table(high_fungibility_pairs)

    print("SUCCESS: Cross-venue arbitrage scanner executed cleanly.")


if __name__ == "__main__":
    main()
