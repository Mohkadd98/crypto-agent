"""
Configuration management for the Crypto Intelligence Agent.
Loads settings from YAML files and environment variables.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


# Load environment variables
env_path = Path(__file__).parent.parent / "config" / "api_keys.env"
load_dotenv(env_path)

CONFIG_DIR = Path(__file__).parent.parent / "config"


class KiloAPISettings(BaseModel):
    base_url: str = "https://ai-gateway.kilo.ai/api/v1"
    api_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbnYiOiJwcm9kdWN0aW9uIiwia2lsb1VzZXJJZCI6IjhlYzlmZDk2LTNkN2QtNGJlYy05Yjk5LTE5YzUwZDIxZTlmMSIsImFwaVRva2VuUGVwcGVyIjpudWxsLCJ2ZXJzaW9uIjozLCJpYXQiOjE3OTUwODc5MTIsImV4cCI6MTk1Mjc2NzkxMn0.FxY2nHDY0MQJCvaVEZ-CCuhxwLBUUoRETWvpVrfclEE"
    default_model: str = "kilo-auto/free"
    fallback_model: str = "kilo-auto/free"
    max_tokens: int = 8192
    temperature: float = 0.7
    timeout: int = 60
    max_retries: int = 3
    stream_responses: bool = True


class GeminiAPISettings(BaseModel):
    """Google Gemini via the OpenAI-compatible endpoint (free tier available)."""
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    api_key: str = ""
    default_model: str = "gemini-3.8-flash"


class ModelSettings(BaseModel):
    model: str
    temperature: float
    max_tokens: int


class ModelsSettings(BaseModel):
    reasoning: ModelSettings
    research: ModelSettings
    lightweight: ModelSettings


class MarketDataProviderSettings(BaseModel):
    base_url: str
    api_key: str = ""
    api_secret: str = ""
    rate_limit: int = 60


class MarketDataSettings(BaseModel):
    primary: str = "coingecko"
    fallback: List[str] = ["binance", "dexscreener", "geckoterminal"]
    coingecko: MarketDataProviderSettings
    binance: MarketDataProviderSettings
    dexscreener: MarketDataProviderSettings
    geckoterminal: MarketDataProviderSettings


class BlockchainRPCSettings(BaseModel):
    rpc_url: str = ""
    fallback_rpcs: List[str] = []


class BlockchainSettings(BaseModel):
    ethereum: BlockchainRPCSettings
    bsc: BlockchainRPCSettings
    polygon: BlockchainRPCSettings
    arbitrum: BlockchainRPCSettings
    solana: BlockchainRPCSettings
    optimism: BlockchainRPCSettings = BlockchainRPCSettings()
    base: BlockchainRPCSettings = BlockchainRPCSettings()
    avalanche: BlockchainRPCSettings = BlockchainRPCSettings()


class ScannerSettings(BaseModel):
    min_market_cap: int = 1000000
    max_market_cap: int = 10000000000
    min_volume_24h: int = 50000
    min_liquidity: int = 100000
    top_n_coins: int = 500
    scan_interval_minutes: int = 15
    timeframes: List[str] = ["1h", "4h", "1d", "1w"]
    lookback_days: int = 365


class TechnicalSettings(BaseModel):
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ema_periods: List[int] = [9, 21, 50, 200]
    atr_period: int = 14
    obv_period: int = 20
    bb_period: int = 20
    bb_std: float = 2.0


class RiskSettings(BaseModel):
    max_drawdown_threshold: float = 0.5
    volatility_threshold: float = 0.8
    liquidity_risk_threshold: float = 0.3
    concentration_risk_threshold: float = 0.4


class SkillSettings(BaseModel):
    auto_load: bool = True
    skills_dir: str = "skills"
    enabled_by_default: List[str] = []


class DatabaseSettings(BaseModel):
    type: str = "sqlite"
    path: str = "data/agent.db"
    pool_size: int = 5
    echo: bool = False


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/agent.log"
    max_size_mb: int = 100
    backup_count: int = 5
    console: bool = True


class CostSettings(BaseModel):
    max_daily_usd: float = 10.0
    max_monthly_usd: float = 200.0
    track_usage: bool = True
    alert_threshold_pct: int = 80


class ReportsSettings(BaseModel):
    output_dir: str = "reports"
    format: str = "markdown"
    include_charts: bool = False
    auto_save: bool = True


class AppSettings(BaseModel):
    name: str = "CRYPTO INTELLIGENCE AGENT"
    version: str = "1.0.0"
    debug: bool = False
    kilo_api: KiloAPISettings
    gemini_api: GeminiAPISettings = GeminiAPISettings()
    models: ModelsSettings = ModelsSettings(reasoning=ModelSettings(model="kilo-auto/free", temperature=0.5, max_tokens=8192), research=ModelSettings(model="kilo-auto/free", temperature=0.3, max_tokens=16384), lightweight=ModelSettings(model="kilo-auto/free", temperature=0.1, max_tokens=2048))
    market_data: MarketDataSettings
    blockchain: BlockchainSettings
    scanner: ScannerSettings
    technical: TechnicalSettings
    risk: RiskSettings
    skills: SkillSettings
    database: DatabaseSettings
    logging: LoggingSettings
    cost: CostSettings
    reports: ReportsSettings


def load_yaml_config(filename: str) -> Dict[str, Any]:
    """Load a YAML configuration file."""
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


_PLACEHOLDER_HINTS = ("your_", "your-", "replace", "changeme", "example", "here")


def _is_placeholder(value: str) -> bool:
    """Detect template/placeholder values from api_keys.env."""
    if not value:
        return True
    lowered = value.strip().lower()
    return any(hint in lowered for hint in _PLACEHOLDER_HINTS)


def get_env(key: str, default: str = "") -> str:
    """Get environment variable, ignoring unfilled template placeholders."""
    value = os.getenv(key)
    if value is None or _is_placeholder(value):
        return "" if _is_placeholder(default) else default
    return value


@lru_cache(maxsize=1)
def load_settings() -> AppSettings:
    """Load all settings from YAML and environment variables."""
    # Load base config from settings.yaml
    base_config = load_yaml_config("settings.yaml")
    
    # Extract app settings from YAML app section
    app_config = base_config.pop("app", {})
    base_config["name"] = app_config.get("name", "CRYPTO INTELLIGENCE AGENT")
    base_config["version"] = app_config.get("version", "1.0.0")
    base_config["debug"] = app_config.get("debug", False)
    
    # Override with environment variables
    if "kilo_api" in base_config:
        base_config["kilo_api"]["api_key"] = get_env("KILO_API_KEY", base_config["kilo_api"].get("api_key", ""))
    
    if "gemini_api" in base_config:
        base_config["gemini_api"]["api_key"] = get_env("GEMINI_API_KEY", base_config["gemini_api"].get("api_key", ""))
        base_config["gemini_api"]["base_url"] = get_env("GEMINI_BASE_URL", base_config["gemini_api"].get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai/"))
        base_config["gemini_api"]["default_model"] = get_env("GEMINI_MODEL", base_config["gemini_api"].get("default_model", "gemini-3.8-flash"))
    
    if "market_data" in base_config:
        if "coingecko" in base_config["market_data"]:
            base_config["market_data"]["coingecko"]["api_key"] = get_env("COINGECKO_API_KEY", base_config["market_data"]["coingecko"].get("api_key", ""))
        if "binance" in base_config["market_data"]:
            base_config["market_data"]["binance"]["api_key"] = get_env("BINANCE_API_KEY", base_config["market_data"]["binance"].get("api_key", ""))
            base_config["market_data"]["binance"]["api_secret"] = get_env("BINANCE_API_SECRET", base_config["market_data"]["binance"].get("api_secret", ""))
    
    if "blockchain" in base_config:
        for chain in ["ethereum", "bsc", "polygon", "arbitrum", "solana"]:
            if chain in base_config["blockchain"]:
                env_key = f"{chain.upper()}_RPC_URL"
                base_config["blockchain"][chain]["rpc_url"] = get_env(env_key, base_config["blockchain"][chain].get("rpc_url", ""))
    
    return AppSettings(**base_config)


def get_settings() -> AppSettings:
    """Get the current settings instance."""
    return load_settings()


def reload_settings() -> AppSettings:
    """Force reload settings from disk."""
    load_settings.cache_clear()
    return load_settings()
