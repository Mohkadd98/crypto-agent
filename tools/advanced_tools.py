"""
Advanced analysis tools for the Crypto Intelligence Agent.

Covers:
- Derivatives (funding, open interest, long/short ratio)  [Binance public]
- Market breadth / advance-decline
- Correlation matrix & beta
- Sector rotation                               [CoinGecko categories]
- Order book depth & imbalance                  [Binance public]
- Fibonacci retracement/extension
- Volume profile (VPVR, POC, value area)
- Volatility analytics
- Momentum multi-timeframe scanner
- Mean reversion / z-score
- Ichimoku cloud
- Wyckoff phase heuristic
- New DEX pair scanner                          [GeckoTerminal / DexScreener]
- Gas tracker                                  [RPC]
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

import numpy as np

from providers.market_data import get_market_data_provider, MarketDataProvider, DataSource
from providers.blockchain import get_blockchain_provider, Chain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any, source: str, metadata: Optional[Dict] = None) -> Dict:
    return {
        "success": True,
        "data": data,
        "source": source,
        "timestamp": datetime.utcnow().isoformat(),
        "error": None,
        "metadata": metadata or {},
    }


def _fail(error: str, source: str) -> Dict:
    return {
        "success": False,
        "data": None,
        "source": source,
        "timestamp": datetime.utcnow().isoformat(),
        "error": str(error),
        "metadata": {},
    }


def _arr(ohlcv: Dict) -> Dict[str, np.ndarray]:
    return {
        "high": np.asarray(ohlcv["highs"], dtype=float),
        "low": np.asarray(ohlcv["lows"], dtype=float),
        "close": np.asarray(ohlcv["closes"], dtype=float),
        "open": np.asarray(ohlcv["opens"], dtype=float),
        "volume": np.asarray(ohlcv["volumes"], dtype=float),
    }


def _f(x: Any) -> float:
    return float(x) if x is not None and not (isinstance(x, float) and np.isnan(x)) else 0.0


# ---------------------------------------------------------------------------
# Derivatives
# ---------------------------------------------------------------------------

class AdvancedTools:
    """Advanced market & quantitative tools."""

    def __init__(self, provider: Optional[MarketDataProvider] = None):
        self.provider = provider

    async def _provider(self) -> MarketDataProvider:
        return self.provider or await get_market_data_provider()

    # ---- Derivatives -----------------------------------------------------

    async def get_derivatives_analysis(self, symbol: str) -> Dict:
        try:
            p = await self._provider()
            funding, oi, ls = await _gather_derivatives(p, symbol)

            signals = []
            score = 0.0  # -1 bearish crowded longs, +1 bullish crowded shorts

            fr = funding.get("current_funding_rate", 0.0)
            if fr > 0.0005:
                score -= 0.5
                signals.append(f"Funding strongly positive ({fr*100:.3f}%) — longs crowded, correction risk")
            elif fr > 0.0001:
                score -= 0.2
                signals.append(f"Funding mildly positive ({fr*100:.3f}%) — bullish bias")
            elif fr < -0.0005:
                score += 0.5
                signals.append(f"Funding strongly negative ({fr*100:.3f}%) — shorts crowded, squeeze potential")
            elif fr < -0.0001:
                score += 0.2
                signals.append(f"Funding mildly negative ({fr*100:.3f}%) — bearish bias")

            ratio_series = ls.get("history", [])
            if ratio_series:
                last_ratio = ratio_series[-1]["ratio"]
                if last_ratio > 2.0:
                    score -= 0.4
                    signals.append(f"Long/short ratio {last_ratio:.2f} — retail heavily long")
                elif last_ratio < 0.6:
                    score += 0.4
                    signals.append(f"Long/short ratio {last_ratio:.2f} — retail heavily short")

            oi_hist = oi.get("history", [])
            oi_change_pct = 0.0
            if len(oi_hist) >= 2:
                first, last = oi_hist[0]["open_interest_value"], oi_hist[-1]["open_interest_value"]
                if first > 0:
                    oi_change_pct = (last - first) / first * 100
                    signals.append(f"Open interest changed {oi_change_pct:+.1f}% over {len(oi_hist)}h")

            stance = "neutral"
            if score >= 0.3:
                stance = "contrarian_bullish"
            elif score <= -0.3:
                stance = "contrarian_bearish"

            return _ok(
                {
                    "symbol": funding.get("symbol", symbol.upper()),
                    "funding": {
                        "current_rate_pct": fr * 100,
                        "annualized_pct": fr * 3 * 365 * 100,
                        "next_funding_time": funding.get("next_funding_time"),
                        "mark_price": funding.get("mark_price"),
                        "index_price": funding.get("index_price"),
                        "history": funding.get("history", [])[-24:],
                    },
                    "open_interest": {
                        "current": oi.get("open_interest", 0),
                        "change_pct_period": oi_change_pct,
                        "history": oi_hist[-24:],
                    },
                    "long_short": {
                        "latest_ratio": ratio_series[-1]["ratio"] if ratio_series else None,
                        "history": ratio_series[-24:],
                    },
                    "sentiment_score": round(score, 2),
                    "stance": stance,
                    "signals": signals,
                },
                source="binance_futures",
                metadata={"symbol": symbol.upper()},
            )
        except Exception as e:
            return _fail(e, "binance_futures")

    # ---- Market breadth --------------------------------------------------

    async def get_market_breadth(self, top_n: int = 150) -> Dict:
        try:
            p = await self._provider()
            coins = await p.get_coins_markets(
                vs_currency="usd", order="market_cap_desc",
                per_page=min(top_n, 250), page=1,
                price_change_percentage="24h,7d,30d",
            )
            if not coins:
                return _fail("No market data", "coingecko")

            def collect(attr: str) -> List[float]:
                vals = []
                for c in coins:
                    v = getattr(c, attr, None)
                    if v is not None:
                        vals.append(float(v))
                return vals

            d1, d7, d30 = collect("price_change_percentage_24h"), collect("price_change_percentage_7d"), collect("price_change_percentage_30d")

            def stat(vals: List[float]) -> Dict:
                if not vals:
                    return {"positive": 0, "negative": 0, "pct_positive": 0.0, "median": 0.0, "mean": 0.0}
                pos = sum(1 for v in vals if v > 0)
                return {
                    "positive": pos,
                    "negative": len(vals) - pos,
                    "pct_positive": pos / len(vals) * 100,
                    "median": float(np.median(vals)),
                    "mean": float(np.mean(vals)),
                }

            s1, s7, s30 = stat(d1), stat(d7), stat(d30)

            # Composite breadth score (0-100)
            breadth_score = (
                s1["pct_positive"] * 0.2
                + s7["pct_positive"] * 0.35
                + s30["pct_positive"] * 0.35
                + (10 if s7["median"] > 0 else 0)
                + (10 if s30["median"] > 0 else 0)
            )
            breadth_score = max(0.0, min(100.0, breadth_score))

            if breadth_score >= 70:
                regime, note = "strong_bull", "Broad participation — healthy uptrend"
            elif breadth_score >= 55:
                regime, note = "bull", "More winners than losers"
            elif breadth_score >= 45:
                regime, note = "mixed", "No clear direction, selective market"
            elif breadth_score >= 30:
                regime, note = "bear", "Weakness broad, few leaders"
            else:
                regime, note = "strong_bear", "Broad decline — risk-off"

            top = sorted(coins, key=lambda c: c.price_change_percentage_24h or -999, reverse=True)[:5]
            bottom = sorted(coins, key=lambda c: c.price_change_percentage_24h or 999)[:5]

            return _ok(
                {
                    "universe_size": len(coins),
                    "advance_decline": {"advancing": s1["positive"], "declining": s1["negative"], "ratio": (s1["positive"] / max(s1["negative"], 1))},
                    "pct_above_24h": s1["pct_positive"],
                    "pct_above_7d": s7["pct_positive"],
                    "pct_above_30d": s30["pct_positive"],
                    "median_change": {"24h": s1["median"], "7d": s7["median"], "30d": s30["median"]},
                    "mean_change": {"24h": s1["mean"], "7d": s7["mean"], "30d": s30["mean"]},
                    "breadth_score": round(breadth_score, 1),
                    "regime": regime,
                    "interpretation": note,
                    "leaders": [{"symbol": c.symbol, "change_24h": c.price_change_percentage_24h} for c in top],
                    "laggards": [{"symbol": c.symbol, "change_24h": c.price_change_percentage_24h} for c in bottom],
                },
                source="coingecko",
                metadata={"top_n": top_n},
            )
        except Exception as e:
            return _fail(e, "coingecko")

    # ---- Correlation -----------------------------------------------------

    async def calculate_correlation_matrix(self, symbols: List[str], days: int = 90) -> Dict:
        try:
            p = await self._provider()
            symbols = [s.upper() for s in symbols]
            if len(symbols) < 2:
                return _fail("Need at least 2 symbols", "coingecko")

            series: Dict[str, np.ndarray] = {}
            for sym in symbols:
                ohlcv = await p.get_historical_ohlcv(sym, "1d", days)
                if ohlcv and len(ohlcv.closes) >= 10:
                    series[sym] = np.asarray(ohlcv.closes, dtype=float)

            if len(series) < 2:
                return _fail("Insufficient price data for correlation", "coingecko")

            min_len = min(len(v) for v in series.values())
            names = list(series.keys())
            closes = np.vstack([series[n][-min_len:] for n in names])
            returns = np.diff(closes, axis=1) / closes[:, :-1]
            corr = np.corrcoef(returns)

            matrix = {
                names[i]: {names[j]: round(float(corr[i][j]), 3) for j in range(len(names))}
                for i in range(len(names))
            }

            # Beta vs BTC (fetch BTC if missing)
            btc_returns = None
            if "BTC" in names:
                btc_returns = returns[names.index("BTC")]
            else:
                btc_ohlcv = await p.get_historical_ohlcv("BTC", "1d", days)
                if btc_ohlcv and len(btc_ohlcv.closes) >= 10:
                    b = np.asarray(btc_ohlcv.closes, dtype=float)[-min_len:]
                    btc_returns = np.diff(b) / b[:-1]

            betas = {}
            if btc_returns is not None and len(btc_returns) == returns.shape[1] and np.var(btc_returns) > 0:
                for i, n in enumerate(names):
                    cov = np.cov(returns[i], btc_returns)[0][1]
                    betas[n] = round(float(cov / np.var(btc_returns)), 3)

            off_diag = [corr[i][j] for i in range(len(names)) for j in range(len(names)) if i != j]
            avg_corr = float(np.mean(off_diag)) if off_diag else 0.0
            diversification = "poor" if avg_corr > 0.8 else ("moderate" if avg_corr > 0.6 else "good")

            pairs = []
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    pairs.append({"pair": f"{names[i]}/{names[j]}", "correlation": round(float(corr[i][j]), 3)})
            pairs.sort(key=lambda x: x["correlation"], reverse=True)

            return _ok(
                {
                    "symbols": names,
                    "days": days,
                    "matrix": matrix,
                    "average_correlation": round(avg_corr, 3),
                    "diversification": diversification,
                    "most_correlated": pairs[:3],
                    "least_correlated": pairs[-3:] if len(pairs) >= 3 else pairs,
                    "beta_to_btc": betas,
                },
                source="coingecko",
                metadata={"symbols": names},
            )
        except Exception as e:
            return _fail(e, "coingecko")

    # ---- Sector rotation ------------------------------------------------

    async def get_sector_performance(self, top_n: int = 12) -> Dict:
        try:
            p = await self._provider()
            cats = await p.get_categories()
            if not cats:
                return _fail("No category data", "coingecko")

            rows = []
            for c in cats:
                mcap = c.get("market_cap") or 0
                if mcap < 50_000_000:
                    continue
                rows.append({
                    "sector": c.get("name", "Unknown"),
                    "market_cap": mcap,
                    "market_cap_change_24h": c.get("market_cap_change_24h") or 0,
                    "volume_24h": c.get("volume_24h") or 0,
                    "top_coins": c.get("top_3_coins_id", [])[:3] if isinstance(c.get("top_3_coins_id"), list) else [],
                })

            rows.sort(key=lambda r: r["market_cap_change_24h"], reverse=True)
            leaders = rows[:top_n]
            laggards = rows[-5:] if len(rows) >= 5 else rows

            # Rotation signal: cyclical / high-beta leaders
            hot_sectors = {"memes", "artificial-intelligence", "ai", "gaming", "decentralized-finance-defi", "layer-2", "solana-ecosystem"}
            leader_names = {r["sector"].lower().replace(" ", "-") for r in leaders[:5]}
            risk_on = len(leader_names & hot_sectors) >= 2

            return _ok(
                {
                    "market_regime": "risk_on" if risk_on else "mixed",
                    "rotation_signal": (
                        "Capital rotating into high-beta / narrative sectors — risk-on"
                        if risk_on else
                        "Leadership not in cyclical sectors — selective or defensive regime"
                    ),
                    "leaders": leaders,
                    "laggards": laggards,
                },
                source="coingecko",
                metadata={"top_n": top_n, "sectors_analyzed": len(rows)},
            )
        except Exception as e:
            return _fail(e, "coingecko")

    # ---- Order book ------------------------------------------------------

    async def analyze_order_book(self, symbol: str, limit: int = 100) -> Dict:
        try:
            p = await self._provider()
            book = await p.get_binance_depth(symbol, limit)
            bids = [(float(px), float(qty)) for px, qty in book["bids"]]
            asks = [(float(px), float(qty)) for px, qty in book["asks"]]
            if not bids or not asks:
                return _fail("Empty order book", "binance")

            best_bid, best_ask = bids[0][0], asks[0][0]
            mid = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_pct = spread / mid * 100

            bid_vol = sum(q for _, q in bids)
            ask_vol = sum(q for _, q in asks)
            total = bid_vol + ask_vol
            imbalance = (bid_vol - ask_vol) / total * 100 if total else 0

            bid_notional = sum(px * q for px, q in bids)
            ask_notional = sum(px * q for px, q in asks)

            def walls(levels, side):
                if not levels:
                    return []
                qtys = [q for _, q in levels]
                mean = float(np.mean(qtys)) or 1.0
                found = [
                    {"price": px, "quantity": q, "multiple": round(q / mean, 1)}
                    for px, q in levels if q > mean * 4
                ]
                found.sort(key=lambda x: x["quantity"], reverse=True)
                return [{"side": side, **w} for w in found[:5]]

            support_walls = walls(bids[:40], "bid")
            resistance_walls = walls(asks[:40], "ask")

            if imbalance > 15:
                pressure, note = "buy", "Bid-heavy book — buyers absorbing supply"
            elif imbalance < -15:
                pressure, note = "sell", "Ask-heavy book — sellers dominating"
            else:
                pressure, note = "balanced", "Order book roughly balanced"

            return _ok(
                {
                    "symbol": book["symbol"],
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "mid_price": mid,
                    "spread": spread,
                    "spread_pct": spread_pct,
                    "bid_volume": bid_vol,
                    "ask_volume": ask_vol,
                    "bid_notional_usd": bid_notional,
                    "ask_notional_usd": ask_notional,
                    "imbalance_pct": imbalance,
                    "pressure": pressure,
                    "interpretation": note,
                    "bid_walls": support_walls,
                    "ask_walls": resistance_walls,
                    "liquidity_quality": "tight" if spread_pct < 0.05 else ("normal" if spread_pct < 0.2 else "wide"),
                },
                source="binance",
                metadata={"levels": limit},
            )
        except Exception as e:
            return _fail(e, "binance")

    # ---- Fibonacci -------------------------------------------------------

    async def calculate_fibonacci(self, ohlcv: Dict, lookback: int = 120) -> Dict:
        try:
            a = _arr(ohlcv)
            high, low, close = a["high"][-lookback:], a["low"][-lookback:], a["close"]
            if len(close) < 10:
                return _fail("Insufficient OHLCV data", "calculated")

            hi_idx = int(np.argmax(high))
            lo_idx = int(np.argmin(low))
            swing_high, swing_low = float(high[hi_idx]), float(low[lo_idx])
            uptrend = lo_idx < hi_idx  # low came first => up move
            price = float(close[-1])
            rng = swing_high - swing_low
            if rng <= 0:
                return _fail("Invalid swing range", "calculated")

            retr = {}
            for lvl in (0.236, 0.382, 0.5, 0.618, 0.786):
                retr[str(lvl)] = swing_high - rng * lvl if uptrend else swing_low + rng * lvl

            ext = {}
            for lvl in (1.272, 1.618, 2.618):
                ext[str(lvl)] = swing_high + rng * (lvl - 1) if uptrend else swing_low - rng * (lvl - 1)

            # Nearest fib level
            all_levels = {**{f"retr_{k}": v for k, v in retr.items()}, **{f"ext_{k}": v for k, v in ext.items()}}
            nearest = min(all_levels.items(), key=lambda kv: abs(kv[1] - price))

            # Position within range
            pos = (price - swing_low) / rng * 100

            return _ok(
                {
                    "trend": "up" if uptrend else "down",
                    "swing_high": swing_high,
                    "swing_low": swing_low,
                    "current_price": price,
                    "range_position_pct": round(pos, 2),
                    "retracement_levels": {k: round(v, 8) for k, v in retr.items()},
                    "extension_levels": {k: round(v, 8) for k, v in ext.items()},
                    "nearest_level": {"name": nearest[0], "price": round(nearest[1], 8), "distance_pct": round(abs(nearest[1] - price) / price * 100, 2)},
                    "golden_zone": bool(retr["0.382"] <= price <= retr["0.618"]) if uptrend else bool(retr["0.618"] <= price <= retr["0.382"]),
                },
                source="calculated",
                metadata={"lookback": lookback},
            )
        except Exception as e:
            return _fail(e, "calculated")

    # ---- Volume profile --------------------------------------------------

    async def calculate_volume_profile(self, ohlcv: Dict, bins: int = 24) -> Dict:
        try:
            a = _arr(ohlcv)
            high, low, close, vol = a["high"], a["low"], a["close"], a["volume"]
            if len(close) < 10 or vol.sum() <= 0:
                return _fail("Insufficient volume data", "calculated")

            typical = (high + low + close) / 3
            lo, hi = float(low.min()), float(high.max())
            if hi <= lo:
                return _fail("Zero price range", "calculated")

            hist, edges = np.histogram(typical, bins=bins, range=(lo, hi), weights=vol)
            centers = (edges[:-1] + edges[1:]) / 2
            total_vol = hist.sum()
            poc_idx = int(np.argmax(hist))
            poc = float(centers[poc_idx])

            # Value area = 70% of volume around POC
            order = np.argsort(hist)[::-1]
            cum, selected = 0.0, []
            for idx in order:
                selected.append(idx)
                cum += hist[idx]
                if cum >= total_vol * 0.70:
                    break
            va_prices = centers[selected]
            vah, val = float(max(va_prices)), float(min(va_prices))
            price = float(close[-1])

            if price > vah:
                location = "above_value_area"
            elif price < val:
                location = "below_value_area"
            else:
                location = "inside_value_area"

            # High volume nodes (top 3)
            hvns = [{"price": round(float(centers[i]), 8), "volume": float(hist[i]), "share_pct": round(float(hist[i] / total_vol * 100), 2)} for i in order[:3]]

            return _ok(
                {
                    "poc": round(poc, 8),
                    "value_area_high": round(vah, 8),
                    "value_area_low": round(val, 8),
                    "current_price": price,
                    "price_location": location,
                    "high_volume_nodes": hvns,
                    "histogram": [
                        {"price": round(float(centers[i]), 8), "volume": float(hist[i])}
                        for i in range(len(centers))
                    ],
                    "bias": "bullish" if price > poc else "bearish",
                },
                source="calculated",
                metadata={"bins": bins},
            )
        except Exception as e:
            return _fail(e, "calculated")

    # ---- Volatility ------------------------------------------------------

    async def analyze_volatility(self, ohlcv: Dict) -> Dict:
        try:
            a = _arr(ohlcv)
            close, high, low = a["close"], a["high"], a["low"]
            if len(close) < 20:
                return _fail("Insufficient data", "calculated")

            rets = np.diff(close) / close[:-1]

            def rv(window: int) -> float:
                r = rets[-window:] if len(rets) >= window else rets
                return float(np.std(r) * np.sqrt(365) * 100) if len(r) > 1 else 0.0

            vol_7, vol_30, vol_all = rv(7), rv(30), rv(len(rets))

            # ATR(14)
            trs = []
            for i in range(1, len(close)):
                trs.append(max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1])))
            atr = float(np.mean(trs[-14:])) if trs else 0.0
            atr_pct = atr / close[-1] * 100 if close[-1] else 0.0

            # Max drawdown
            peak = np.maximum.accumulate(close)
            dd = (close - peak) / peak
            max_dd = float(dd.min() * 100)

            if vol_30 > 150:
                regime = "extreme"
            elif vol_30 > 90:
                regime = "high"
            elif vol_30 > 50:
                regime = "normal"
            else:
                regime = "low"

            expansion = vol_7 > vol_30 * 1.25
            compression = vol_7 < vol_30 * 0.75

            return _ok(
                {
                    "realized_vol_7d_pct": round(vol_7, 2),
                    "realized_vol_30d_pct": round(vol_30, 2),
                    "realized_vol_full_pct": round(vol_all, 2),
                    "atr": round(atr, 8),
                    "atr_pct": round(atr_pct, 2),
                    "max_drawdown_pct": round(max_dd, 2),
                    "regime": regime,
                    "volatility_state": "expanding" if expansion else ("contracting" if compression else "stable"),
                    "note": (
                        "Volatility expanding — size down, widen stops"
                        if expansion else
                        "Volatility compressing — breakout setup forming"
                        if compression else "Volatility stable"
                    ),
                },
                source="calculated",
            )
        except Exception as e:
            return _fail(e, "calculated")

    # ---- Momentum scanner ------------------------------------------------

    async def scan_momentum(self, limit: int = 20, min_volume_24h: float = 1_000_000) -> Dict:
        try:
            p = await self._provider()
            coins = await p.get_coins_markets(
                order="market_cap_desc", per_page=250, page=1,
                price_change_percentage="24h,7d,30d",
            )
            scored = []
            for c in coins:
                if not c.total_volume or c.total_volume < min_volume_24h:
                    continue
                d1 = c.price_change_percentage_24h or 0
                d7 = c.price_change_percentage_7d or 0
                d30 = c.price_change_percentage_30d or 0
                # Weighted momentum, recent first
                score = d1 * 0.5 + (d7 / 7) * 0.3 + (d30 / 30) * 0.2
                acceleration = d1 - (d7 / 7)
                scored.append({
                    "symbol": c.symbol,
                    "name": c.name,
                    "price": c.current_price,
                    "market_cap": c.market_cap,
                    "volume_24h": c.total_volume,
                    "change_24h": d1,
                    "change_7d": d7,
                    "change_30d": d30,
                    "momentum_score": round(score, 4),
                    "acceleration": round(acceleration, 2),
                })
            scored.sort(key=lambda x: x["momentum_score"], reverse=True)
            top = scored[:limit]
            return _ok(
                {
                    "count": len(top),
                    "candidates": top,
                    "strongest": top[0] if top else None,
                    "accelerating": [s for s in top if s["acceleration"] > 0][:10],
                },
                source="coingecko",
                metadata={"universe": len(coins)},
            )
        except Exception as e:
            return _fail(e, "coingecko")

    # ---- Mean reversion --------------------------------------------------

    async def calculate_mean_reversion(self, ohlcv: Dict) -> Dict:
        try:
            a = _arr(ohlcv)
            close = a["close"]
            if len(close) < 30:
                return _fail("Insufficient data (need 30+)", "calculated")

            sma20 = float(np.mean(close[-20:]))
            std20 = float(np.std(close[-20:]))
            sma50 = float(np.mean(close[-50:])) if len(close) >= 50 else float(np.mean(close))
            price = float(close[-1])
            z = (price - sma20) / std20 if std20 > 0 else 0.0

            # Bollinger %B
            upper, lower = sma20 + 2 * std20, sma20 - 2 * std20
            pct_b = (price - lower) / (upper - lower) if upper != lower else 0.5

            # RSI(14) manual (Wilder)
            deltas = np.diff(close[-15:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains) if len(gains) else 0
            avg_loss = np.mean(losses) if len(losses) else 0
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))

            if z <= -2:
                signal, strength = "strong_buy_reversion", "high"
            elif z <= -1:
                signal, strength = "buy_reversion", "medium"
            elif z >= 2:
                signal, strength = "strong_sell_reversion", "high"
            elif z >= 1:
                signal, strength = "sell_reversion", "medium"
            else:
                signal, strength = "neutral", "low"

            return _ok(
                {
                    "price": price,
                    "sma20": sma20,
                    "sma50": sma50,
                    "z_score": round(z, 3),
                    "bollinger": {
                        "upper": upper, "middle": sma20, "lower": lower,
                        "percent_b": round(pct_b, 3),
                    },
                    "rsi_14": round(float(rsi), 2),
                    "signal": signal,
                    "strength": strength,
                    "distance_from_sma20_pct": round((price - sma20) / sma20 * 100, 2),
                    "trend_context": "above_sma50" if price > sma50 else "below_sma50",
                },
                source="calculated",
            )
        except Exception as e:
            return _fail(e, "calculated")

    # ---- Ichimoku --------------------------------------------------------

    async def calculate_ichimoku(self, ohlcv: Dict) -> Dict:
        try:
            a = _arr(ohlcv)
            high, low, close = a["high"], a["low"], a["close"]
            if len(close) < 78:
                return _fail("Insufficient data (need 78+ candles)", "calculated")

            def midline(period: int, offset: int = 0) -> float:
                end = len(high) - offset
                start = max(0, end - period)
                return (float(np.max(high[start:end])) + float(np.min(low[start:end]))) / 2

            tenkan = midline(9)
            kijun = midline(26)
            senkou_a = (midline(9, 26) + midline(26, 26)) / 2
            senkou_b = midline(52, 26)
            chikou = float(close[-1])  # current close vs close 26 ago
            chikou_ref = float(close[-27]) if len(close) >= 27 else chikou
            price = float(close[-1])

            cloud_top, cloud_bottom = max(senkou_a, senkou_b), min(senkou_a, senkou_b)
            if price > cloud_top:
                position = "above_cloud"
            elif price < cloud_bottom:
                position = "below_cloud"
            else:
                position = "inside_cloud"

            signals = []
            if position == "above_cloud":
                signals.append("Price above cloud — bullish")
            elif position == "below_cloud":
                signals.append("Price below cloud — bearish")
            if tenkan > kijun:
                signals.append("Tenkan above Kijun — bullish momentum")
            else:
                signals.append("Tenkan below Kijun — bearish momentum")
            if chikou > chikou_ref:
                signals.append("Chikou span bullish")
            else:
                signals.append("Chikou span bearish")

            bull = sum(1 for s in signals if "bullish" in s)
            bear = sum(1 for s in signals if "bearish" in s)
            bias = "bullish" if bull > bear else ("bearish" if bear > bull else "neutral")

            return _ok(
                {
                    "tenkan_sen": round(tenkan, 8),
                    "kijun_sen": round(kijun, 8),
                    "senkou_span_a": round(senkou_a, 8),
                    "senkou_span_b": round(senkou_b, 8),
                    "chikou_span": round(chikou, 8),
                    "cloud_top": round(cloud_top, 8),
                    "cloud_bottom": round(cloud_bottom, 8),
                    "price_position": position,
                    "cloud_color": "bullish" if senkou_a > senkou_b else "bearish",
                    "bias": bias,
                    "signals": signals,
                },
                source="calculated",
            )
        except Exception as e:
            return _fail(e, "calculated")

    # ---- Wyckoff ---------------------------------------------------------

    async def analyze_wyckoff(self, ohlcv: Dict, window: int = 60) -> Dict:
        try:
            a = _arr(ohlcv)
            high, low, close, vol = a["high"], a["low"], a["close"], a["volume"]
            if len(close) < window + 10:
                return _fail(f"Insufficient data (need {window+10}+)", "calculated")

            h, l, c, v = high[-window:], low[-window:], close[-window:], vol[-window:]
            rng_high, rng_low = float(np.max(h)), float(np.min(l))
            rng_width = (rng_high - rng_low) / rng_low * 100 if rng_low else 0
            price = float(close[-1])

            # Prior trend (before window)
            prior = close[:-window]
            prior_trend = "down" if len(prior) > 5 and prior[-1] < prior[0] else "up"

            # Range tightness
            in_range = rng_width < 35

            # Spring: wick below range low then close back inside (last 15 bars)
            spring = False
            upthrust = False
            for i in range(max(0, len(c) - 15), len(c)):
                if l[i] < rng_low * 1.002 and c[i] > rng_low and c[i] < rng_high:
                    spring = True
                if h[i] > rng_high * 0.998 and c[i] < rng_high and c[i] > rng_low:
                    upthrust = True

            # Volume behavior
            vol_first = float(np.mean(v[: window // 2]))
            vol_second = float(np.mean(v[window // 2:]))
            vol_trend = "increasing" if vol_second > vol_first * 1.1 else ("decreasing" if vol_second < vol_first * 0.9 else "flat")

            # Sign of strength / weakness: strong move out of range on volume
            sos = price > rng_high * 0.995 and vol_second > vol_first
            sow = price < rng_low * 1.005 and vol_second > vol_first

            if in_range and prior_trend == "down" and spring:
                phase, structure = "C", "accumulation"
            elif in_range and prior_trend == "down":
                phase, structure = "B", "accumulation"
            elif sos and prior_trend == "down":
                phase, structure = "D", "accumulation"
            elif in_range and prior_trend == "up" and upthrust:
                phase, structure = "C", "distribution"
            elif in_range and prior_trend == "up":
                phase, structure = "B", "distribution"
            elif sow and prior_trend == "up":
                phase, structure = "D", "distribution"
            else:
                phase, structure = "unknown", "neutral"

            confidence = 0.0
            confidence += 0.25 if in_range else 0
            confidence += 0.25 if (spring or upthrust) else 0
            confidence += 0.25 if (sos or sow) else 0
            confidence += 0.25 if vol_trend != "flat" else 0

            return _ok(
                {
                    "structure": structure,
                    "phase": phase,
                    "prior_trend": prior_trend,
                    "range_high": round(rng_high, 8),
                    "range_low": round(rng_low, 8),
                    "range_width_pct": round(rng_width, 2),
                    "in_trading_range": in_range,
                    "spring_detected": spring,
                    "upthrust_detected": upthrust,
                    "sign_of_strength": sos,
                    "sign_of_weakness": sow,
                    "volume_trend": vol_trend,
                    "confidence": round(confidence, 2),
                    "current_price": price,
                },
                source="calculated",
                metadata={"window": window},
            )
        except Exception as e:
            return _fail(e, "calculated")

    # ---- New DEX pairs ---------------------------------------------------

    async def scan_new_pairs(self, network: str = "eth", limit: int = 20, min_liquidity_usd: float = 10_000) -> Dict:
        try:
            p = await self._provider()
            pools = await p.get_new_pools(network, page=1)
            rows = []
            for pool in pools:
                attrs = pool.get("attributes", {})
                reserve = attrs.get("reserve_in_usd")
                reserve = float(reserve) if reserve else 0.0
                if reserve < min_liquidity_usd:
                    continue
                vol = (attrs.get("volume_usd") or {}).get("h24") if isinstance(attrs.get("volume_usd"), dict) else None
                chg = (attrs.get("price_change_percentage") or {}).get("h24") if isinstance(attrs.get("price_change_percentage"), dict) else None
                rows.append({
                    "name": attrs.get("name"),
                    "pool_address": attrs.get("address"),
                    "base_token_price_usd": attrs.get("base_token_price_usd"),
                    "liquidity_usd": reserve,
                    "volume_24h_usd": float(vol) if vol else 0.0,
                    "change_24h_pct": float(chg) if chg else 0.0,
                    "created_at": attrs.get("pool_created_at"),
                    "network": network,
                })
                if len(rows) >= limit:
                    break
            rows.sort(key=lambda r: r["liquidity_usd"], reverse=True)
            return _ok(
                {"network": network, "count": len(rows), "pairs": rows},
                source="geckoterminal",
                metadata={"min_liquidity_usd": min_liquidity_usd},
            )
        except Exception as e:
            return _fail(e, "geckoterminal")

    # ---- Gas tracker -----------------------------------------------------

    async def get_gas_prices(self, chains: Optional[List[str]] = None) -> Dict:
        try:
            bp = await get_blockchain_provider()
            chains = chains or ["ethereum", "bsc", "polygon", "arbitrum", "base", "avalanche"]
            out = {}
            for ch in chains:
                try:
                    info = await bp.get_gas_price(Chain(ch))
                    out[ch] = info
                except Exception as e:
                    out[ch] = {"chain": ch, "error": str(e)}
            valid = {k: v for k, v in out.items() if "gas_price_gwei" in v}
            cheapest = min(valid.items(), key=lambda kv: kv[1]["gas_price_gwei"])[0] if valid else None
            return _ok(
                {"chains": out, "cheapest_chain": cheapest},
                source="rpc",
                metadata={"chains_checked": len(chains)},
            )
        except Exception as e:
            return _fail(e, "rpc")


# ---------------------------------------------------------------------------
# Derivatives helper (parallel calls)
# ---------------------------------------------------------------------------

async def _gather_derivatives(p: MarketDataProvider, symbol: str) -> tuple:
    import asyncio
    results = await asyncio.gather(
        p.get_funding_rate(symbol),
        p.get_open_interest(symbol),
        p.get_long_short_ratio(symbol),
        return_exceptions=True,
    )
    funding = results[0] if isinstance(results[0], dict) else {}
    oi = results[1] if isinstance(results[1], dict) else {}
    ls = results[2] if isinstance(results[2], dict) else {}
    return funding, oi, ls


# ---------------------------------------------------------------------------
# Module-level tool wrappers
# ---------------------------------------------------------------------------

_tools = AdvancedTools()


async def _resolve_ohlcv(
    symbol: Optional[str] = None,
    ohlcv: Optional[Dict] = None,
    days: int = 200,
    timeframe: str = "1d",
) -> Optional[Dict]:
    """Return an OHLCV payload, fetching it by symbol when needed."""
    if ohlcv and all(k in ohlcv for k in ("highs", "lows", "closes", "volumes")):
        return ohlcv
    if not symbol:
        return None
    provider = await get_market_data_provider()
    data = await provider.get_historical_ohlcv(symbol, timeframe, days)
    if not data or len(data.closes) < 10:
        return None
    return {
        "timestamps": data.timestamps,
        "opens": data.opens,
        "highs": data.highs,
        "lows": data.lows,
        "closes": data.closes,
        "volumes": data.volumes,
    }


async def get_derivatives_analysis(symbol: str) -> Dict:
    return await _tools.get_derivatives_analysis(symbol)


async def get_market_breadth(top_n: int = 150) -> Dict:
    return await _tools.get_market_breadth(top_n)


async def calculate_correlation_matrix(symbols: List[str], days: int = 90) -> Dict:
    return await _tools.calculate_correlation_matrix(symbols, days)


async def get_sector_performance(top_n: int = 12) -> Dict:
    return await _tools.get_sector_performance(top_n)


async def analyze_order_book(symbol: str, limit: int = 100) -> Dict:
    return await _tools.analyze_order_book(symbol, limit)


async def calculate_fibonacci(
    symbol: str = "",
    ohlcv: Optional[Dict] = None,
    lookback: int = 120,
    days: int = 200,
) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _fail(f"No OHLCV data for {symbol or 'input'}", "calculated")
    return await _tools.calculate_fibonacci(data, lookback)


async def calculate_volume_profile(
    symbol: str = "",
    ohlcv: Optional[Dict] = None,
    bins: int = 24,
    days: int = 200,
) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _fail(f"No OHLCV data for {symbol or 'input'}", "calculated")
    return await _tools.calculate_volume_profile(data, bins)


async def analyze_volatility(
    symbol: str = "",
    ohlcv: Optional[Dict] = None,
    days: int = 200,
) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _fail(f"No OHLCV data for {symbol or 'input'}", "calculated")
    return await _tools.analyze_volatility(data)


async def scan_momentum(limit: int = 20, min_volume_24h: float = 1_000_000) -> Dict:
    return await _tools.scan_momentum(limit, min_volume_24h)


async def calculate_mean_reversion(
    symbol: str = "",
    ohlcv: Optional[Dict] = None,
    days: int = 200,
) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _fail(f"No OHLCV data for {symbol or 'input'}", "calculated")
    return await _tools.calculate_mean_reversion(data)


async def calculate_ichimoku(
    symbol: str = "",
    ohlcv: Optional[Dict] = None,
    days: int = 200,
) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _fail(f"No OHLCV data for {symbol or 'input'}", "calculated")
    return await _tools.calculate_ichimoku(data)


async def analyze_wyckoff(
    symbol: str = "",
    ohlcv: Optional[Dict] = None,
    window: int = 60,
    days: int = 200,
) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _fail(f"No OHLCV data for {symbol or 'input'}", "calculated")
    return await _tools.analyze_wyckoff(data, window)


async def scan_new_pairs(network: str = "eth", limit: int = 20, min_liquidity_usd: float = 10_000) -> Dict:
    return await _tools.scan_new_pairs(network, limit, min_liquidity_usd)


async def get_gas_prices(chains: Optional[List[str]] = None) -> Dict:
    return await _tools.get_gas_prices(chains)


# ---------------------------------------------------------------------------
# OpenAI function definitions
# ---------------------------------------------------------------------------

ADVANCED_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_derivatives_analysis",
            "description": "Analyze futures derivatives: funding rate, open interest, long/short ratio, and crowding signals",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "Coin symbol (e.g. BTC, ETH, SOL)"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_breadth",
            "description": "Measure market breadth: % of top coins advancing, advance/decline ratio, regime (strong bull to strong bear)",
            "parameters": {
                "type": "object",
                "properties": {"top_n": {"type": "integer", "description": "Number of top coins to analyze", "default": 150}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_correlation_matrix",
            "description": "Compute price-return correlation matrix and beta to BTC across multiple coins",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {"type": "array", "items": {"type": "string"}, "description": "List of coin symbols"},
                    "days": {"type": "integer", "description": "Lookback window in days", "default": 90},
                },
                "required": ["symbols"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sector_performance",
            "description": "Get sector/category performance to detect capital rotation (AI, DeFi, L2, memes, etc.)",
            "parameters": {
                "type": "object",
                "properties": {"top_n": {"type": "integer", "default": 12}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_order_book",
            "description": "Analyze order book depth: spread, imbalance, bid/ask walls, liquidity quality",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol"},
                    "limit": {"type": "integer", "default": 100},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_fibonacci",
            "description": "Calculate Fibonacci retracement and extension levels for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "Optional pre-fetched OHLCV data"},
                    "lookback": {"type": "integer", "default": 120},
                    "days": {"type": "integer", "description": "History window in days if fetching", "default": 200},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_volume_profile",
            "description": "Calculate volume profile (POC, value area, high volume nodes) for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "Optional pre-fetched OHLCV data"},
                    "bins": {"type": "integer", "default": 24},
                    "days": {"type": "integer", "description": "History window in days if fetching", "default": 200},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_volatility",
            "description": "Analyze realized volatility, ATR%, max drawdown and volatility regime for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "Optional pre-fetched OHLCV data"},
                    "days": {"type": "integer", "description": "History window in days if fetching", "default": 200},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_momentum",
            "description": "Scan for coins with strongest multi-timeframe momentum and acceleration",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                    "min_volume_24h": {"type": "number", "default": 1000000},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_mean_reversion",
            "description": "Calculate mean-reversion metrics (z-score, Bollinger %B, RSI) for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "Optional pre-fetched OHLCV data"},
                    "days": {"type": "integer", "description": "History window in days if fetching", "default": 200},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_ichimoku",
            "description": "Calculate Ichimoku cloud (tenkan, kijun, senkou spans, bias) for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "Optional pre-fetched OHLCV data"},
                    "days": {"type": "integer", "description": "History window in days if fetching", "default": 200},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_wyckoff",
            "description": "Wyckoff phase analysis (accumulation/distribution, spring, upthrust) for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "Optional pre-fetched OHLCV data"},
                    "window": {"type": "integer", "default": 60},
                    "days": {"type": "integer", "description": "History window in days if fetching", "default": 200},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_new_pairs",
            "description": "Scan newly created DEX liquidity pools on a network",
            "parameters": {
                "type": "object",
                "properties": {
                    "network": {"type": "string", "description": "Network (eth, bsc, polygon, arbitrum, base, solana)", "default": "eth"},
                    "limit": {"type": "integer", "default": 20},
                    "min_liquidity_usd": {"type": "number", "default": 10000},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gas_prices",
            "description": "Get current gas prices across multiple chains",
            "parameters": {
                "type": "object",
                "properties": {
                    "chains": {"type": "array", "items": {"type": "string"}, "description": "Chains to check (optional)"},
                },
                "required": [],
            },
        },
    },
]
