# NaxosData Python SDK (`naxosdata` / `naxos-py`)

[![PyPI version](https://img.shields.io/pypi/v/naxosdata.svg)](https://pypi.org/project/naxosdata/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

The official Python client library for the [NaxosData](https://naxosdata.com) Historical L2 Data, Canonical Symbology Mapping & Local SDK Backtesting API.

Provides synchronous (`NaxosClient`) and asynchronous (`AsyncNaxosClient`) access to normalized Level 2 order books, cross-venue matched pairs, and discrete event-driven backtesting across all **6 active prediction venues**: **Polymarket**, **Kalshi**, **Limitless**, **PredictIt**, **Drift BET**, and **Smarkets**.

---

## 60-Second Quickstart

### 1. Installation

```bash
pip install naxosdata
```

With optional Pandas & PyArrow support for DataFrame exports and local backtesting:
```bash
pip install "naxosdata[backtest]"
```

### 2. Python Client (Fetch L2, Matched Pairs & Backtest in 10 Lines)

```python
import os
from naxosdata import NaxosClient, Venue

client = NaxosClient(api_key=os.getenv("NAXOS_API_KEY", "nx_live_demo"))

# 1. Fetch normalized Level 2 snapshot (20-level depth)
snap = client.get_orderbook_snapshot(venue=Venue.POLYMARKET, market_id="poly-fed-nov-2026")
print(f"Spread: {snap.spread_bps} bps | Best Bid: ${snap.best_bid:.3f} | Best Ask: ${snap.best_ask:.3f}")

# 2. Query cross-venue matched pairs filtered by volume & oracle alignment
pairs = client.get_pairs(min_fungibility=80, min_volume=10000.0)
for p in pairs[:3]:
    print(f"[{p.pair_id}] {p.venue_long} -> {p.venue_short} | Net ROI: +{p.net_roi_pct:.2f}% | Score: {p.fungibility_score}/100")

# 3. Pull historical L2 orderbooks for local strategy backtesting
backtest = client.run_backtest(pair_id=pairs[0].pair_id if pairs else "PAIR_FED_NOV26_25BPS", bankroll=5000.0)
print(backtest.summary())
```

---

## Canonical Schema & 6-Venue Normalization

All 6 venues are normalized into the **`0.0001`–`0.9999`** probability scale with standardized **20-level L2 depth** (`best_bid`, `best_ask`, `mid_price`, `spread_bps`, `obi_top5`) and exact net-of-fee math:

| Venue | Native Protocol Format | Canonical Normalization Mechanism | Exact Net-of-Fee Math |
| :--- | :--- | :--- | :--- |
| **`POLYMARKET`** | CLOB USD strings `[0.00, 1.00]` | Direct probability ladder (sorted bids desc, asks asc) | 0 bps maker/taker CLOB fee + Polygon L2 gas (~$0.008/tx) |
| **`KALSHI`** | Reciprocal cents `[1, 99]` / `orderbook_fp` | Reciprocal Inversion: `YES_Ask = 1.00 - NO_Bid` (ascending) | Quadratic taker fee: $\lceil 0.07 \times C \times P \times (1 - P) \times 100 \rceil / 100$ |
| **`LIMITLESS`** | Base L2 micro-units ($10^6$) | Scale `/ 1,000,000.0`, sort bids desc, asks asc | 10 bps volume taker fee + Base L2 gas (~$0.004/tx) |
| **`PREDICTIT`** | Integer cents `[1¢–99¢]` | Divide by $100.0$ to canonical decimal probability | 10% fee on net profit: $0.10 \times C \times (1.00 - P)$ |
| **`DRIFT_BET`** | Solana DEX order books | Decimal probability ladder with 20-level depth | 5 bps volume taker fee + Solana priority gas (~$0.001/tx) |
| **`SMARKETS`** | European odds / bps | Invert decimal odds or scale basis points | 2% (200 bps) flat commission on net market profit |

---

## Production Tiers & Quotas

| Tier | Price | Rate Limit | Historical Lookback | Daily Row Quota | Key Features |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Hobbyist** | **$0/mo** | `30 req/min` | `24h` lookback | `50,000` rows/day | Open-source SDK access, top liquid markets |
| **Quant Pro** | **$30/mo** | `180 req/min` | `90d` lookback | `1,000,000` rows/day | Real-time WebSocket streams, cross-venue pair scanner |
| **Institutional** | **$100/mo** | `600 req/min` | Unlimited all-time | `10,000,000` rows/day | Priority endpoints, instant Telegram/Discord webhook alerts |

Set your API key via environment variable:
```bash
export NAXOS_API_KEY="nx_live_..."
```

---

## Async Client Usage

```python
import asyncio
import os
from naxosdata import AsyncNaxosClient, Venue

async def main():
    async with AsyncNaxosClient(api_key=os.getenv("NAXOS_API_KEY", "nx_live_demo")) as client:
        markets = await client.get_markets(venue=Venue.POLYMARKET)
        print(f"Discovered {len(markets)} active Polymarket contracts")

        usage = await client.get_usage()
        print(f"Active Tier: {usage.tier} | Requests today: {usage.requests_today} / {usage.rate_limit_per_min} req/min")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## License

MIT © [NaxosData.com](https://naxosdata.com)
