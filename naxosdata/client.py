"""Client implementations for NaxosData API (synchronous and asynchronous)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union
import httpx
import requests

from naxosdata.exceptions import (
    AuthenticationError,
    NaxosAPIError,
    NotFoundError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)
from naxosdata.models import (
    ArbitragePair,
    BacktestResult,
    Market,
    OrderBookSnapshot,
    RecordList,
    StrategyType,
    UsageTelemetry,
    Venue,
)

DEFAULT_BASE_URL = "http://localhost:3000/api/v1"
LOCAL_FALLBACK_URLS = ["http://127.0.0.1:3000/api/v1", "http://localhost:3000/api/v1"]
PRODUCTION_BASE_URL = "https://api.naxosdata.com/v1"


def _resolve_base_url(base_url: Optional[str] = None) -> str:
    """Resolve API base URL respecting env variables and local availability."""
    if base_url:
        return base_url.rstrip("/")
    env_url = os.getenv("NAXOS_BASE_URL")
    if env_url:
        return env_url.rstrip("/")

    # Check if local Next.js dev server is reachable
    for local_url in LOCAL_FALLBACK_URLS:
        try:
            r = requests.get(f"{local_url}/health", headers={"Authorization": "Bearer nx_live_probe"}, timeout=0.3)
            if r.status_code in (200, 401, 404):
                return local_url
        except Exception:
            pass

    return PRODUCTION_BASE_URL


def _handle_error_response(status_code: int, data: Dict[str, Any], headers: Dict[str, str]) -> None:
    """Raise appropriate typed exception based on HTTP status code and response payload."""
    message = data.get("message") or data.get("error") or f"HTTP error {status_code}"
    headers_lower = {k.lower(): str(v) for k, v in headers.items()}
    if status_code in (401, 403):
        raise AuthenticationError(message, status_code, data, headers)
    elif status_code == 429:
        retry_after = headers_lower.get("retry-after")
        sec = None
        if retry_after:
            try:
                sec = int(float(retry_after))
            except (ValueError, TypeError):
                sec = None
        if "quota" in message.lower() or "row" in message.lower():
            raise QuotaExceededError(message, status_code, data, headers)
        raise RateLimitError(message, status_code, sec, data, headers)
    elif status_code == 404:
        raise NotFoundError(message, status_code, data, headers)
    elif status_code >= 500:
        raise ServerError(message, status_code, data, headers)
    else:
        raise NaxosAPIError(message, status_code, data, headers)


class _MarketsResource:
    def __init__(self, client: NaxosClient):
        self._client = client

    def list(
        self,
        venue: Optional[Union[str, Venue]] = None,
        category: Optional[str] = None,
        live_only: bool = False,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> RecordList[Market]:
        return self._client.get_markets(
            venue=venue,
            category=category,
            live_only=live_only,
            status=status,
            search=search,
        )


class _OrderbooksResource:
    def __init__(self, client: NaxosClient):
        self._client = client

    def snapshot(
        self,
        venue: Union[str, Venue],
        market_id: str,
        timestamp_ms: Optional[int] = None,
    ) -> OrderBookSnapshot:
        return self._client.get_orderbook_snapshot(
            venue=venue,
            market_id=market_id,
            timestamp_ms=timestamp_ms,
        )


class _PairsResource:
    def __init__(self, client: NaxosClient):
        self._client = client

    def list(
        self,
        min_fungibility: int = 0,
        venue_pair: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> RecordList[ArbitragePair]:
        return self._client.get_pairs(
            min_fungibility=min_fungibility,
            venue_pair=venue_pair,
            category=category,
            search=search,
        )

    def comparison(self, pair_id: str) -> ArbitragePair:
        pairs = self._client.get_pairs(search=pair_id)
        for p in pairs:
            if p.pair_id.lower() == pair_id.lower():
                return p
        if pairs:
            return pairs[0]
        raise NotFoundError(f"Arbitrage pair '{pair_id}' not found.")


class _BacktestResource:
    def __init__(self, client: NaxosClient):
        self._client = client

    def run(
        self,
        pair_id: Optional[str] = None,
        bankroll: float = 1000.0,
        min_spread_cents: float = 1.5,
        latency_ms: float = 35.0,
        enable_escape_sweeps: bool = True,
        enable_rebalancer: bool = True,
        data_source: str = "archive",
        strategy_type: Union[str, StrategyType] = StrategyType.CROSS_VENUE_ARB,
        strategy_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BacktestResult:
        return self._client.run_backtest(
            pair_id=pair_id,
            bankroll=bankroll,
            min_spread_cents=min_spread_cents,
            latency_ms=latency_ms,
            enable_escape_sweeps=enable_escape_sweeps,
            enable_rebalancer=enable_rebalancer,
            data_source=data_source,
            strategy_type=strategy_type,
            strategy_config=strategy_config,
            **kwargs,
        )


class NaxosClient:
    """Synchronous Client for NaxosData REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
        auto_retry_rate_limit: bool = False,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("NAXOS_API_KEY") or "nx_live_default"
        self.base_url = _resolve_base_url(base_url)
        self.timeout = timeout
        self.auto_retry_rate_limit = auto_retry_rate_limit
        self.max_retries = max_retries
        self.session = requests.Session()
        self.last_rate_limit_info: Dict[str, Any] = {}

        # Namespace helpers
        self.markets = _MarketsResource(self)
        self.orderbooks = _OrderbooksResource(self)
        self.pairs = _PairsResource(self)
        self.backtest = _BacktestResource(self)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Naxos-API-Key": self.api_key,
            "User-Agent": "naxosdata-python/1.4.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _update_rate_limit_info(self, headers: Any) -> None:
        headers_lower = {k.lower(): str(v) for k, v in dict(headers).items()}
        self.last_rate_limit_info = {
            "limit": headers_lower.get("x-ratelimit-limit"),
            "remaining": headers_lower.get("x-ratelimit-remaining"),
            "quota_used": headers_lower.get("x-quota-rows-used") or headers_lower.get("x-quota-daily-used"),
            "quota_limit": headers_lower.get("x-quota-rows-limit") or headers_lower.get("x-quota-daily-limit"),
            "quota_remaining": headers_lower.get("x-quota-remaining") or headers_lower.get("x-quota-daily-remaining"),
            "retry_after": headers_lower.get("retry-after"),
            "latency_ms": headers_lower.get("x-naxos-latency-ms"),
            "security_score": headers_lower.get("x-security-score"),
            "account_status": headers_lower.get("x-account-status"),
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        retries_left = self.max_retries if self.auto_retry_rate_limit else 0
        backoff_sec = 1.0

        try:
            while True:
                resp = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                self._update_rate_limit_info(resp.headers)
                try:
                    data = resp.json()
                except Exception:
                    data = {"message": resp.text}

                if resp.status_code == 429 and retries_left > 0:
                    retries_left -= 1
                    retry_after = resp.headers.get("Retry-After")
                    try:
                        wait_sec = float(retry_after) if retry_after else backoff_sec
                    except (ValueError, TypeError):
                        wait_sec = backoff_sec
                    time.sleep(min(max(0.0, wait_sec), 30.0))
                    backoff_sec = min(backoff_sec * 2.0, 30.0)
                    continue

                if not resp.ok:
                    _handle_error_response(resp.status_code, data, dict(resp.headers))

                return data
        except requests.RequestException as e:
            if isinstance(e, (requests.ConnectionError, requests.Timeout)):
                # If production URL failed, attempt automatic local fallback
                if self.base_url == PRODUCTION_BASE_URL:
                    for fallback in LOCAL_FALLBACK_URLS:
                        try:
                            resp = self.session.request(
                                method=method,
                                url=f"{fallback}/{path.lstrip('/')}",
                                params=params,
                                json=json_data,
                                headers=self._headers(),
                                timeout=self.timeout,
                            )
                            self.base_url = fallback
                            self._update_rate_limit_info(resp.headers)
                            try:
                                fallback_data = resp.json()
                            except Exception:
                                fallback_data = {"message": resp.text}

                            if not resp.ok:
                                _handle_error_response(resp.status_code, fallback_data, dict(resp.headers))

                            return fallback_data
                        except requests.RequestException:
                            continue
            raise NaxosAPIError(f"HTTP request to {url} failed: {e}")

    def get_markets(
        self,
        venue: Optional[Union[str, Venue]] = None,
        category: Optional[str] = None,
        live_only: bool = False,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> RecordList[Market]:
        """Fetch list of markets matching optional filter criteria."""
        params: Dict[str, Any] = {}
        if venue:
            v_val = venue.value if isinstance(venue, Venue) else str(venue)
            if v_val.upper() != "ALL":
                params["venue"] = v_val.upper()
        if category and category.upper() != "ALL":
            params["category"] = category
        if live_only:
            params["only_recorded"] = "true"
        if status and status.upper() != "ALL":
            params["status"] = status
        if search:
            params["search"] = search

        data = self._request("GET", "/markets", params=params)
        raw_list = data.get("data", [])
        return RecordList([Market(**m) for m in raw_list])

    def get_orderbook_snapshot(
        self,
        venue: Union[str, Venue],
        market_id: str,
        timestamp_ms: Optional[int] = None,
    ) -> OrderBookSnapshot:
        """Fetch normalized Level 2 order book snapshot for a market."""
        v_str = venue.value if isinstance(venue, Venue) else str(venue)
        path = f"/orderbooks/{v_str.upper()}/{market_id}/snapshot"
        params: Dict[str, Any] = {}
        if timestamp_ms:
            params["timestamp_ms"] = timestamp_ms

        data = self._request("GET", path, params=params)
        return OrderBookSnapshot(**data)

    def get_pairs(
        self,
        min_fungibility: int = 0,
        venue_pair: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        live_only: bool = False,
    ) -> RecordList[ArbitragePair]:
        """Fetch discovered cross-venue matched arbitrage pairs."""
        params: Dict[str, Any] = {}
        if category and category.upper() != "ALL":
            params["category"] = category
        if search:
            params["search"] = search
        if live_only:
            params["only_recorded"] = "true"

        data = self._request("GET", "/pairs", params=params)
        raw_list = data.get("data", [])
        pairs: List[ArbitragePair] = []
        for p in raw_list:
            score = int(p.get("fungibility_score", 0))
            if score < min_fungibility:
                continue
            if venue_pair:
                vp = venue_pair.upper()
                v_long = str(p.get("venue_long", "")).upper()
                v_short = str(p.get("venue_short", "")).upper()
                if vp not in f"{v_long}_{v_short}" and vp not in f"{v_short}_{v_long}":
                    continue
            pairs.append(ArbitragePair(**p))
        return RecordList(pairs)

    def run_backtest(
        self,
        pair_id: Optional[str] = None,
        bankroll: float = 1000.0,
        min_spread_cents: float = 1.5,
        latency_ms: float = 35.0,
        enable_escape_sweeps: bool = True,
        enable_rebalancer: bool = True,
        data_source: str = "archive",
        strategy_type: Union[str, StrategyType] = StrategyType.CROSS_VENUE_ARB,
        strategy_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BacktestResult:
        """Execute discrete event-driven backtest against archive tape."""
        st_str = strategy_type.value if isinstance(strategy_type, StrategyType) else str(strategy_type)
        cfg = dict(strategy_config or {})
        cfg.update(kwargs)
        body: Dict[str, Any] = {
            "pair_id": pair_id,
            "bankroll": bankroll,
            "min_spread_cents": min_spread_cents,
            "latency_ms": latency_ms,
            "enable_escape_sweeps": enable_escape_sweeps,
            "enable_rebalancer": enable_rebalancer,
            "data_source": data_source,
            "strategy_type": st_str,
            "strategy_config": cfg,
        }
        for k, v in cfg.items():
            if k not in body:
                body[k] = v
        data = self._request("POST", "/backtest", json_data=body)
        return BacktestResult(**data)

    def get_usage(self) -> UsageTelemetry:
        """Fetch active API key rate limits, daily requests, and row quota utilization."""
        data = self._request("GET", "/usage")
        return UsageTelemetry(**data)

    def get_health(self) -> Dict[str, Any]:
        """Fetch live recorder daemon heartbeat and archive storage status."""
        return self._request("GET", "/health")


class AsyncNaxosClient:
    """Asynchronous Client for NaxosData REST API using HTTPX."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
        auto_retry_rate_limit: bool = False,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("NAXOS_API_KEY") or "nx_live_default"
        self.base_url = _resolve_base_url(base_url)
        self.timeout = timeout
        self.auto_retry_rate_limit = auto_retry_rate_limit
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self.last_rate_limit_info: Dict[str, Any] = {}

    async def __aenter__(self) -> AsyncNaxosClient:
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Naxos-API-Key": self.api_key,
            "User-Agent": "naxosdata-python/1.4.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _update_rate_limit_info(self, headers: Any) -> None:
        headers_lower = {k.lower(): str(v) for k, v in dict(headers).items()}
        self.last_rate_limit_info = {
            "limit": headers_lower.get("x-ratelimit-limit"),
            "remaining": headers_lower.get("x-ratelimit-remaining"),
            "quota_used": headers_lower.get("x-quota-rows-used") or headers_lower.get("x-quota-daily-used"),
            "quota_limit": headers_lower.get("x-quota-rows-limit") or headers_lower.get("x-quota-daily-limit"),
            "quota_remaining": headers_lower.get("x-quota-remaining") or headers_lower.get("x-quota-daily-remaining"),
            "retry_after": headers_lower.get("retry-after"),
            "latency_ms": headers_lower.get("x-naxos-latency-ms"),
            "security_score": headers_lower.get("x-security-score"),
            "account_status": headers_lower.get("x-account-status"),
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        close_after = False
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
            close_after = True

        url = f"{self.base_url}/{path.lstrip('/')}"
        retries_left = self.max_retries if self.auto_retry_rate_limit else 0
        backoff_sec = 1.0

        try:
            while True:
                resp = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=self._headers(),
                )
                self._update_rate_limit_info(resp.headers)
                try:
                    data = resp.json()
                except Exception:
                    data = {"message": resp.text}

                if resp.status_code == 429 and retries_left > 0:
                    retries_left -= 1
                    retry_after = resp.headers.get("Retry-After")
                    try:
                        wait_sec = float(retry_after) if retry_after else backoff_sec
                    except (ValueError, TypeError):
                        wait_sec = backoff_sec
                    await asyncio.sleep(min(max(0.0, wait_sec), 30.0))
                    backoff_sec = min(backoff_sec * 2.0, 30.0)
                    continue

                if not resp.is_success:
                    _handle_error_response(resp.status_code, data, dict(resp.headers))

                return data
        except httpx.RequestError as e:
            if self.base_url == PRODUCTION_BASE_URL:
                for fallback_url_base in LOCAL_FALLBACK_URLS:
                    try:
                        fallback_url = f"{fallback_url_base}/{path.lstrip('/')}"
                        resp = await self._client.request(
                            method=method,
                            url=fallback_url,
                            params=params,
                            json=json_data,
                            headers=self._headers(),
                        )
                        self.base_url = fallback_url_base
                        self._update_rate_limit_info(resp.headers)
                        try:
                            fallback_data = resp.json()
                        except Exception:
                            fallback_data = {"message": resp.text}

                        if not resp.is_success:
                            _handle_error_response(resp.status_code, fallback_data, dict(resp.headers))

                        return fallback_data
                    except httpx.RequestError:
                        continue
            raise NaxosAPIError(f"Async HTTP request to {url} failed: {e}")
        finally:
            if close_after and self._client:
                await self._client.aclose()
                self._client = None

    async def get_markets(
        self,
        venue: Optional[Union[str, Venue]] = None,
        category: Optional[str] = None,
        live_only: bool = False,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> RecordList[Market]:
        params: Dict[str, Any] = {}
        if venue:
            v_val = venue.value if isinstance(venue, Venue) else str(venue)
            if v_val.upper() != "ALL":
                params["venue"] = v_val.upper()
        if category and category.upper() != "ALL":
            params["category"] = category
        if live_only:
            params["only_recorded"] = "true"
        if status and status.upper() != "ALL":
            params["status"] = status
        if search:
            params["search"] = search

        data = await self._request("GET", "/markets", params=params)
        return RecordList([Market(**m) for m in data.get("data", [])])

    async def get_orderbook_snapshot(
        self,
        venue: Union[str, Venue],
        market_id: str,
        timestamp_ms: Optional[int] = None,
    ) -> OrderBookSnapshot:
        v_str = venue.value if isinstance(venue, Venue) else str(venue)
        path = f"/orderbooks/{v_str.upper()}/{market_id}/snapshot"
        params: Dict[str, Any] = {}
        if timestamp_ms:
            params["timestamp_ms"] = timestamp_ms

        data = await self._request("GET", path, params=params)
        return OrderBookSnapshot(**data)

    async def get_pairs(
        self,
        min_fungibility: int = 0,
        venue_pair: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        live_only: bool = False,
    ) -> RecordList[ArbitragePair]:
        params: Dict[str, Any] = {}
        if category and category.upper() != "ALL":
            params["category"] = category
        if search:
            params["search"] = search
        if live_only:
            params["only_recorded"] = "true"

        data = await self._request("GET", "/pairs", params=params)
        raw_list = data.get("data", [])
        pairs: List[ArbitragePair] = []
        for p in raw_list:
            score = int(p.get("fungibility_score", 0))
            if score < min_fungibility:
                continue
            if venue_pair:
                vp = venue_pair.upper()
                v_long = str(p.get("venue_long", "")).upper()
                v_short = str(p.get("venue_short", "")).upper()
                if vp not in f"{v_long}_{v_short}" and vp not in f"{v_short}_{v_long}":
                    continue
            pairs.append(ArbitragePair(**p))
        return RecordList(pairs)

    async def run_backtest(
        self,
        pair_id: Optional[str] = None,
        bankroll: float = 1000.0,
        min_spread_cents: float = 1.5,
        latency_ms: float = 35.0,
        enable_escape_sweeps: bool = True,
        enable_rebalancer: bool = True,
        data_source: str = "archive",
        strategy_type: Union[str, StrategyType] = StrategyType.CROSS_VENUE_ARB,
        strategy_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BacktestResult:
        st_str = strategy_type.value if isinstance(strategy_type, StrategyType) else str(strategy_type)
        cfg = dict(strategy_config or {})
        cfg.update(kwargs)
        body: Dict[str, Any] = {
            "pair_id": pair_id,
            "bankroll": bankroll,
            "min_spread_cents": min_spread_cents,
            "latency_ms": latency_ms,
            "enable_escape_sweeps": enable_escape_sweeps,
            "enable_rebalancer": enable_rebalancer,
            "data_source": data_source,
            "strategy_type": st_str,
            "strategy_config": cfg,
        }
        for k, v in cfg.items():
            if k not in body:
                body[k] = v
        data = await self._request("POST", "/backtest", json_data=body)
        return BacktestResult(**data)

    async def get_usage(self) -> UsageTelemetry:
        data = await self._request("GET", "/usage")
        return UsageTelemetry(**data)

    async def get_health(self) -> Dict[str, Any]:
        return await self._request("GET", "/health")

    async def stream_orderbook(
        self,
        venue: Union[str, Venue],
        market_id: str,
        interval_sec: float = 0.5,
        max_ticks: Optional[int] = None,
    ) -> AsyncIterator[OrderBookSnapshot]:
        """Async generator yielding real-time order book snapshots."""
        ticks_yielded = 0
        while max_ticks is None or ticks_yielded < max_ticks:
            snap = await self.get_orderbook_snapshot(venue=venue, market_id=market_id)
            yield snap
            ticks_yielded += 1
            import asyncio
            await asyncio.sleep(interval_sec)
