"""
Market data tools for the Crypto Intelligence Agent.
Provides tools for fetching market data, prices, and historical data.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from providers.market_data import (
    get_market_data_provider, MarketDataProvider, 
    CoinInfo, OHLCVData, MarketOverview, DataSource
)


@dataclass
class ToolResult:
    """Standard tool result format."""
    success: bool
    data: Any
    source: str
    timestamp: datetime
    error: Optional[str] = None
    metadata: Dict = None
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


class MarketTools:
    """Market data tools for the agent."""
    
    def __init__(self, provider: Optional[MarketDataProvider] = None):
        self.provider = provider
    
    async def _get_provider(self) -> MarketDataProvider:
        if self.provider is None:
            return await get_market_data_provider()
        return self.provider
    
    async def get_market_overview(self) -> ToolResult:
        """Get global market overview."""
        try:
            provider = await self._get_provider()
            overview = await provider.get_market_overview()
            
            return ToolResult(
                success=True,
                data={
                    "total_market_cap": overview.total_market_cap,
                    "total_volume_24h": overview.total_volume_24h,
                    "btc_dominance": overview.btc_dominance,
                    "eth_dominance": overview.eth_dominance,
                    "market_cap_change_24h": overview.market_cap_change_24h,
                    "active_cryptocurrencies": overview.active_cryptocurrencies,
                    "markets": overview.markets
                },
                source="coingecko",
                timestamp=overview.fetched_at,
                metadata={"provider": "coingecko"}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="coingecko",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def search_coin(self, query: str) -> ToolResult:
        """Search for coins by name or symbol."""
        try:
            provider = await self._get_provider()
            coins = await provider.search_coin(query)
            
            return ToolResult(
                success=True,
                data=[{
                    "id": coin.id,
                    "symbol": coin.symbol,
                    "name": coin.name,
                    "current_price": coin.current_price,
                    "market_cap": coin.market_cap,
                    "market_cap_rank": coin.market_cap_rank,
                    "price_change_24h": coin.price_change_24h,
                    "price_change_percentage_24h": coin.price_change_percentage_24h
                } for coin in coins],
                source="coingecko",
                timestamp=datetime.utcnow(),
                metadata={"query": query, "count": len(coins)}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="coingecko",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def get_coin_price(self, symbol: str, vs_currency: str = "usd") -> ToolResult:
        """Get current price for a coin."""
        try:
            provider = await self._get_provider()
            price = await provider.get_coin_price(symbol, vs_currency)
            
            if price is None:
                return ToolResult(
                    success=False,
                    data=None,
                    source="coingecko",
                    timestamp=datetime.utcnow(),
                    error=f"Coin {symbol} not found"
                )
            
            return ToolResult(
                success=True,
                data={"symbol": symbol.upper(), "price": price, "currency": vs_currency},
                source="coingecko",
                timestamp=datetime.utcnow(),
                metadata={"vs_currency": vs_currency}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="coingecko",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def get_market_cap(self, symbol: str) -> ToolResult:
        """Get market cap for a coin."""
        try:
            provider = await self._get_provider()
            market_cap = await provider.get_market_cap(symbol)
            
            if market_cap is None:
                return ToolResult(
                    success=False,
                    data=None,
                    source="coingecko",
                    timestamp=datetime.utcnow(),
                    error=f"Coin {symbol} not found"
                )
            
            return ToolResult(
                success=True,
                data={"symbol": symbol.upper(), "market_cap": market_cap},
                source="coingecko",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="coingecko",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def get_trading_volume(self, symbol: str) -> ToolResult:
        """Get 24h trading volume for a coin."""
        try:
            provider = await self._get_provider()
            volume = await provider.get_trading_volume(symbol)
            
            if volume is None:
                return ToolResult(
                    success=False,
                    data=None,
                    source="coingecko",
                    timestamp=datetime.utcnow(),
                    error=f"Coin {symbol} not found"
                )
            
            return ToolResult(
                success=True,
                data={"symbol": symbol.upper(), "volume_24h": volume},
                source="coingecko",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="coingecko",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        days: int = 30,
        source: DataSource = DataSource.COINGECKO
    ) -> ToolResult:
        """Get historical OHLCV data."""
        try:
            provider = await self._get_provider()
            ohlcv = await provider.get_historical_ohlcv(symbol, timeframe, days, source)
            
            if ohlcv is None:
                return ToolResult(
                    success=False,
                    data=None,
                    source=source.value,
                    timestamp=datetime.utcnow(),
                    error=f"Could not fetch data for {symbol}"
                )
            
            return ToolResult(
                success=True,
                data={
                    "symbol": ohlcv.symbol,
                    "timeframe": ohlcv.timeframe,
                    "timestamps": ohlcv.timestamps,
                    "opens": ohlcv.opens,
                    "highs": ohlcv.highs,
                    "lows": ohlcv.lows,
                    "closes": ohlcv.closes,
                    "volumes": ohlcv.volumes,
                    "data_points": len(ohlcv.timestamps)
                },
                source=source.value,
                timestamp=ohlcv.fetched_at,
                metadata={"days": days, "timeframe": timeframe}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source=source.value,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def get_exchange_data(self, symbol: str) -> ToolResult:
        """Get exchange data (CEX + DEX) for a symbol."""
        try:
            provider = await self._get_provider()
            data = await provider.get_exchange_data(symbol)
            
            return ToolResult(
                success=True,
                data=data,
                source="multi",
                timestamp=datetime.utcnow(),
                metadata={"symbol": symbol.upper()}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="multi",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def scan_market(
        self,
        min_market_cap: float = 1_000_000,
        max_market_cap: float = 10_000_000_000,
        min_volume_24h: float = 50_000,
        min_price_change_24h: float = -50,
        max_price_change_24h: float = 1000,
        limit: int = 100
    ) -> ToolResult:
        """Scan market for coins meeting criteria."""
        try:
            provider = await self._get_provider()
            coins = await provider.scan_market(
                min_market_cap=min_market_cap,
                max_market_cap=max_market_cap,
                min_volume_24h=min_volume_24h,
                min_price_change_24h=min_price_change_24h,
                max_price_change_24h=max_price_change_24h,
                limit=limit
            )
            
            return ToolResult(
                success=True,
                data=[{
                    "id": coin.id,
                    "symbol": coin.symbol,
                    "name": coin.name,
                    "current_price": coin.current_price,
                    "market_cap": coin.market_cap,
                    "market_cap_rank": coin.market_cap_rank,
                    "total_volume": coin.total_volume,
                    "price_change_24h": coin.price_change_24h,
                    "price_change_percentage_24h": coin.price_change_percentage_24h,
                    "circulating_supply": coin.circulating_supply,
                    "total_supply": coin.total_supply,
                    "max_supply": coin.max_supply
                } for coin in coins],
                source="coingecko",
                timestamp=datetime.utcnow(),
                metadata={
                    "filters": {
                        "min_market_cap": min_market_cap,
                        "max_market_cap": max_market_cap,
                        "min_volume_24h": min_volume_24h,
                        "min_price_change_24h": min_price_change_24h,
                        "max_price_change_24h": max_price_change_24h
                    },
                    "count": len(coins)
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="coingecko",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def get_top_coins(self, limit: int = 100, vs_currency: str = "usd") -> ToolResult:
        """Get top coins by market cap."""
        try:
            provider = await self._get_provider()
            coins = await provider.get_coins_markets(
                vs_currency=vs_currency,
                order="market_cap_desc",
                per_page=limit,
                page=1
            )
            
            return ToolResult(
                success=True,
                data=[{
                    "id": coin.id,
                    "symbol": coin.symbol,
                    "name": coin.name,
                    "current_price": coin.current_price,
                    "market_cap": coin.market_cap,
                    "market_cap_rank": coin.market_cap_rank,
                    "total_volume": coin.total_volume,
                    "price_change_percentage_24h": coin.price_change_percentage_24h,
                    "price_change_percentage_7d": getattr(coin, 'price_change_percentage_7d', None),
                    "price_change_percentage_30d": getattr(coin, 'price_change_percentage_30d', None)
                } for coin in coins],
                source="coingecko",
                timestamp=datetime.utcnow(),
                metadata={"limit": limit, "vs_currency": vs_currency}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="coingecko",
                timestamp=datetime.utcnow(),
                error=str(e)
            )


# Tool function wrappers for easy registration
async def get_market_overview() -> Dict:
    tools = MarketTools()
    result = await tools.get_market_overview()
    return result.to_dict()


async def search_coin(query: str) -> Dict:
    tools = MarketTools()
    result = await tools.search_coin(query)
    return result.to_dict()


async def get_coin_price(symbol: str, vs_currency: str = "usd") -> Dict:
    tools = MarketTools()
    result = await tools.get_coin_price(symbol, vs_currency)
    return result.to_dict()


async def get_market_cap(symbol: str) -> Dict:
    tools = MarketTools()
    result = await tools.get_market_cap(symbol)
    return result.to_dict()


async def get_trading_volume(symbol: str) -> Dict:
    tools = MarketTools()
    result = await tools.get_trading_volume(symbol)
    return result.to_dict()


async def get_historical_ohlcv(symbol: str, timeframe: str = "1d", days: int = 30, source: str = "coingecko") -> Dict:
    tools = MarketTools()
    result = await tools.get_historical_ohlcv(symbol, timeframe, days, DataSource(source))
    return result.to_dict()


async def get_exchange_data(symbol: str) -> Dict:
    tools = MarketTools()
    result = await tools.get_exchange_data(symbol)
    return result.to_dict()


async def scan_market(
    min_market_cap: float = 1_000_000,
    max_market_cap: float = 10_000_000_000,
    min_volume_24h: float = 50_000,
    min_price_change_24h: float = -50,
    max_price_change_24h: float = 1000,
    limit: int = 100
) -> Dict:
    tools = MarketTools()
    result = await tools.scan_market(
        min_market_cap=min_market_cap,
        max_market_cap=max_market_cap,
        min_volume_24h=min_volume_24h,
        min_price_change_24h=min_price_change_24h,
        max_price_change_24h=max_price_change_24h,
        limit=limit
    )
    return result.to_dict()


async def get_top_coins(limit: int = 100, vs_currency: str = "usd") -> Dict:
    tools = MarketTools()
    result = await tools.get_top_coins(limit, vs_currency)
    return result.to_dict()


# Tool definitions for AI function calling
MARKET_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_market_overview",
            "description": "Get global cryptocurrency market overview including total market cap, volume, BTC/ETH dominance",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_coin",
            "description": "Search for cryptocurrencies by name or symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (name or symbol)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_coin_price",
            "description": "Get current price for a specific cryptocurrency",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g., BTC, ETH)"},
                    "vs_currency": {"type": "string", "description": "Quote currency", "default": "usd"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_cap",
            "description": "Get market capitalization for a cryptocurrency",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trading_volume",
            "description": "Get 24h trading volume for a cryptocurrency",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_historical_ohlcv",
            "description": "Get historical OHLCV (Open, High, Low, Close, Volume) data",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol"},
                    "timeframe": {"type": "string", "description": "Timeframe (1h, 4h, 1d, 1w)", "default": "1d"},
                    "days": {"type": "integer", "description": "Number of days of history", "default": 30},
                    "source": {"type": "string", "description": "Data source", "enum": ["coingecko", "binance", "dexscreener", "geckoterminal"], "default": "coingecko"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_data",
            "description": "Get exchange data (CEX and DEX) for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scan_market",
            "description": "Scan market for coins meeting specific criteria",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_market_cap": {"type": "number", "description": "Minimum market cap in USD", "default": 1000000},
                    "max_market_cap": {"type": "number", "description": "Maximum market cap in USD", "default": 10000000000},
                    "min_volume_24h": {"type": "number", "description": "Minimum 24h volume in USD", "default": 50000},
                    "min_price_change_24h": {"type": "number", "description": "Minimum 24h price change %", "default": -50},
                    "max_price_change_24h": {"type": "number", "description": "Maximum 24h price change %", "default": 1000},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 100}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_coins",
            "description": "Get top coins by market cap",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of coins", "default": 100},
                    "vs_currency": {"type": "string", "description": "Quote currency", "default": "usd"}
                },
                "required": []
            }
        }
    }
]