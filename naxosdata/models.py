"""Pydantic Models and Data Types for NaxosData SDK."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class RecordList(List[T]):
    """A list of typed records that provides convenient conversion to pandas DataFrames and dicts."""

    def to_dataframe(self) -> Any:
        """Convert list of records to a pandas DataFrame if pandas is installed."""
        try:
            import pandas as pd
            records = [item.model_dump() if hasattr(item, "model_dump") else item for item in self]
            return pd.DataFrame(records)
        except ImportError:
            raise ImportError(
                "pandas is required for .to_dataframe(). Install via 'pip install pandas' or 'pip install naxosdata[backtest]'."
            )

    def to_records(self) -> List[Dict[str, Any]]:
        """Return list of dict representations."""
        return [item.model_dump() if hasattr(item, "model_dump") else dict(item) for item in self]


class Venue(str, Enum):
    """Supported prediction market trading venues."""
    POLYMARKET = "POLYMARKET"
    KALSHI = "KALSHI"
    LIMITLESS = "LIMITLESS"
    PREDICTIT = "PREDICTIT"
    DRIFT_BET = "DRIFT_BET"
    SMARKETS = "SMARKETS"
    FORECASTX = "FORECASTX"
    ALL = "ALL"


class StrategyType(str, Enum):
    """Supported prediction market backtesting strategy archetypes."""
    CROSS_VENUE_ARB = "CROSS_VENUE_ARB"
    MARKET_MAKING = "MARKET_MAKING"
    ORDERFLOW_IMBALANCE = "ORDERFLOW_IMBALANCE"
    RESOLUTION_CARRY = "RESOLUTION_CARRY"
    CUSTOM_STRATEGY = "CUSTOM_STRATEGY"


class L2OrderLevel(BaseModel):
    """Normalized Level 2 price level."""
    model_config = ConfigDict(extra="ignore")

    price: float
    size: float
    total: Optional[float] = None
    notional: Optional[float] = None


class OrderBookSnapshot(BaseModel):
    """Normalized L2 Order Book Snapshot."""
    model_config = ConfigDict(extra="ignore")

    venue: str
    market_id: str
    pair_id: Optional[str] = None
    title: Optional[str] = None
    timestamp_ms: int = 0
    wire_lag_ms: int = 0
    seq_num: int = 1
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread_bps: float = 0.0
    mid_price_yes: Optional[float] = None
    bids_yes_prices: List[float] = Field(default_factory=list)
    bids_yes_sizes: List[float] = Field(default_factory=list)
    asks_yes_prices: List[float] = Field(default_factory=list)
    asks_yes_sizes: List[float] = Field(default_factory=list)
    bids: List[L2OrderLevel] = Field(default_factory=list)
    asks: List[L2OrderLevel] = Field(default_factory=list)
    is_live_recorded: bool = False

    def to_dataframe(self) -> Any:
        """Export bids and asks depth ladder to a pandas DataFrame."""
        try:
            import pandas as pd
            bids_df = pd.DataFrame([b.model_dump() for b in self.bids])
            bids_df["side"] = "BID"
            asks_df = pd.DataFrame([a.model_dump() for a in self.asks])
            asks_df["side"] = "ASK"
            return pd.concat([bids_df, asks_df], ignore_index=True)
        except ImportError:
            raise ImportError("pandas is required for .to_dataframe().")


class Market(BaseModel):
    """Market metadata and latest price/orderbook telemetry."""
    model_config = ConfigDict(extra="ignore")

    id: str
    market_id: Optional[str] = None
    pair_id: Optional[str] = None
    title: str
    subtitle: Optional[str] = ""
    category: str = "Macro"
    venue: str
    symbol: Optional[str] = None
    expiry: Optional[str] = None
    expiration_ts_ms: Optional[int] = None
    status: str = "ACTIVE"
    resolution_outcome: Optional[str] = None
    oracle: Optional[str] = None
    fungibility_score: Optional[int] = 0
    fungibility_breakdown: Optional[Dict[str, Any]] = None
    fungibility_notes: Optional[str] = None
    current_price: float = 0.5
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread_bps: float = 0.0
    volume_24h: float = 0.0
    open_interest: float = 0.0
    vwap_1h: Optional[float] = None
    fee_bps: float = 0.0
    wire_lag_ms: int = 14
    seq_num: int = 1
    resolution_source_url: Optional[str] = ""
    is_live_recorded: bool = False
    l2_snapshots: Optional[List[Dict[str, Any]]] = None
    time_series_1h: Optional[List[Dict[str, Any]]] = None
    time_series_24h: Optional[List[Dict[str, Any]]] = None
    time_series_7d: Optional[List[Dict[str, Any]]] = None
    time_series_30d: Optional[List[Dict[str, Any]]] = None


class ArbitragePair(BaseModel):
    """Cross-venue matched arbitrage pair opportunity."""
    model_config = ConfigDict(extra="ignore")

    pair_id: str
    event_title: str = ""
    category: str = "Macro"
    venue_long: str
    venue_short: str
    long_ask: float = 0.0
    short_bid: float = 0.0
    spread_cents: float = 0.0
    gross_spread_bps: float = 0.0
    net_roi_pct: float = 0.0
    combined_liquidity_usd: float = 0.0
    fungibility_score: int = 0
    risk_rating: str = "LOW_RISK"
    oracle_long: Optional[str] = None
    oracle_short: Optional[str] = None
    rule_discrepancy: Optional[str] = None
    market_id_long: str = ""
    market_id_short: str = ""
    is_live_recorded: bool = False
    arb_count_24h: int = 0
    avg_duration_sec: float = 0.0


class BacktestSummary(BaseModel):
    """Key performance metrics from backtest simulation."""
    model_config = ConfigDict(extra="ignore")

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_pct: float = 0.0
    starting_bankroll: float = 0.0
    final_equity: float = 0.0
    net_profit_usd: float = 0.0
    roi_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_trade_duration_sec: float = 0.0
    total_fees_paid_usd: float = 0.0
    escape_sweeps_executed: int = 0
    unwinds_executed: int = 0
    rebalancer_actions: int = 0
    strategy_type: Optional[str] = "CROSS_VENUE_ARB"


class BacktestResult(BaseModel):
    """Comprehensive backtest execution result."""
    model_config = ConfigDict(extra="ignore")

    status: str = "success"
    pair_id: Optional[str] = None
    data_source: Optional[str] = "archive"
    duration_days: Optional[float] = 30.0
    strategy_type: Optional[str] = "CROSS_VENUE_ARB"
    strategy_config: Dict[str, Any] = Field(default_factory=dict)
    strategy_telemetry: Dict[str, Any] = Field(default_factory=dict)
    stats: Dict[str, Any] = Field(default_factory=dict)
    trades: List[Dict[str, Any]] = Field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    telemetry: Dict[str, Any] = Field(default_factory=dict)

    @property
    def net_profit(self) -> float:
        """Net profit in USD."""
        if "net_profit_usd" in self.stats:
            return float(self.stats["net_profit_usd"])
        if "total_realized_pnl" in self.telemetry:
            return float(self.telemetry["total_realized_pnl"])
        return 0.0

    @property
    def final_equity(self) -> float:
        """Final portfolio equity in USD."""
        if "final_equity" in self.stats:
            return float(self.stats["final_equity"])
        if "final_equity" in self.telemetry:
            return float(self.telemetry["final_equity"])
        return 0.0

    @property
    def win_rate(self) -> float:
        """Win rate percentage."""
        if "win_rate_pct" in self.stats:
            return float(self.stats["win_rate_pct"])
        if "win_rate_pct" in self.telemetry:
            return float(self.telemetry["win_rate_pct"])
        return 0.0

    @property
    def roi_pct(self) -> float:
        """Return on investment percentage."""
        if "roi_pct" in self.stats:
            return float(self.stats["roi_pct"])
        if "net_roi_pct" in self.telemetry:
            return float(self.telemetry["net_roi_pct"])
        return 0.0

    @property
    def sharpe(self) -> float:
        """Annualized Sharpe ratio."""
        if "sharpe_ratio" in self.stats:
            return float(self.stats["sharpe_ratio"])
        if "sharpe_ratio" in self.telemetry:
            return float(self.telemetry["sharpe_ratio"])
        return 0.0

    def summary(self) -> Dict[str, Any]:
        """Return the performance summary metrics dictionary."""
        if self.stats:
            return self.stats
        lifecycle = self.telemetry.get("position_lifecycle", {})
        return {
            "starting_bankroll": self.telemetry.get("initial_bankroll", 0.0),
            "final_equity": self.final_equity,
            "net_profit_usd": self.net_profit,
            "roi_pct": self.roi_pct,
            "win_rate_pct": self.win_rate,
            "annualized_apy": self.telemetry.get("annualized_apy", 0.0),
            "frames_replayed": self.telemetry.get("frames_replayed", 0),
            "total_trades": lifecycle.get("positions_opened", 0),
            "winning_trades": lifecycle.get("early_exits", 0),
            "losing_trades": lifecycle.get("scratch_unwinds", 0),
        }

    def to_dataframe(self) -> Any:
        """Convert equity curve to pandas DataFrame."""
        try:
            import pandas as pd
            return pd.DataFrame(self.equity_curve)
        except ImportError:
            raise ImportError("pandas is required for .to_dataframe().")


class UsageTelemetry(BaseModel):
    """Institutional API Key Quota and Rate Limit Telemetry."""
    model_config = ConfigDict(extra="ignore")

    status: str = "success"
    api_key_prefix: str
    tier: Dict[str, Any]
    requests_today: int
    requests_this_minute: int
    rate_limit_remaining: int
    rows_used: int
    rows_limit: int
    rows_remaining: int
    quota_utilization_pct: float


class KalshiBreakevenResult(BaseModel):
    """Result of exact nonlinear Kalshi taker fee and breakeven calculation."""
    model_config = ConfigDict(extra="ignore")

    poly_yes_price: float
    target_roi_pct: float
    max_kalshi_no_price: float
    kalshi_fee_cents: float
    poly_fee_cents: float
    gross_edge_cents: float
    net_edge_cents: float
    total_cost_per_pair: float

