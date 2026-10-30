"""NaxosData Python SDK.

Institutional Tick Archive & Normalized Real-Time API for Polymarket, Kalshi, Limitless, and ForecastEx.
"""

from naxosdata.client import AsyncNaxosClient, NaxosClient
from naxosdata.exceptions import (
    AuthenticationError,
    NaxosAPIError,
    NotFoundError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)
from naxosdata.fee_math import (
    calculate_kalshi_breakeven,
    calculate_kalshi_breakeven_spread,
    calculate_kalshi_taker_fee,
)
from naxosdata.models import (
    ArbitragePair,
    BacktestResult,
    BacktestSummary,
    KalshiBreakevenResult,
    L2OrderLevel,
    Market,
    OrderBookSnapshot,
    RecordList,
    StrategyType,
    UsageTelemetry,
    Venue,
)

__version__ = "1.4.0"
__all__ = [
    "NaxosClient",
    "AsyncNaxosClient",
    "Venue",
    "StrategyType",
    "Market",
    "OrderBookSnapshot",
    "L2OrderLevel",
    "ArbitragePair",
    "BacktestResult",
    "BacktestSummary",
    "KalshiBreakevenResult",
    "calculate_kalshi_taker_fee",
    "calculate_kalshi_breakeven",
    "calculate_kalshi_breakeven_spread",
    "UsageTelemetry",
    "RecordList",
    "NaxosAPIError",
    "AuthenticationError",
    "RateLimitError",
    "QuotaExceededError",
    "NotFoundError",
    "ServerError",
]
