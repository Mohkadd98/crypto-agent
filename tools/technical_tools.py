"""
Technical analysis tools for the Crypto Intelligence Agent.
Calculates indicators, detects patterns, and analyzes market structure.
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import pandas_ta as ta


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


class TrendDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class MarketStructure(str, Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    RANGING = "ranging"


def _prepare_dataframe(ohlcv: Dict) -> pd.DataFrame:
    """Convert OHLCV data to pandas DataFrame."""
    closes = ohlcv['closes']
    timestamps = ohlcv.get('timestamps')
    if not timestamps:
        # Synthetic daily index when the caller only supplies price series.
        timestamps = [int((datetime.utcnow().timestamp() - (len(closes) - i) * 86400) * 1000)
                      for i in range(len(closes))]
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(timestamps, unit='ms'),
        'open': ohlcv['opens'],
        'high': ohlcv['highs'],
        'low': ohlcv['lows'],
        'close': closes,
        'volume': ohlcv['volumes']
    })
    df.set_index('timestamp', inplace=True)
    return df


def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI."""
    return ta.rsi(close, length=period)


def _calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD."""
    macd = ta.macd(close, fast=fast, slow=slow, signal=signal)
    return macd['MACD_12_26_9'], macd['MACDs_12_26_9'], macd['MACDh_12_26_9']


def _calculate_ema(close: pd.Series, period: int) -> pd.Series:
    """Calculate EMA."""
    return ta.ema(close, length=period)


def _calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume."""
    return ta.obv(close, volume)


def _calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    return ta.atr(high, low, close, length=period)


