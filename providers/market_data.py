"""
Market data provider for the Crypto Intelligence Agent.
Supports CoinGecko, Binance, DexScreener, and GeckoTerminal.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

import httpx
import ccxt.async_support as ccxt
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.config import get_settings, MarketDataSettings


class DataSource(str, Enum):
    COINGECKO = "coingecko"
    BINANCE = "binance"
    DEXSCREENER = "dexscreener"
    GECKOTERMINAL = "geckoterminal"
    CCXT = "ccxt"


@dataclass
class CoinInfo:
    id: str
    symbol: str
    name: str
    image: Optional[str] = None
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    market_cap_rank: Optional[int] = None
    total_volume: Optional[float] = None
    price_change_24h: Optional[float] = None
    price_change_percentage_24h: Optional[float] = None
    price_change_percentage_7d: Optional[float] = None
    price_change_percentage_30d: Optional[float] = None
    fully_diluted_valuation: Optional[float] = None
    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    ath: Optional[float] = None
    atl: Optional[float] = None
    last_updated: Optional[datetime] = None
    source: DataSource = DataSource.COINGECKO


@dataclass
class OHLCVData:
    symbol: str
    timeframe: str
    timestamps: List[int]
    opens: List[float]
    highs: List[float]
    lows: List[float]
    closes: List[float]
    volumes: List[float]
    source: DataSource = DataSource.COINGECKO
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MarketOverview:
    total_market_cap: float
    total_volume_24h: float
    btc_dominance: float
    eth_dominance: float
    market_cap_change_24h: float
    active_cryptocurrencies: int
    markets: int
    fetched_at: datetime = field(default_factory=datetime.utcnow)


class MarketDataError(Exception):
    """Base exception for market data errors."""
    pass


class RateLimitError(MarketDataError):
    """Rate limit exceeded."""
    pass


class MarketDataProvider:
    """Unified market data provider with multiple sources and fallback."""
    
    def __init__(self, settings: Optional[MarketDataSettings] = None):
        self.settings = settings or get_settings().market_data
        self._client: Optional[httpx.AsyncClient] = None
        self._ccxt_exchanges: Dict[str, ccxt.Exchange] = {}
        self._rate_limits: Dict[str, float] = {}  # source -> last request time
        self._cooldowns: Dict[str, float] = {}  # source -> unix time before which we must not call
        self._cache: Dict[str, tuple[Any, float]] = {}  # key -> (data, timestamp)
        self._cache_ttl = 60  # seconds
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
            )
        return self._client
    
    async def close(self) -> None:
        """Close all connections."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        for exchange in self._ccxt_exchanges.values():
            await exchange.close()
        self._ccxt_exchanges.clear()
    
    async def _check_rate_limit(self, source: str, rate_limit: int) -> None:
        """Check and enforce rate limits by waiting the required interval."""
        now = time.time()
        min_interval = 60.0 / rate_limit if rate_limit > 0 else 0

        # Honor an active cooldown set after an upstream 429.
        cooldown_until = self._cooldowns.get(source, 0.0)
        if cooldown_until > now:
            await asyncio.sleep(cooldown_until - now)
            now = time.time()

        last_request = self._rate_limits.get(source, 0)
        wait_time = min_interval - (now - last_request)
        
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        self._rate_limits[source] = time.time()
    
    def _get_cache_key(self, source: str, endpoint: str, params: Dict) -> str:
        """Generate cache key."""
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{source}:{endpoint}?{param_str}"
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return data
            else:
                del self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: Any) -> None:
        """Cache data with timestamp."""
        self._cache[key] = (data, time.time())
    
    # ===========================================
    # CoinGecko API
    # ===========================================
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, RateLimitError))
    )
    async def _coingecko_request(self, endpoint: str, params: Dict = None) -> Any:
        """Make a request to CoinGecko API."""
        await self._check_rate_limit("coingecko", self.settings.coingecko.rate_limit)
        
        client = await self._get_client()
        headers = {}
        if self.settings.coingecko.api_key:
            headers["x-cg-demo-api-key"] = self.settings.coingecko.api_key
        
        url = f"{self.settings.coingecko.base_url}{endpoint}"
        response = await client.get(url, params=params or {}, headers=headers)
        
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 20.0
            except ValueError:
                delay = 20.0
            # Anonymous/free tiers can throttle for a while: cool down before the
            # next call instead of hammering the endpoint.
            delay = max(15.0, min(delay, 60.0))
            self._cooldowns["coingecko"] = time.time() + delay
            raise RateLimitError(f"CoinGecko rate limited, cooling down {delay:.0f}s")
        elif response.status_code >= 400:
            raise MarketDataError(f"CoinGecko error: {response.status_code} - {response.text}")
        
        return response.json()
    
    async def get_coins_list(self, include_platform: bool = False) -> List[Dict]:
        """Get list of all coins from CoinGecko."""
        cache_key = self._get_cache_key("coingecko", "/coins/list", {"include_platform": str(include_platform).lower()})
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        data = await self._coingecko_request("/coins/list", {"include_platform": str(include_platform).lower()})
        self._set_cache(cache_key, data)
        return data
    
    async def get_market_overview(self) -> MarketOverview:
        """Get global market overview."""
        cache_key = self._get_cache_key("coingecko", "/global", {})
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        data = await self._coingecko_request("/global")
        global_data = data.get("data", {})
        
        overview = MarketOverview(
            total_market_cap=global_data.get("total_market_cap", {}).get("usd", 0),
            total_volume_24h=global_data.get("total_volume", {}).get("usd", 0),
            btc_dominance=global_data.get("market_cap_percentage", {}).get("btc", 0),
            eth_dominance=global_data.get("market_cap_percentage", {}).get("eth", 0),
            market_cap_change_24h=global_data.get("market_cap_change_percentage_24h_usd", 0),
            active_cryptocurrencies=global_data.get("active_cryptocurrencies", 0),
            markets=global_data.get("markets", 0)
        )
        self._set_cache(cache_key, overview)
        return overview
    
    async def get_coins_markets(
        self,
        vs_currency: str = "usd",
        ids: Optional[List[str]] = None,
        category: Optional[str] = None,
        order: str = "market_cap_desc",
        per_page: int = 250,
        page: int = 1,
        sparkline: bool = False,
        price_change_percentage: str = "24h,7d,30d"
    ) -> List[CoinInfo]:
        """Get coin market data."""
        params = {
            "vs_currency": vs_currency,
            "order": order,
            "per_page": per_page,
            "page": page,
            "sparkline": str(sparkline).lower(),
            "price_change_percentage": price_change_percentage
        }
        if ids:
            params["ids"] = ",".join(ids)
        if category:
            params["category"] = category
        
        cache_key = self._get_cache_key("coingecko", "/coins/markets", params)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        data = await self._coingecko_request("/coins/markets", params)
        
        coins = []
        for item in data:
            coin = CoinInfo(
                id=item["id"],
                symbol=item["symbol"].upper(),
                name=item["name"],
                image=item.get("image"),
                current_price=item.get("current_price"),
                market_cap=item.get("market_cap"),
                market_cap_rank=item.get("market_cap_rank"),
                total_volume=item.get("total_volume"),
                price_change_24h=item.get("price_change_24h"),
                price_change_percentage_24h=item.get("price_change_percentage_24h"),
                price_change_percentage_7d=item.get("price_change_percentage_7d_in_currency"),
                price_change_percentage_30d=item.get("price_change_percentage_30d_in_currency"),
                fully_diluted_valuation=item.get("fully_diluted_valuation"),
                circulating_supply=item.get("circulating_supply"),
                total_supply=item.get("total_supply"),
                max_supply=item.get("max_supply"),
                ath=item.get("ath", {}).get("usd") if isinstance(item.get("ath"), dict) else item.get("ath"),
                atl=item.get("atl", {}).get("usd") if isinstance(item.get("atl"), dict) else item.get("atl"),
                last_updated=datetime.fromisoformat(item["last_updated"].replace("Z", "+00:00")) if item.get("last_updated") else None,
                source=DataSource.COINGECKO
            )
            coins.append(coin)
        
        self._set_cache(cache_key, coins)
        return coins
    
    async def get_coin_by_id(self, coin_id: str, localization: bool = False, tickers: bool = False, market_data: bool = True, community_data: bool = False, developer_data: bool = False, sparkline: bool = False) -> Optional[CoinInfo]:
        """Get detailed coin info by ID."""
        params = {
            "localization": str(localization).lower(),
            "tickers": str(tickers).lower(),
            "market_data": str(market_data).lower(),
            "community_data": str(community_data).lower(),
            "developer_data": str(developer_data).lower(),
            "sparkline": str(sparkline).lower()
        }
        
        cache_key = self._get_cache_key("coingecko", f"/coins/{coin_id}", params)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            data = await self._coingecko_request(f"/coins/{coin_id}", params)
        except MarketDataError:
            return None
        
        market_data = data.get("market_data", {})
        
        coin = CoinInfo(
            id=data["id"],
            symbol=data["symbol"].upper(),
            name=data["name"],
            image=data.get("image", {}).get("large"),
            current_price=market_data.get("current_price", {}).get("usd"),
            market_cap=market_data.get("market_cap", {}).get("usd"),
            market_cap_rank=data.get("market_cap_rank"),
            total_volume=market_data.get("total_volume", {}).get("usd"),
            price_change_24h=market_data.get("price_change_24h"),
            price_change_percentage_24h=market_data.get("price_change_percentage_24h"),
            price_change_percentage_7d=market_data.get("price_change_percentage_7d"),
            price_change_percentage_30d=market_data.get("price_change_percentage_30d"),
            fully_diluted_valuation=market_data.get("fully_diluted_valuation", {}).get("usd") if isinstance(market_data.get("fully_diluted_valuation"), dict) else market_data.get("fully_diluted_valuation"),
            circulating_supply=market_data.get("circulating_supply"),
            total_supply=market_data.get("total_supply"),
            max_supply=market_data.get("max_supply"),
            ath=market_data.get("ath", {}).get("usd"),
            atl=market_data.get("atl", {}).get("usd"),
            last_updated=datetime.fromisoformat(market_data["last_updated"].replace("Z", "+00:00")) if market_data.get("last_updated") else None,
            source=DataSource.COINGECKO
        )
        
        self._set_cache(cache_key, coin)
        return coin
    
    async def get_coin_ohlcv(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        days: Union[int, str] = 30
    ) -> OHLCVData:
        """Get OHLCV data for a coin.

        Note: CoinGecko's /coins/{id}/ohlc endpoint only accepts a fixed set of
        ``days`` values and returns no volume. Use ``get_binance_klines`` when
        volume is required.
        """
        # CoinGecko only allows these values for the OHLC endpoint.
        allowed_days = [1, 7, 14, 30, 90, 180, 365]
        try:
            requested = int(days)
        except (TypeError, ValueError):
            requested = 365
        requested = max(1, min(requested, 365))
        normalized_days = next((d for d in allowed_days if d >= requested), allowed_days[-1])

        params = {"vs_currency": vs_currency, "days": str(normalized_days)}
        
        cache_key = self._get_cache_key("coingecko", f"/coins/{coin_id}/ohlc", params)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        data = await self._coingecko_request(f"/coins/{coin_id}/ohlc", params)
        
        # CoinGecko returns [timestamp, open, high, low, close]
        timestamps = [int(item[0]) for item in data]
        opens = [item[1] for item in data]
        highs = [item[2] for item in data]
        lows = [item[3] for item in data]
        closes = [item[4] for item in data]
        
        # OHLC endpoint has no volume; fetch total_volumes from market_chart and
        # align them to the OHLC timestamps. If that fails, fall back to zeros.
        volumes = [0.0] * len(data)
        try:
            chart = await self.get_coin_market_chart(coin_id, vs_currency, normalized_days)
            chart_vols = chart.get("total_volumes", []) if isinstance(chart, dict) else []
            if chart_vols:
                vol_by_ts = {int(v[0]): float(v[1]) for v in chart_vols if len(v) >= 2}
                chart_ts = sorted(vol_by_ts)
                for i, ts in enumerate(timestamps):
                    if ts in vol_by_ts:
                        volumes[i] = vol_by_ts[ts]
                    elif chart_ts:
                        nearest = min(chart_ts, key=lambda t: abs(t - ts))
                        volumes[i] = vol_by_ts[nearest]
        except Exception:
            pass
        
        ohlcv = OHLCVData(
            symbol=coin_id.upper(),
            timeframe="1h" if normalized_days == 1 else "1d",
            timestamps=timestamps,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            source=DataSource.COINGECKO
        )
        
        self._set_cache(cache_key, ohlcv)
        return ohlcv
    
    async def get_binance_klines(
        self,
        symbol: str,
        interval: str = "1d",
        limit: int = 500
    ) -> Optional[OHLCVData]:
        """Get OHLCV candles from Binance spot (public, includes volume)."""
        valid = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}
        if interval not in valid:
            interval = "1d"
        
        pair = symbol.upper().replace("/", "")
        if not pair.endswith("USDT"):
            pair += "USDT"
        
        cache_key = self._get_cache_key("binance", "/api/v3/klines", {"symbol": pair, "interval": interval, "limit": limit})
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        data = await self._binance_public_get(
            "https://api.binance.com/api/v3/klines",
            {"symbol": pair, "interval": interval, "limit": max(1, min(limit, 1000))}
        )
        if not isinstance(data, list) or not data:
            return None
        
        ohlcv = OHLCVData(
            symbol=symbol.upper(),
            timeframe=interval,
            timestamps=[int(item[0]) for item in data],
            opens=[float(item[1]) for item in data],
            highs=[float(item[2]) for item in data],
            lows=[float(item[3]) for item in data],
            closes=[float(item[4]) for item in data],
            volumes=[float(item[5]) for item in data],
            source=DataSource.BINANCE
        )
        self._set_cache(cache_key, ohlcv)
        return ohlcv
    
    async def get_coin_market_chart(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        days: Union[int, str] = 30,
        interval: Optional[str] = None
    ) -> Dict[str, List]:
        """Get market chart data (prices, market_caps, total_volumes)."""
        params = {"vs_currency": vs_currency, "days": str(days)}
        if interval:
            params["interval"] = interval
        
        cache_key = self._get_cache_key("coingecko", f"/coins/{coin_id}/market_chart", params)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        data = await self._coingecko_request(f"/coins/{coin_id}/market_chart", params)
        self._set_cache(cache_key, data)
        return data
    
    async def search_coins(self, query: str) -> List[Dict]:
        """Search for coins."""
        params = {"query": query}
        cache_key = self._get_cache_key("coingecko", "/search", params)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        data = await self._coingecko_request("/search", params)
        coins = data.get("coins", [])
        self._set_cache(cache_key, coins)
        return coins
    
    # ===========================================
    # CCXT Exchange Integration
    # ===========================================
    
    async def _get_ccxt_exchange(self, exchange_id: str) -> ccxt.Exchange:
        """Get or create a CCXT exchange instance."""
        if exchange_id not in self._ccxt_exchanges:
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            self._ccxt_exchanges[exchange_id] = exchange
        return self._ccxt_exchanges[exchange_id]
    
    async def get_ccxt_ticker(self, exchange_id: str, symbol: str) -> Dict:
        """Get ticker from a CCXT exchange."""
        exchange = await self._get_ccxt_exchange(exchange_id)
        await exchange.load_markets()
        ticker = await exchange.fetch_ticker(symbol)
        return ticker
    
    async def get_ccxt_ohlcv(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
        since: Optional[int] = None
    ) -> OHLCVData:
        """Get OHLCV from a CCXT exchange."""
        exchange = await self._get_ccxt_exchange(exchange_id)
        await exchange.load_markets()
        
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, since, limit)
        
        timestamps = [int(candle[0]) for candle in ohlcv]
        opens = [candle[1] for candle in ohlcv]
        highs = [candle[2] for candle in ohlcv]
        lows = [candle[3] for candle in ohlcv]
        closes = [candle[4] for candle in ohlcv]
        volumes = [candle[5] for candle in ohlcv]
        
        return OHLCVData(
            symbol=symbol,
            timeframe=timeframe,
            timestamps=timestamps,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            source=DataSource.CCXT
        )
    
    # ===========================================
    # DexScreener API
    # ===========================================
    
    async def get_dexscreener_pairs(self, chain_id: str, token_address: str) -> List[Dict]:
        """Get pairs for a token from DexScreener."""
        client = await self._get_client()
        url = f"{self.settings.dexscreener.base_url}/tokens/{chain_id}/{token_address}"
        response = await client.get(url)
        
        if response.status_code >= 400:
            raise MarketDataError(f"DexScreener error: {response.status_code}")
        
        return response.json().get("pairs", [])
    
    async def search_dexscreener(self, query: str) -> List[Dict]:
        """Search DexScreener."""
        client = await self._get_client()
        url = f"{self.settings.dexscreener.base_url}/search"
        params = {"q": query}
        response = await client.get(url, params=params)
        
        if response.status_code >= 400:
            raise MarketDataError(f"DexScreener error: {response.status_code}")
        
        return response.json().get("pairs", [])
    
    # ===========================================
    # GeckoTerminal API
    # ===========================================
    
    async def get_geckoterminal_pools(self, network: str, token_address: str) -> List[Dict]:
        """Get pools for a token from GeckoTerminal."""
        client = await self._get_client()
        url = f"{self.settings.geckoterminal.base_url}/networks/{network}/tokens/{token_address}/pools"
        response = await client.get(url)
        
        if response.status_code >= 400:
            raise MarketDataError(f"GeckoTerminal error: {response.status_code}")
        
        return response.json().get("data", [])
    
    async def get_geckoterminal_ohlcv(
        self,
        network: str,
        pool_address: str,
        timeframe: str = "1h",
        limit: int = 500
    ) -> OHLCVData:
        """Get OHLCV from GeckoTerminal."""
        client = await self._get_client()
        url = f"{self.settings.geckoterminal.base_url}/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}"
        params = {"limit": limit}
        response = await client.get(url, params=params)
        
        if response.status_code >= 400:
            raise MarketDataError(f"GeckoTerminal error: {response.status_code}")
        
        data = response.json().get("data", {}).get("attributes", {}).get("ohlcv_list", [])
        
        timestamps = [int(item[0]) for item in data]
        opens = [item[1] for item in data]
        highs = [item[2] for item in data]
        lows = [item[3] for item in data]
        closes = [item[4] for item in data]
        volumes = [item[5] for item in data]
        
        return OHLCVData(
            symbol=pool_address,
            timeframe=timeframe,
            timestamps=timestamps,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            source=DataSource.GECKOTERMINAL
        )
    
    # ===========================================
    # CoinGecko Categories (free)
    # ===========================================
    
    async def get_categories(self) -> List[Dict]:
        """Get all coin categories with market data (free CoinGecko endpoint)."""
        cache_key = self._get_cache_key("coingecko", "/coins/categories", {})
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        data = await self._coingecko_request("/coins/categories")
        self._set_cache(cache_key, data)
        return data
    
    # ===========================================
    # Binance public market data (no API key)
    # ===========================================
    
    async def _binance_public_get(self, url: str, params: Optional[Dict] = None) -> Any:
        """GET a public Binance endpoint (spot or futures)."""
        client = await self._get_client()
        response = await client.get(url, params=params or {})
        if response.status_code == 429:
            raise RateLimitError("Binance rate limit exceeded")
        if response.status_code >= 400:
            raise MarketDataError(f"Binance error: {response.status_code} - {response.text[:200]}")
        return response.json()
    
    async def get_binance_depth(self, symbol: str, limit: int = 100) -> Dict:
        """Get order book depth from Binance spot."""
        symbol = symbol.upper().replace("/", "")
        if not symbol.endswith("USDT"):
            symbol += "USDT"
        data = await self._binance_public_get(
            "https://api.binance.com/api/v3/depth",
            {"symbol": symbol, "limit": max(5, min(limit, 5000))}
        )
        return {"symbol": symbol, "bids": data.get("bids", []), "asks": data.get("asks", [])}
    
    def _to_futures_symbol(self, symbol: str) -> str:
        symbol = symbol.upper().replace("/", "")
        if not symbol.endswith("USDT"):
            symbol += "USDT"
        return symbol
    
    async def get_funding_rate(self, symbol: str, limit: int = 30) -> Dict:
        """Get funding rate history from Binance futures."""
        symbol = self._to_futures_symbol(symbol)
        history = await self._binance_public_get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            {"symbol": symbol, "limit": max(1, min(limit, 1000))}
        )
        premium = await self._binance_public_get(
            "https://fapi.binance.com/fapi/v1/premiumIndex",
            {"symbol": symbol}
        )
        rates = [
            {"timestamp": int(h["fundingTime"]), "rate": float(h["fundingRate"])}
            for h in history
        ] if isinstance(history, list) else []
        return {
            "symbol": symbol,
            "current_funding_rate": float(premium.get("lastFundingRate", 0)),
            "mark_price": float(premium.get("markPrice", 0)),
            "index_price": float(premium.get("indexPrice", 0)),
            "next_funding_time": int(premium.get("nextFundingTime", 0)),
            "history": rates,
        }
    
    async def get_open_interest(self, symbol: str) -> Dict:
        """Get open interest from Binance futures."""
        symbol = self._to_futures_symbol(symbol)
        oi = await self._binance_public_get(
            "https://fapi.binance.com/fapi/v1/openInterest", {"symbol": symbol}
        )
        hist = await self._binance_public_get(
            "https://fapi.binance.com/futures/data/openInterestHist",
            {"symbol": symbol, "period": "1h", "limit": 48}
        )
        return {
            "symbol": symbol,
            "open_interest": float(oi.get("openInterest", 0)),
            "open_interest_value": float(oi.get("openInterest", 0)) * float(oi.get("openInterest", 0) and 1),
            "history": [
                {
                    "timestamp": int(h["timestamp"]),
                    "open_interest": float(h["sumOpenInterest"]),
                    "open_interest_value": float(h["sumOpenInterestValue"]),
                }
                for h in hist
            ] if isinstance(hist, list) else [],
        }
    
    async def get_long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 48) -> Dict:
        """Get global long/short account ratio from Binance futures."""
        symbol = self._to_futures_symbol(symbol)
        data = await self._binance_public_get(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
            {"symbol": symbol, "period": period, "limit": max(1, min(limit, 500))}
        )
        return {
            "symbol": symbol,
            "period": period,
            "history": [
                {
                    "timestamp": int(d["timestamp"]),
                    "long_account": float(d["longAccount"]),
                    "short_account": float(d["shortAccount"]),
                    "ratio": float(d["longShortRatio"]),
                }
                for d in data
            ] if isinstance(data, list) else [],
        }
    
    # ===========================================
    # GeckoTerminal new pools (free)
    # ===========================================
    
    async def get_new_pools(self, network: str = "eth", page: int = 1) -> List[Dict]:
        """Get newly created liquidity pools from GeckoTerminal."""
        client = await self._get_client()
        url = f"{self.settings.geckoterminal.base_url}/networks/{network}/new_pools"
        response = await client.get(url, params={"page": page})
        if response.status_code >= 400:
            raise MarketDataError(f"GeckoTerminal error: {response.status_code}")
        return response.json().get("data", [])
    
    # ===========================================
    # DexScreener latest profiles (free)
    # ===========================================
    
    async def get_dexscreener_latest_profiles(self) -> List[Dict]:
        """Get latest token profiles from DexScreener."""
        client = await self._get_client()
        response = await client.get("https://api.dexscreener.com/token-profiles/latest/v1")
        if response.status_code >= 400:
            raise MarketDataError(f"DexScreener error: {response.status_code}")
        return response.json() if isinstance(response.json(), list) else []
    
    # ===========================================
    # High-level unified methods
    # ===========================================
    
    async def search_coin(self, query: str) -> List[CoinInfo]:
        """Search for a coin across sources."""
        # Try CoinGecko search first
        results = await self.search_coins(query)
        coins = []
        
        for item in results[:10]:
            coin_detail = await self.get_coin_by_id(item["id"])
            if coin_detail:
                coins.append(coin_detail)
        
        return coins
    
    async def get_binance_price(
        self, symbol: str, vs_currency: str = "usd"
    ) -> Optional[float]:
        """Fast spot price straight from Binance (no CoinGecko quota used)."""
        quote = vs_currency.upper()
        if quote in ("USD", "USDT"):
            pair = f"{symbol.upper().replace('/', '')}USDT"
        elif quote in ("EUR", "GBP", "BRL", "TRY", "AUD"):
            pair = f"{symbol.upper().replace('/', '')}{quote}"
        else:
            return None
        try:
            data = await self._binance_public_get(
                "https://api.binance.com/api/v3/ticker/price", {"symbol": pair}
            )
            return float(data["price"])
        except Exception:
            return None

    async def get_coin_price(self, symbol: str, vs_currency: str = "usd") -> Optional[float]:
        """Get current price for a coin symbol (Binance first, CoinGecko fallback)."""
        price = await self.get_binance_price(symbol, vs_currency)
        if price is not None:
            return price
        # Try to find coin by symbol
        coins = await self.get_coins_markets(vs_currency=vs_currency, order="market_cap_desc", per_page=500)
        
        for coin in coins:
            if coin.symbol == symbol.upper():
                return coin.current_price
        
        # Try search
        search_results = await self.search_coin(symbol)
        if search_results:
            return search_results[0].current_price
        
        return None
    
    async def get_market_cap(self, symbol: str) -> Optional[float]:
        """Get market cap for a coin symbol."""
        coins = await self.get_coins_markets(order="market_cap_desc", per_page=500)
        
        for coin in coins:
            if coin.symbol == symbol.upper():
                return coin.market_cap
        
        return None
    
    async def get_trading_volume(self, symbol: str) -> Optional[float]:
        """Get 24h trading volume for a coin symbol."""
        coins = await self.get_coins_markets(order="market_cap_desc", per_page=500)
        
        for coin in coins:
            if coin.symbol == symbol.upper():
                return coin.total_volume
        
        return None
    
    async def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        days: int = 30,
        source: DataSource = DataSource.COINGECKO
    ) -> Optional[OHLCVData]:
        """Get historical OHLCV data for a symbol.

        Prefers Binance spot klines because they include real volume (required by
        volume profile / Wyckoff / volatility skills) and avoid CoinGecko's
        restricted ``days`` parameter. Falls back to CoinGecko OHLC if the pair
        is not listed on Binance.
        """
        # Estimate the number of candles needed from the requested day window.
        candles_per_day = {"1m": 1440, "3m": 480, "5m": 288, "15m": 96, "30m": 48,
                           "1h": 24, "2h": 12, "4h": 6, "6h": 4, "8h": 3,
                           "12h": 2, "1d": 1, "3d": 1 / 3, "1w": 1 / 7, "1M": 1 / 30}
        limit = int(days * candles_per_day.get(timeframe, 1))
        limit = max(30, min(limit, 1000))

        if source in (DataSource.COINGECKO, DataSource.BINANCE, DataSource.CCXT):
            try:
                klines = await self.get_binance_klines(symbol, timeframe, limit=limit)
                if klines and len(klines.closes) >= 10:
                    return klines
            except Exception:
                pass

        if source == DataSource.CCXT:
            # Try another exchange via ccxt before giving up
            try:
                return await self.get_ccxt_ohlcv("binance", f"{symbol.upper()}/USDT", timeframe, limit=limit)
            except Exception:
                pass
            return None

        # CoinGecko fallback (no volume guarantees, restricted days values)
        coins = await self.get_coins_markets(order="market_cap_desc", per_page=500)
        coin_id = None

        for coin in coins:
            if coin.symbol == symbol.upper():
                coin_id = coin.id
                break

        if not coin_id:
            search_results = await self.search_coin(symbol)
            if search_results:
                coin_id = search_results[0].id

        if not coin_id:
            return None

        return await self.get_coin_ohlcv(coin_id, days=days)
    
    async def get_exchange_data(self, symbol: str) -> Dict:
        """Get exchange data for a symbol (CEX + DEX)."""
        result = {
            "cex": {},
            "dex": {}
        }
        
        # CEX data from Binance
        try:
            ticker = await self.get_ccxt_ticker("binance", f"{symbol.upper()}/USDT")
            result["cex"]["binance"] = {
                "price": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "volume_24h": ticker.get("quoteVolume"),
                "change_24h": ticker.get("percentage")
            }
        except Exception:
            pass
        
        # DEX data from DexScreener
        try:
            # This would need the token address, which we don't have from symbol alone
            # In practice, you'd map symbols to addresses
            pass
        except Exception:
            pass
        
        return result
    
    async def scan_market(
        self,
        min_market_cap: float = 1_000_000,
        max_market_cap: float = 10_000_000_000,
        min_volume_24h: float = 50_000,
        min_price_change_24h: float = -50,
        max_price_change_24h: float = 1000,
        limit: int = 100
    ) -> List[CoinInfo]:
        """Scan market for coins meeting criteria."""
        coins = await self.get_coins_markets(per_page=min(limit * 3, 250))
        
        filtered = []
        for coin in coins:
            if coin.market_cap is None or coin.total_volume is None:
                continue
            
            if coin.market_cap < min_market_cap or coin.market_cap > max_market_cap:
                continue
            
            if coin.total_volume < min_volume_24h:
                continue
            
            pct_change = coin.price_change_percentage_24h or 0
            if pct_change < min_price_change_24h or pct_change > max_price_change_24h:
                continue
            
            filtered.append(coin)
            
            if len(filtered) >= limit:
                break
        
        return filtered


# Global provider instance
_market_data_provider: Optional[MarketDataProvider] = None


async def get_market_data_provider() -> MarketDataProvider:
    """Get the global market data provider instance."""
    global _market_data_provider
    if _market_data_provider is None:
        _market_data_provider = MarketDataProvider()
    return _market_data_provider


async def close_market_data_provider() -> None:
    """Close the global market data provider."""
    global _market_data_provider
    if _market_data_provider:
        await _market_data_provider.close()
        _market_data_provider = None