def _calculate_bollinger_bands(close: pd.Series, period: int = 20, std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands (tolerant of pandas_ta column naming changes)."""
    bb = ta.bbands(close, length=period, std=std)

    def _pick(prefix: str) -> pd.Series:
        matches = [c for c in bb.columns if c.startswith(prefix)]
        return bb[matches[0]] if matches else pd.Series(index=close.index, dtype=float)

    return _pick("BBU_"), _pick("BBM_"), _pick("BBL_")


def _detect_support_resistance(df: pd.DataFrame, window: int = 20, min_touches: int = 2) -> Dict:
    """Detect support and resistance levels."""
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    
    # Find local maxima and minima
    resistance_levels = []
    support_levels = []
    
    for i in range(window, len(df) - window):
        # Resistance (local high)
        if highs[i] == max(highs[i-window:i+window+1]):
            # Count touches
            touches = sum(1 for h in highs if abs(h - highs[i]) / highs[i] < 0.01)
            if touches >= min_touches:
                resistance_levels.append({
                    'price': float(highs[i]),
                    'touches': touches,
                    'strength': touches / window
                })
        
        # Support (local low)
        if lows[i] == min(lows[i-window:i+window+1]):
            touches = sum(1 for l in lows if abs(l - lows[i]) / lows[i] < 0.01)
            if touches >= min_touches:
                support_levels.append({
                    'price': float(lows[i]),
                    'touches': touches,
                    'strength': touches / window
                })
    
    # Sort by strength and remove duplicates (within 1%)
    def deduplicate(levels):
        levels.sort(key=lambda x: x['strength'], reverse=True)
        unique = []
        for level in levels:
            if not any(abs(level['price'] - u['price']) / u['price'] < 0.01 for u in unique):
                unique.append(level)
        return unique[:10]  # Top 10
    
    return {
        'resistance': deduplicate(resistance_levels),
        'support': deduplicate(support_levels)
    }


def _analyze_market_structure(df: pd.DataFrame) -> Dict:
    """Analyze market structure (higher highs, higher lows, etc.)."""
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    
    # Find swing points
    swing_highs = []
    swing_lows = []
    
    for i in range(2, len(df) - 2):
        # Swing high
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append({'index': i, 'price': highs[i]})
        # Swing low
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append({'index': i, 'price': lows[i]})
    
    # Analyze structure
    structure = MarketStructure.RANGING
    trend = TrendDirection.SIDEWAYS
    
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        # Check for higher highs and higher lows (uptrend)
        recent_highs = swing_highs[-3:]
        recent_lows = swing_lows[-3:]
        
        higher_highs = all(recent_highs[i]['price'] > recent_highs[i-1]['price'] for i in range(1, len(recent_highs)))
        higher_lows = all(recent_lows[i]['price'] > recent_lows[i-1]['price'] for i in range(1, len(recent_lows)))
        
        lower_highs = all(recent_highs[i]['price'] < recent_highs[i-1]['price'] for i in range(1, len(recent_highs)))
        lower_lows = all(recent_lows[i]['price'] < recent_lows[i-1]['price'] for i in range(1, len(recent_lows)))
        
        if higher_highs and higher_lows:
            structure = MarketStructure.UPTREND
            trend = TrendDirection.BULLISH
        elif lower_highs and lower_lows:
            structure = MarketStructure.DOWNTREND
            trend = TrendDirection.BEARISH
        elif higher_highs and lower_lows:
            structure = MarketStructure.DISTRIBUTION
        elif lower_highs and higher_lows:
            structure = MarketStructure.ACCUMULATION
    
    return {
        'structure': structure.value,
        'trend': trend.value,
        'swing_highs_count': len(swing_highs),
        'swing_lows_count': len(swing_lows),
        'recent_swing_highs': [{'price': float(h['price']), 'index': int(h['index'])} for h in swing_highs[-5:]],
        'recent_swing_lows': [{'price': float(l['price']), 'index': int(l['index'])} for l in swing_lows[-5:]]
    }


def _detect_accumulation(df: pd.DataFrame) -> Dict:
    """Detect accumulation patterns."""
    closes = df['close'].values
    volumes = df['volume'].values
    highs = df['high'].values
    lows = df['low'].values
    
    signals = []
    score = 0
    
    # Volume increasing on down days (smart money buying)
    for i in range(1, min(20, len(df))):
        if closes[-i] < closes[-i-1] and volumes[-i] > volumes[-i-1] * 1.2:
            signals.append(f"Volume up {volumes[-i]/volumes[-i-1]:.1f}x on down day {i} days ago")
            score += 1
    
    # Price making higher lows while volume decreases (absorption)
    if len(df) >= 10:
        recent_lows = lows[-10:]
        recent_volumes = volumes[-10:]
        if all(recent_lows[i] >= recent_lows[i-1] for i in range(1, len(recent_lows))):
            if np.mean(recent_volumes[:5]) > np.mean(recent_volumes[5:]):
                signals.append("Higher lows with decreasing volume (absorption)")
                score += 2
    
    # OBV trending up while price flat/down
    obv = _calculate_obv(pd.Series(closes), pd.Series(volumes))
    if len(obv) >= 20:
        obv_trend = obv.iloc[-1] - obv.iloc[-20]
        price_trend = closes[-1] - closes[-20]
        if obv_trend > 0 and price_trend <= 0:
            signals.append("OBV rising while price flat/declining (accumulation)")
            score += 2
    
    # Test of support with volume spike
    support_resistance = _detect_support_resistance(df)
    current_price = closes[-1]
    for level in support_resistance['support']:
        if abs(current_price - level['price']) / current_price < 0.02:  # Within 2% of support
            if volumes[-1] > np.mean(volumes[-20:]) * 1.5:
                signals.append(f"Test of support at ${level['price']:.4f} with volume spike")
                score += 2
    
    return {
        'is_accumulating': score >= 3,
        'score': score,
        'max_score': 7,
        'signals': signals,
        'confidence': min(score / 7, 1.0)
    }


def _detect_breakout(df: pd.DataFrame, lookback: int = 20) -> Dict:
    """Detect breakout patterns."""
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    volumes = df['volume'].values
    
    signals = []
    score = 0
    breakout_type = None
    
    if len(df) < lookback + 5:
        return {'is_breakout': False, 'score': 0, 'signals': ['Insufficient data']}
    
    # Resistance level (recent highs)
    resistance = max(highs[-lookback:-5])
    support = min(lows[-lookback:-5])
    
    current_price = closes[-1]
    current_volume = volumes[-1]
    avg_volume = np.mean(volumes[-lookback:-1])
    
    # Upside breakout
    if current_price > resistance * 1.005:  # 0.5% above resistance
        breakout_type = "upside"
        signals.append(f"Price broke above resistance at ${resistance:.4f}")
        score += 2
        
        if current_volume > avg_volume * 1.5:
            signals.append(f"Breakout volume {current_volume/avg_volume:.1f}x average")
            score += 2
        
        # Retest check
        for i in range(1, min(5, len(df))):
            if lows[-i] <= resistance * 1.01 and lows[-i] >= resistance * 0.99:
                if closes[-i] > resistance:
                    signals.append(f"Successful retest of resistance at ${resistance:.4f}")
                    score += 1
                break
    
    # Downside breakout
    elif current_price < support * 0.995:
        breakout_type = "downside"
        signals.append(f"Price broke below support at ${support:.4f}")
        score += 2
        
        if current_volume > avg_volume * 1.5:
            signals.append(f"Breakdown volume {current_volume/avg_volume:.1f}x average")
            score += 2
    
    # Volume confirmation
    if current_volume > avg_volume * 2:
        signals.append("Exceptional volume on breakout")
        score += 1
    
    return {
        'is_breakout': score >= 3,
        'breakout_type': breakout_type,
        'score': score,
        'max_score': 7,
        'signals': signals,
        'resistance': float(resistance),
        'support': float(support),
        'current_price': float(current_price),
        'volume_ratio': float(current_volume / avg_volume) if avg_volume > 0 else 0,
        'confidence': min(score / 7, 1.0)
    }


def _calculate_indicators(df: pd.DataFrame) -> Dict:
    """Calculate all technical indicators."""
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    # RSI
    rsi = _calculate_rsi(close)
    current_rsi = float(rsi.iloc[-1]) if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50
    
    # MACD
    macd_line, signal_line, histogram = _calculate_macd(close)
    current_macd = float(macd_line.iloc[-1]) if not macd_line.empty and not pd.isna(macd_line.iloc[-1]) else 0
    current_signal = float(signal_line.iloc[-1]) if not signal_line.empty and not pd.isna(signal_line.iloc[-1]) else 0
    current_hist = float(histogram.iloc[-1]) if not histogram.empty and not pd.isna(histogram.iloc[-1]) else 0
    
    # EMAs
    emas = {}
    for period in [9, 21, 50, 200]:
        ema = _calculate_ema(close, period)
        emas[f'ema_{period}'] = float(ema.iloc[-1]) if not ema.empty and not pd.isna(ema.iloc[-1]) else close.iloc[-1]
    
    # OBV
    obv = _calculate_obv(close, volume)
    current_obv = float(obv.iloc[-1]) if not obv.empty and not pd.isna(obv.iloc[-1]) else 0
    obv_change = float(obv.iloc[-1] - obv.iloc[-20]) if len(obv) >= 20 else 0
    
    # ATR
    atr = _calculate_atr(high, low, close)
    current_atr = float(atr.iloc[-1]) if not atr.empty and not pd.isna(atr.iloc[-1]) else 0
    atr_pct = (current_atr / close.iloc[-1]) * 100 if close.iloc[-1] > 0 else 0
    
    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = _calculate_bollinger_bands(close)
    bb_position = (close.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) if bb_upper.iloc[-1] != bb_lower.iloc[-1] else 0.5
    
    return {
        'rsi': current_rsi,
        'macd': {
            'macd': current_macd,
            'signal': current_signal,
            'histogram': current_hist,
            'trend': 'bullish' if current_macd > current_signal else 'bearish'
        },
        'emas': emas,
        'obv': current_obv,
        'obv_change_20': obv_change,
        'atr': current_atr,
        'atr_pct': atr_pct,
        'bollinger_bands': {
            'upper': float(bb_upper.iloc[-1]),
            'middle': float(bb_middle.iloc[-1]),
            'lower': float(bb_lower.iloc[-1]),
            'position': float(bb_position)
        }
    }


class TechnicalTools:
    """Technical analysis tools."""
    
    def __init__(self):
        pass
    
    async def calculate_rsi(self, ohlcv: Dict, period: int = 14) -> ToolResult:
        """Calculate RSI."""
        try:
            df = _prepare_dataframe(ohlcv)
            rsi = _calculate_rsi(df['close'], period)
            current = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
            
            # Interpretation
            if current > 70:
                signal = "overbought"
            elif current < 30:
                signal = "oversold"
            elif current > 50:
                signal = "bullish"
            else:
                signal = "bearish"
            
            return ToolResult(
                success=True,
                data={
                    'rsi': current,
                    'period': period,
                    'signal': signal,
                    'values': rsi.dropna().tail(20).tolist()
                },
                source="calculated",
                timestamp=datetime.utcnow(),
                metadata={"period": period}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def calculate_macd(self, ohlcv: Dict, fast: int = 12, slow: int = 26, signal: int = 9) -> ToolResult:
        """Calculate MACD."""
        try:
            df = _prepare_dataframe(ohlcv)
            macd_line, signal_line, histogram = _calculate_macd(df['close'], fast, slow, signal)
            
            current_macd = float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0
            current_signal = float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0
            current_hist = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0
            
            trend = "bullish" if current_macd > current_signal else "bearish"
            crossover = "bullish" if current_hist > 0 and histogram.iloc[-2] <= 0 else ("bearish" if current_hist < 0 and histogram.iloc[-2] >= 0 else "none")
            
            return ToolResult(
                success=True,
                data={
                    'macd': current_macd,
                    'signal': current_signal,
                    'histogram': current_hist,
                    'trend': trend,
                    'crossover': crossover,
                    'fast': fast,
                    'slow': slow,
                    'signal_period': signal
                },
                source="calculated",
                timestamp=datetime.utcnow(),
                metadata={"fast": fast, "slow": slow, "signal": signal}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def calculate_ema(self, ohlcv: Dict, periods: List[int] = None) -> ToolResult:
        """Calculate EMAs."""
        try:
            if periods is None:
                periods = [9, 21, 50, 200]
            
            df = _prepare_dataframe(ohlcv)
            emas = {}
            signals = {}
            
            for period in periods:
                ema = _calculate_ema(df['close'], period)
                value = float(ema.iloc[-1]) if not pd.isna(ema.iloc[-1]) else df['close'].iloc[-1]
                emas[f'ema_{period}'] = value
                
                # Price vs EMA
                if df['close'].iloc[-1] > value:
                    signals[f'ema_{period}'] = "above"
                else:
                    signals[f'ema_{period}'] = "below"
            
            # EMA alignment
            ema_values = [emas[f'ema_{p}'] for p in sorted(periods)]
            alignment = "bullish" if all(ema_values[i] > ema_values[i+1] for i in range(len(ema_values)-1)) else ("bearish" if all(ema_values[i] < ema_values[i+1] for i in range(len(ema_values)-1)) else "mixed")
            
            return ToolResult(
                success=True,
                data={
                    'emas': emas,
                    'signals': signals,
                    'alignment': alignment,
                    'periods': periods
                },
                source="calculated",
                timestamp=datetime.utcnow(),
                metadata={"periods": periods}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def calculate_obv(self, ohlcv: Dict) -> ToolResult:
        """Calculate On-Balance Volume."""
        try:
            df = _prepare_dataframe(ohlcv)
            obv = _calculate_obv(df['close'], df['volume'])
            
            current = float(obv.iloc[-1]) if not pd.isna(obv.iloc[-1]) else 0
            change_20 = float(obv.iloc[-1] - obv.iloc[-20]) if len(obv) >= 20 else 0
            
            trend = "rising" if change_20 > 0 else "falling"
            divergence = "bullish" if change_20 > 0 and df['close'].iloc[-1] < df['close'].iloc[-20] else ("bearish" if change_20 < 0 and df['close'].iloc[-1] > df['close'].iloc[-20] else "none")
            
            return ToolResult(
                success=True,
                data={
                    'obv': current,
                    'change_20': change_20,
                    'trend': trend,
                    'divergence': divergence
                },
                source="calculated",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def calculate_atr(self, ohlcv: Dict, period: int = 14) -> ToolResult:
        """Calculate Average True Range."""
        try:
            df = _prepare_dataframe(ohlcv)
            atr = _calculate_atr(df['high'], df['low'], df['close'], period)
            
            current = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0
            atr_pct = (current / df['close'].iloc[-1]) * 100 if df['close'].iloc[-1] > 0 else 0
            
            return ToolResult(
                success=True,
                data={
                    'atr': current,
                    'atr_pct': atr_pct,
                    'period': period
                },
                source="calculated",
                timestamp=datetime.utcnow(),
                metadata={"period": period}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def detect_support_resistance(self, ohlcv: Dict, window: int = 20, min_touches: int = 2) -> ToolResult:
        """Detect support and resistance levels."""
        try:
            df = _prepare_dataframe(ohlcv)
            levels = _detect_support_resistance(df, window, min_touches)
            
            current_price = df['close'].iloc[-1]
            
            # Find nearest levels
            nearest_resistance = min(levels['resistance'], key=lambda x: abs(x['price'] - current_price)) if levels['resistance'] else None
            nearest_support = min(levels['support'], key=lambda x: abs(x['price'] - current_price)) if levels['support'] else None
            
            return ToolResult(
                success=True,
                data={
                    'resistance': levels['resistance'],
                    'support': levels['support'],
                    'current_price': float(current_price),
                    'nearest_resistance': nearest_resistance,
                    'nearest_support': nearest_support,
                    'distance_to_resistance_pct': ((nearest_resistance['price'] - current_price) / current_price * 100) if nearest_resistance else None,
                    'distance_to_support_pct': ((current_price - nearest_support['price']) / current_price * 100) if nearest_support else None
                },
                source="calculated",
                timestamp=datetime.utcnow(),
                metadata={"window": window, "min_touches": min_touches}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def detect_breakout(self, ohlcv: Dict, lookback: int = 20) -> ToolResult:
        """Detect breakout patterns."""
        try:
            df = _prepare_dataframe(ohlcv)
            result = _detect_breakout(df, lookback)
            
            return ToolResult(
                success=True,
                data=result,
                source="calculated",
                timestamp=datetime.utcnow(),
                metadata={"lookback": lookback}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def detect_accumulation(self, ohlcv: Dict) -> ToolResult:
        """Detect accumulation patterns."""
        try:
            df = _prepare_dataframe(ohlcv)
            result = _detect_accumulation(df)
            
            return ToolResult(
                success=True,
                data=result,
                source="calculated",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def analyze_market_structure(self, ohlcv: Dict) -> ToolResult:
        """Analyze market structure."""
        try:
            df = _prepare_dataframe(ohlcv)
            structure = _analyze_market_structure(df)
            
            return ToolResult(
                success=True,
                data=structure,
                source="calculated",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def full_technical_analysis(self, ohlcv: Dict) -> ToolResult:
        """Perform complete technical analysis."""
        try:
            df = _prepare_dataframe(ohlcv)
            
            indicators = _calculate_indicators(df)
            structure = _analyze_market_structure(df)
            support_resistance = _detect_support_resistance(df)
            accumulation = _detect_accumulation(df)
            breakout = _detect_breakout(df)
            
            # Overall assessment
            bullish_signals = 0
            bearish_signals = 0
            
            # RSI
            if indicators['rsi'] < 30:
                bullish_signals += 1
            elif indicators['rsi'] > 70:
                bearish_signals += 1
            
            # MACD
            if indicators['macd']['trend'] == 'bullish':
                bullish_signals += 1
            else:
                bearish_signals += 1
            
            # EMA alignment
            if indicators['emas']['ema_9'] > indicators['emas']['ema_21'] > indicators['emas']['ema_50']:
                bullish_signals += 1
            elif indicators['emas']['ema_9'] < indicators['emas']['ema_21'] < indicators['emas']['ema_50']:
                bearish_signals += 1
            
            # OBV
            if indicators['obv_change_20'] > 0:
                bullish_signals += 1
            else:
                bearish_signals += 1
            
            # Structure
            if structure['trend'] == 'bullish':
                bullish_signals += 2
            elif structure['trend'] == 'bearish':
                bearish_signals += 2
            
            # Accumulation
            if accumulation['is_accumulating']:
                bullish_signals += 2
            
            # Breakout
            if breakout['is_breakout'] and breakout['breakout_type'] == 'upside':
                bullish_signals += 2
            elif breakout['is_breakout'] and breakout['breakout_type'] == 'downside':
                bearish_signals += 2
            
            total = bullish_signals + bearish_signals
            bias = "bullish" if bullish_signals > bearish_signals else ("bearish" if bearish_signals > bullish_signals else "neutral")
            confidence = abs(bullish_signals - bearish_signals) / total if total > 0 else 0
            
            return ToolResult(
                success=True,
                data={
                    'indicators': indicators,
                    'structure': structure,
                    'support_resistance': support_resistance,
                    'accumulation': accumulation,
                    'breakout': breakout,
                    'summary': {
                        'bias': bias,
                        'confidence': confidence,
                        'bullish_signals': bullish_signals,
                        'bearish_signals': bearish_signals,
                        'total_signals': total
                    }
                },
                source="calculated",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="calculated",
                timestamp=datetime.utcnow(),
                error=str(e)
            )


# Tool function wrappers
async def _resolve_ohlcv(
    symbol: str = "",
    ohlcv: Optional[Dict] = None,
    days: int = 200,
) -> Optional[Dict]:
    """Return an OHLCV payload, fetching it by symbol when needed."""
    if ohlcv and all(k in ohlcv for k in ("highs", "lows", "closes", "volumes")):
        return ohlcv
    if not symbol:
        return None
    from providers.market_data import get_market_data_provider
    provider = await get_market_data_provider()
    data = await provider.get_historical_ohlcv(symbol, "1d", days)
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


def _ohlcv_missing(symbol: str) -> Dict:
    return {
        "success": False,
        "data": None,
        "source": "calculated",
        "timestamp": datetime.utcnow().isoformat(),
        "error": f"No OHLCV data for {symbol or 'input'}",
        "metadata": {},
    }


async def calculate_rsi(symbol: str = "", ohlcv: Optional[Dict] = None, period: int = 14, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().calculate_rsi(data, period)).to_dict()


async def calculate_macd(symbol: str = "", ohlcv: Optional[Dict] = None, fast: int = 12, slow: int = 26, signal: int = 9, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().calculate_macd(data, fast, slow, signal)).to_dict()


async def calculate_ema(symbol: str = "", ohlcv: Optional[Dict] = None, periods: List[int] = None, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().calculate_ema(data, periods)).to_dict()


async def calculate_obv(symbol: str = "", ohlcv: Optional[Dict] = None, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().calculate_obv(data)).to_dict()


async def calculate_atr(symbol: str = "", ohlcv: Optional[Dict] = None, period: int = 14, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().calculate_atr(data, period)).to_dict()


async def detect_support_resistance(symbol: str = "", ohlcv: Optional[Dict] = None, window: int = 20, min_touches: int = 2, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().detect_support_resistance(data, window, min_touches)).to_dict()


async def detect_breakout(symbol: str = "", ohlcv: Optional[Dict] = None, lookback: int = 20, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().detect_breakout(data, lookback)).to_dict()


async def detect_accumulation(symbol: str = "", ohlcv: Optional[Dict] = None, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().detect_accumulation(data)).to_dict()


async def analyze_market_structure(symbol: str = "", ohlcv: Optional[Dict] = None, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().analyze_market_structure(data)).to_dict()


async def full_technical_analysis(symbol: str = "", ohlcv: Optional[Dict] = None, days: int = 200) -> Dict:
    data = await _resolve_ohlcv(symbol, ohlcv, days)
    if not data:
        return _ohlcv_missing(symbol)
    return (await TechnicalTools().full_technical_analysis(data)).to_dict()


# Tool definitions for AI function calling
TECHNICAL_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_rsi",
            "description": "Calculate Relative Strength Index (RSI)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data with timestamps, opens, highs, lows, closes, volumes"},
                    "period": {"type": "integer", "description": "RSI period", "default": 14}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_macd",
            "description": "Calculate MACD (Moving Average Convergence Divergence)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"},
                    "fast": {"type": "integer", "default": 12},
                    "slow": {"type": "integer", "default": 26},
                    "signal": {"type": "integer", "default": 9}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_ema",
            "description": "Calculate Exponential Moving Averages",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"},
                    "periods": {"type": "array", "items": {"type": "integer"}, "default": [9, 21, 50, 200]}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_obv",
            "description": "Calculate On-Balance Volume",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_atr",
            "description": "Calculate Average True Range",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"},
                    "period": {"type": "integer", "default": 14}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_support_resistance",
            "description": "Detect support and resistance levels",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"},
                    "window": {"type": "integer", "default": 20},
                    "min_touches": {"type": "integer", "default": 2}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_breakout",
            "description": "Detect breakout patterns",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"},
                    "lookback": {"type": "integer", "default": 20}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_accumulation",
            "description": "Detect accumulation patterns",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_market_structure",
            "description": "Analyze market structure (trends, swing points)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "full_technical_analysis",
            "description": "Perform complete technical analysis with all indicators",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"}
                },
                "required": ["symbol"]
            }
        }
    }
]