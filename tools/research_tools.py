"""
Research tools for the Crypto Intelligence Agent.
Compares coins, searches historical patterns, calculates potential, evaluates tokenomics.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import xml.etree.ElementTree as xml_et
import httpx
import numpy as np


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


class ResearchTools:
    """Research and analysis tools."""
    
    def __init__(self):
        pass
    
    async def compare_coins(self, coins_data: List[Dict]) -> ToolResult:
        """Compare multiple coins across key metrics."""
        try:
            if not coins_data:
                return ToolResult(
                    success=False,
                    data=None,
                    source="research",
                    timestamp=datetime.utcnow(),
                    error="No coin data provided"
                )
            
            comparison = {
                'coins': [],
                'best_by_metric': {}
            }
            
            metrics = [
                'market_cap', 'volume_24h', 'price_change_24h', 'price_change_7d',
                'price_change_30d', 'circulating_supply', 'total_supply'
            ]
            
            for coin in coins_data:
                coin_info = {
                    'symbol': coin.get('symbol', ''),
                    'name': coin.get('name', ''),
                    'current_price': coin.get('current_price', 0),
                    'market_cap': coin.get('market_cap', 0),
                    'market_cap_rank': coin.get('market_cap_rank', 0),
                    'volume_24h': coin.get('total_volume', 0),
                    'price_change_24h': coin.get('price_change_percentage_24h', 0),
                    'price_change_7d': coin.get('price_change_percentage_7d', 0),
                    'price_change_30d': coin.get('price_change_percentage_30d', 0),
                    'circulating_supply': coin.get('circulating_supply', 0),
                    'total_supply': coin.get('total_supply', 0),
                    'max_supply': coin.get('max_supply', 0),
                    'supply_ratio': coin.get('circulating_supply', 0) / coin.get('total_supply', 1) if coin.get('total_supply', 0) > 0 else 0
                }
                comparison['coins'].append(coin_info)
            
            # Find best by each metric
            for metric in metrics:
                if metric in ['market_cap', 'volume_24h', 'price_change_24h', 'price_change_7d', 'price_change_30d']:
                    best = max(comparison['coins'], key=lambda x: x.get(metric, 0))
                else:
                    best = min(comparison['coins'], key=lambda x: x.get(metric, float('inf')))
                comparison['best_by_metric'][metric] = best['symbol']
            
            return ToolResult(
                success=True,
                data=comparison,
                source="research",
                timestamp=datetime.utcnow(),
                metadata={"compared_count": len(coins_data)}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="research",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def search_historical_patterns(self, ohlcv: Dict, pattern_type: str = "all") -> ToolResult:
        """Search for historical chart patterns."""
        try:
            closes = np.array(ohlcv['closes'])
            highs = np.array(ohlcv['highs'])
            lows = np.array(ohlcv['lows'])
            volumes = np.array(ohlcv['volumes'])
            
            if len(closes) < 50:
                return ToolResult(
                    success=False,
                    data=None,
                    source="research",
                    timestamp=datetime.utcnow(),
                    error="Insufficient data for pattern detection (need 50+ candles)"
                )
            
            patterns = []
            
            # Double bottom/top
            if pattern_type in ["all", "double_bottom", "double_top"]:
                patterns.extend(self._detect_double_patterns(highs, lows, closes))
            
            # Head and shoulders
            if pattern_type in ["all", "head_shoulders"]:
                patterns.extend(self._detect_head_shoulders(highs, lows))
            
            # Cup and handle
            if pattern_type in ["all", "cup_handle"]:
                patterns.extend(self._detect_cup_handle(closes, volumes))
            
            # Flags and pennants
            if pattern_type in ["all", "flags"]:
                patterns.extend(self._detect_flags_pennants(closes, volumes))
            
            # Triangles
            if pattern_type in ["all", "triangles"]:
                patterns.extend(self._detect_triangles(highs, lows, closes))
            
            return ToolResult(
                success=True,
                data={
                    'patterns': patterns,
                    'pattern_count': len(patterns),
                    'data_points': len(closes)
                },
                source="research",
                timestamp=datetime.utcnow(),
                metadata={"pattern_type": pattern_type}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="research",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    def _detect_double_patterns(self, highs, lows, closes) -> List[Dict]:
        """Detect double bottom and double top patterns."""
        patterns = []
        window = 20
        
        for i in range(window, len(closes) - window):
            # Double bottom - two similar lows
            if lows[i] == min(lows[i-window:i+window]):
                # Look for previous similar low
                for j in range(i - window * 2, i - window):
                    if j >= 0 and abs(lows[j] - lows[i]) / lows[i] < 0.03:  # Within 3%
                        # Check for peak between them
                        peak = max(highs[j:i])
                        if peak > lows[i] * 1.1:  # At least 10% bounce
                            patterns.append({
                                'type': 'double_bottom',
                                'first_bottom': {'index': int(j), 'price': float(lows[j])},
                                'second_bottom': {'index': int(i), 'price': float(lows[i])},
                                'neckline': float(peak),
                                'target': float(peak + (peak - lows[i])),
                                'confidence': 0.7
                            })
            
            # Double top - two similar highs
            if highs[i] == max(highs[i-window:i+window]):
                for j in range(i - window * 2, i - window):
                    if j >= 0 and abs(highs[j] - highs[i]) / highs[i] < 0.03:
                        trough = min(lows[j:i])
                        if trough < highs[i] * 0.9:
                            patterns.append({
                                'type': 'double_top',
                                'first_top': {'index': int(j), 'price': float(highs[j])},
                                'second_top': {'index': int(i), 'price': float(highs[i])},
                                'neckline': float(trough),
                                'target': float(trough - (highs[i] - trough)),
                                'confidence': 0.7
                            })
        
        return patterns[-5:]  # Return last 5
    
    def _detect_head_shoulders(self, highs, lows) -> List[Dict]:
        """Detect head and shoulders patterns."""
        patterns = []
        window = 5
        
        # Find peaks
        peaks = []
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i-window:i+window]):
                peaks.append({'index': i, 'price': highs[i]})
        
        # Look for head and shoulders (3 peaks, middle highest)
        for i in range(2, len(peaks)):
            left = peaks[i-2]
            head = peaks[i-1]
            right = peaks[i]
            
            if (head['price'] > left['price'] and head['price'] > right['price'] and
                abs(left['price'] - right['price']) / left['price'] < 0.05):  # Shoulders similar
                
                # Find neckline
                neckline = min(lows[left['index']:right['index']])
                
                patterns.append({
                    'type': 'head_shoulders',
                    'left_shoulder': {'index': left['index'], 'price': float(left['price'])},
                    'head': {'index': head['index'], 'price': float(head['price'])},
                    'right_shoulder': {'index': right['index'], 'price': float(right['price'])},
                    'neckline': float(neckline),
                    'target': float(neckline - (head['price'] - neckline)),
                    'confidence': 0.75
                })
        
        return patterns[-3:]
    
    def _detect_cup_handle(self, closes, volumes) -> List[Dict]:
        """Detect cup and handle pattern."""
        patterns = []
        
        # Simplified: look for U-shape followed by small pullback
        window = 50
        if len(closes) < window * 2:
            return patterns
        
        for i in range(window, len(closes) - 10):
            # Cup: price goes down then up to similar level
            cup_start = closes[i - window]
            cup_bottom = min(closes[i - window:i])
            cup_end = closes[i]
            
            if (abs(cup_start - cup_end) / cup_start < 0.05 and  # Start ~ end
                cup_bottom < cup_start * 0.8):  # At least 20% drop
                
                # Handle: small pullback after cup
                handle_end = min(closes[i:i+10])
                if handle_end > cup_bottom and handle_end < cup_end * 0.95:
                    patterns.append({
                        'type': 'cup_handle',
                        'cup_start': {'index': i - window, 'price': float(cup_start)},
                        'cup_bottom': {'index': int(np.argmin(closes[i-window:i]) + i - window), 'price': float(cup_bottom)},
                        'cup_end': {'index': i, 'price': float(cup_end)},
                        'handle_low': {'index': int(np.argmin(closes[i:i+10]) + i), 'price': float(handle_end)},
                        'target': float(cup_end + (cup_end - cup_bottom)),
                        'confidence': 0.65
                    })
        
        return patterns[-3:]
    
    def _detect_flags_pennants(self, closes, volumes) -> List[Dict]:
        """Detect flag and pennant patterns."""
        patterns = []
        window = 20
        
        # Look for strong move followed by consolidation
        for i in range(window, len(closes) - 10):
            # Flagpole: strong move
            pole_start = closes[i - window]
            pole_end = closes[i]
            pole_change = (pole_end - pole_start) / pole_start
            
            if abs(pole_change) > 0.15:  # >15% move
                # Consolidation: small range
                consolidation = closes[i:i+10]
                cons_range = (max(consolidation) - min(consolidation)) / pole_end
                
                if cons_range < 0.05:  # <5% range
                    # Volume should decrease during consolidation
                    vol_pole = np.mean(volumes[i-window:i])
                    vol_cons = np.mean(volumes[i:i+10])
                    
                    patterns.append({
                        'type': 'bull_flag' if pole_change > 0 else 'bear_flag',
                        'pole_start': {'index': i - window, 'price': float(pole_start)},
                        'pole_end': {'index': i, 'price': float(pole_end)},
                        'pole_change_pct': pole_change * 100,
                        'consolidation_range_pct': cons_range * 100,
                        'volume_decrease': vol_cons < vol_pole * 0.7,
                        'target': float(pole_end + (pole_end - pole_start)) if pole_change > 0 else float(pole_end - (pole_start - pole_end)),
                        'confidence': 0.7
                    })
        
        return patterns[-3:]
    
    def _detect_triangles(self, highs, lows, closes) -> List[Dict]:
        """Detect triangle patterns (ascending, descending, symmetrical)."""
        patterns = []
        window = 30
        
        if len(closes) < window:
            return patterns
        
        # Get recent highs and lows
        recent_highs = highs[-window:]
        recent_lows = lows[-window:]
        
        # Fit lines
        x = np.arange(window)
        
        # Upper trendline (highs)
        high_slope, high_intercept = np.polyfit(x, recent_highs, 1)
        # Lower trendline (lows)
        low_slope, low_intercept = np.polyfit(x, recent_lows, 1)
        
        # Classify triangle
        if high_slope < -0.001 and low_slope > 0.001:
            triangle_type = "symmetrical"
        elif abs(high_slope) < 0.001 and low_slope > 0.001:
            triangle_type = "ascending"
        elif high_slope < -0.001 and abs(low_slope) < 0.001:
            triangle_type = "descending"
        else:
            triangle_type = "none"
        
        if triangle_type != "none":
            # Calculate convergence point
            if high_slope != low_slope:
                converge_x = (low_intercept - high_intercept) / (high_slope - low_intercept)
                converge_price = high_slope * converge_x + high_intercept
            else:
                converge_x = window * 2
                converge_price = high_slope * converge_x + high_intercept
            
            patterns.append({
                'type': f'{triangle_type}_triangle',
                'upper_slope': float(high_slope),
                'lower_slope': float(low_slope),
                'convergence_index': float(converge_x),
                'convergence_price': float(converge_price),
                'current_price': float(closes[-1]),
                'breakout_direction': 'up' if triangle_type in ['ascending', 'symmetrical'] else 'down',
                'confidence': 0.6
            })
        
        return patterns
    
    async def calculate_potential_upside(self, coin_data: Dict, ohlcv: Dict) -> ToolResult:
        """Calculate potential upside based on technical and fundamental factors."""
        try:
            current_price = coin_data.get('current_price', 0)
            if current_price == 0:
                return ToolResult(
                    success=False,
                    data=None,
                    source="research",
                    timestamp=datetime.utcnow(),
                    error="Current price not available"
                )
            
            # Technical targets
            highs = np.array(ohlcv['highs'])
            lows = np.array(ohlcv['lows'])
            closes = np.array(ohlcv['closes'])
            
            # Resistance levels
            recent_high = max(highs[-50:]) if len(highs) >= 50 else max(highs)
            all_time_high = coin_data.get('ath', recent_high)
            
            # Fibonacci levels from recent low
            recent_low = min(lows[-50:]) if len(lows) >= 50 else min(lows)
            fib_levels = {
                '0.236': recent_low + (recent_high - recent_low) * 0.236,
                '0.382': recent_low + (recent_high - recent_low) * 0.382,
                '0.5': recent_low + (recent_high - recent_low) * 0.5,
                '0.618': recent_low + (recent_high - recent_low) * 0.618,
                '0.786': recent_low + (recent_high - recent_low) * 0.786
            }
            
            # Risk/reward scenarios
            stop_loss = recent_low * 0.98  # 2% below recent low
            
            targets = {
                'conservative': min(fib_levels['0.382'], recent_high * 1.1),
                'moderate': min(fib_levels['0.618'], recent_high * 1.3),
                'aggressive': min(all_time_high * 1.2, recent_high * 1.5)
            }
            
            scenarios = {}
            for name, target in targets.items():
                upside = ((target - current_price) / current_price) * 100
                risk = ((current_price - stop_loss) / current_price) * 100
                rr_ratio = upside / risk if risk > 0 else 0
                
                scenarios[name] = {
                    'target_price': target,
                    'upside_pct': upside,
                    'stop_loss': stop_loss,
                    'risk_pct': risk,
                    'risk_reward_ratio': rr_ratio
                }
            
            # Probability estimates based on market structure
            market_cap = coin_data.get('market_cap', 0)
            volume = coin_data.get('total_volume', 0)
            
            liquidity_score = min(volume / market_cap * 100, 10) if market_cap > 0 else 0
            
            return ToolResult(
                success=True,
                data={
                    'current_price': current_price,
                    'recent_high': recent_high,
                    'recent_low': recent_low,
                    'all_time_high': all_time_high,
                    'fibonacci_levels': fib_levels,
                    'stop_loss': stop_loss,
                    'targets': targets,
                    'scenarios': scenarios,
                    'liquidity_score': liquidity_score,
                    'distance_to_ath_pct': ((all_time_high - current_price) / current_price * 100) if all_time_high > 0 else 0
                },
                source="research",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="research",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def evaluate_tokenomics(self, coin_data: Dict) -> ToolResult:
        """Evaluate tokenomics quality."""
        try:
            circulating = coin_data.get('circulating_supply', 0)
            total = coin_data.get('total_supply', 0)
            max_supply = coin_data.get('max_supply', 0)
            market_cap = coin_data.get('market_cap', 0)
            fdv = coin_data.get('fully_diluted_valuation', total * coin_data.get('current_price', 0)) if total > 0 else 0
            
            score = 0
            max_score = 10
            factors = []
            
            # Supply ratio
            if total > 0:
                supply_ratio = circulating / total
                if supply_ratio > 0.8:
                    score += 2
                    factors.append("High circulating supply ratio (>80%)")
                elif supply_ratio > 0.5:
                    score += 1
                    factors.append("Moderate circulating supply ratio (50-80%)")
                else:
                    factors.append("Low circulating supply ratio (<50%) - dilution risk")
            
            # Max supply
            if max_supply and max_supply > 0:
                if max_supply == total:
                    score += 1
                    factors.append("Max supply reached - no future inflation")
                else:
                    inflation_remaining = (max_supply - total) / max_supply
                    if inflation_remaining < 0.1:
                        score += 1
                        factors.append("Low remaining inflation (<10%)")
                    elif inflation_remaining < 0.3:
                        factors.append("Moderate remaining inflation (10-30%)")
                    else:
                        factors.append("High remaining inflation (>30%)")
            
            # Market cap vs FDV
            if fdv > 0 and market_cap > 0:
                fdv_ratio = market_cap / fdv
                if fdv_ratio > 0.8:
                    score += 2
                    factors.append("Low FDV dilution (market cap > 80% FDV)")
                elif fdv_ratio > 0.5:
                    score += 1
                    factors.append("Moderate FDV dilution (50-80%)")
                else:
                    factors.append("High FDV dilution (<50%)")
            
            # Price (psychological)
            price = coin_data.get('current_price', 0)
            if 0.01 < price < 1000:
                score += 1
                factors.append("Price in retail-friendly range")
            
            # Volume/market cap ratio (liquidity)
            volume = coin_data.get('total_volume', 0)
            if market_cap > 0:
                vol_mcap = volume / market_cap
                if vol_mcap > 0.1:
                    score += 2
                    factors.append("High liquidity (vol/mcap > 10%)")
                elif vol_mcap > 0.05:
                    score += 1
                    factors.append("Good liquidity (vol/mcap > 5%)")
                else:
                    factors.append("Low liquidity (vol/mcap < 5%)")
            
            # Determine rating
            if score >= 8:
                rating = "excellent"
            elif score >= 6:
                rating = "good"
            elif score >= 4:
                rating = "fair"
            else:
                rating = "poor"
            
            return ToolResult(
                success=True,
                data={
                    'score': score,
                    'max_score': max_score,
                    'rating': rating,
                    'factors': factors,
                    'metrics': {
                        'circulating_supply': circulating,
                        'total_supply': total,
                        'max_supply': max_supply,
                        'supply_ratio': circulating / total if total > 0 else 0,
                        'market_cap': market_cap,
                        'fdv': fdv,
                        'fdv_ratio': market_cap / fdv if fdv > 0 else 0,
                        'volume_24h': volume,
                        'vol_mcap_ratio': volume / market_cap if market_cap > 0 else 0
                    }
                },
                source="research",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="research",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def analyze_token_unlocks(self, coin_data: Dict, unlock_schedule: List[Dict] = None) -> ToolResult:
        """Analyze upcoming token unlocks and their potential impact."""
        try:
            circulating = coin_data.get('circulating_supply', 0)
            total = coin_data.get('total_supply', 0)
            current_price = coin_data.get('current_price', 0)
            market_cap = coin_data.get('market_cap', 0)
            
            if not unlock_schedule:
                # Generate mock schedule based on supply difference
                locked = total - circulating if total > circulating else 0
                unlock_schedule = [
                    {'date': '2024-12-01', 'amount': locked * 0.1, 'type': 'team'},
                    {'date': '2025-03-01', 'amount': locked * 0.15, 'type': 'investors'},
                    {'date': '2025-06-01', 'amount': locked * 0.1, 'type': 'ecosystem'},
                    {'date': '2025-12-01', 'amount': locked * 0.2, 'type': 'team'},
                ]
            
            total_unlock = sum(u['amount'] for u in unlock_schedule)
            unlock_pct = (total_unlock / circulating * 100) if circulating > 0 else 0
            
            # Calculate potential price impact (simplified)
            # Assumes unlocks create selling pressure proportional to unlock size
            daily_volume = coin_data.get('total_volume', 0)
            volume_absorption_days = total_unlock / (daily_volume / current_price) if daily_volume > 0 else float('inf')
            
            impact = "low"
            if unlock_pct > 20 and volume_absorption_days < 30:
                impact = "high"
            elif unlock_pct > 10 or volume_absorption_days < 90:
                impact = "medium"
            
            return ToolResult(
                success=True,
                data={
                    'current_circulating': circulating,
                    'total_supply': total,
                    'locked_supply': total - circulating,
                    'upcoming_unlocks': unlock_schedule,
                    'total_upcoming_unlock': total_unlock,
                    'unlock_percentage_of_circulating': unlock_pct,
                    'estimated_absorption_days': volume_absorption_days,
                    'impact_assessment': impact,
                    'recommendation': "Monitor closely" if impact == "high" else ("Watch" if impact == "medium" else "Low concern")
                },
                source="research",
                timestamp=datetime.utcnow(),
                metadata={"has_custom_schedule": unlock_schedule is not None}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="research",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    async def calculate_risk_score(self, coin_data: Dict, ohlcv: Dict = None) -> ToolResult:
        """Calculate comprehensive risk score."""
        try:
            score = 0
            max_score = 100
            factors = []
            
            # Market cap risk
            mcap = coin_data.get('market_cap', 0)
            if mcap < 10_000_000:
                score += 25
                factors.append("Micro cap (<$10M) - very high risk")
            elif mcap < 50_000_000:
                score += 15
                factors.append("Small cap (<$50M) - high risk")
            elif mcap < 200_000_000:
                score += 8
                factors.append("Mid cap (<$200M) - moderate risk")
            elif mcap < 1_000_000_000:
                score += 3
                factors.append("Large cap (<$1B) - lower risk")
            else:
                factors.append("Mega cap (>$1B) - lowest risk")
            
            # Liquidity risk
            volume = coin_data.get('total_volume', 0)
            if mcap > 0:
                vol_ratio = volume / mcap
                if vol_ratio < 0.01:
                    score += 20
                    factors.append("Very low liquidity (vol/mcap < 1%)")
                elif vol_ratio < 0.05:
                    score += 10
                    factors.append("Low liquidity (vol/mcap < 5%)")
                elif vol_ratio < 0.1:
                    score += 3
                    factors.append("Moderate liquidity (vol/mcap < 10%)")
                else:
                    factors.append("Good liquidity (vol/mcap > 10%)")
            
            # Volatility risk (from OHLCV if available)
            if ohlcv and len(ohlcv['closes']) >= 30:
                closes = np.array(ohlcv['closes'])
                returns = np.diff(closes) / closes[:-1]
                volatility = np.std(returns) * np.sqrt(365) * 100  # Annualized
                
                if volatility > 150:
                    score += 20
                    factors.append(f"Extreme volatility ({volatility:.0f}% annualized)")
                elif volatility > 100:
                    score += 12
                    factors.append(f"High volatility ({volatility:.0f}% annualized)")
                elif volatility > 60:
                    score += 6
                    factors.append(f"Moderate volatility ({volatility:.0f}% annualized)")
                else:
                    factors.append(f"Low volatility ({volatility:.0f}% annualized)")
            
            # Supply risk
            circulating = coin_data.get('circulating_supply', 0)
            total = coin_data.get('total_supply', 0)
            max_supply = coin_data.get('max_supply', 0)
            
            if total > 0:
                supply_ratio = circulating / total
                if supply_ratio < 0.3:
                    score += 15
                    factors.append("Very low circulating supply (<30%) - high dilution risk")
                elif supply_ratio < 0.5:
                    score += 8
                    factors.append("Low circulating supply (<50%) - dilution risk")
                elif supply_ratio < 0.8:
                    score += 3
                    factors.append("Moderate circulating supply (50-80%)")
            
            # Price momentum risk
            change_24h = coin_data.get('price_change_percentage_24h', 0)
            change_7d = coin_data.get('price_change_percentage_7d', 0)
            
            if change_24h > 50:
                score += 10
                factors.append("Extreme 24h pump (>50%) - reversal risk")
            elif change_24h < -30:
                score += 5
                factors.append("Sharp 24h drop (>30%) - momentum risk")
            
            if change_7d > 100:
                score += 8
                factors.append("Parabolic 7d run (>100%) - correction risk")
            
            # Determine risk level
            if score >= 70:
                risk_level = "extreme"
            elif score >= 50:
                risk_level = "high"
            elif score >= 30:
                risk_level = "moderate"
            elif score >= 15:
                risk_level = "low"
            else:
                risk_level = "very_low"
            
            return ToolResult(
                success=True,
                data={
                    'risk_score': score,
                    'max_score': max_score,
                    'risk_level': risk_level,
                    'risk_pct': score / max_score * 100,
                    'factors': factors,
                    'recommendation': self._get_risk_recommendation(risk_level)
                },
                source="research",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="research",
                timestamp=datetime.utcnow(),
                error=str(e)
            )
    
    def _get_risk_recommendation(self, risk_level: str) -> str:
        recommendations = {
            "extreme": "Avoid - only for very experienced traders with tiny position sizes",
            "high": "High risk - small position only, strict stop-loss required",
            "moderate": "Moderate risk - standard position sizing, use stop-loss",
            "low": "Lower risk - suitable for standard allocation",
            "very_low": "Very low risk - suitable for core portfolio allocation"
        }
        return recommendations.get(risk_level, "Unknown risk level")
    
    async def rank_candidates(self, candidates: List[Dict]) -> ToolResult:
        """Rank candidate coins by opportunity score."""
        try:
            if not candidates:
                return ToolResult(
                    success=False,
                    data=None,
                    source="research",
                    timestamp=datetime.utcnow(),
                    error="No candidates provided"
                )
            
            ranked = []
            
            for coin in candidates:
                score = 0
                factors = []
                
                # Market cap sweet spot (50M - 500M)
                mcap = coin.get('market_cap', 0)
                if 50_000_000 <= mcap <= 500_000_000:
                    score += 20
                    factors.append("Ideal market cap range")
                elif 10_000_000 <= mcap < 50_000_000:
                    score += 10
                    factors.append("Small but viable market cap")
                elif mcap > 500_000_000:
                    score += 5
                    factors.append("Large cap - slower growth potential")
                
                # Volume/mcap ratio
                volume = coin.get('total_volume', 0)
                if mcap > 0:
                    vol_ratio = volume / mcap
                    if vol_ratio > 0.2:
                        score += 15
                        factors.append("Excellent liquidity")
                    elif vol_ratio > 0.1:
                        score += 10
                        factors.append("Good liquidity")
                    elif vol_ratio > 0.05:
                        score += 5
                        factors.append("Adequate liquidity")
                
                # Price momentum (positive but not extreme)
                change_24h = coin.get('price_change_percentage_24h', 0)
                change_7d = coin.get('price_change_percentage_7d', 0)
                change_30d = coin.get('price_change_percentage_30d', 0)
                
                if 5 <= change_24h <= 20:
                    score += 10
                    factors.append("Healthy 24h momentum")
                elif change_24h > 50:
                    score -= 5
                    factors.append("Overextended 24h")
                
                if 10 <= change_7d <= 50:
                    score += 10
                    factors.append("Strong weekly trend")
                elif change_7d > 100:
                    score -= 5
                    factors.append("Parabolic weekly")
                
                if change_30d > 0:
                    score += 5
                    factors.append("Positive monthly trend")
                
                # Supply dynamics
                circulating = coin.get('circulating_supply', 0)
                total = coin.get('total_supply', 0)
                if total > 0 and circulating / total > 0.7:
                    score += 10
                    factors.append("High circulating supply")
                
                # Distance from ATH
                ath = coin.get('ath', 0)
                current = coin.get('current_price', 0)
                if ath > 0 and current > 0:
                    ath_dist = (ath - current) / current * 100
                    if 50 <= ath_dist <= 200:
                        score += 10
                        factors.append("Good distance from ATH for recovery")
                    elif ath_dist < 20:
                        score -= 5
                        factors.append("Near ATH - limited upside")
                
                ranked.append({
                    'symbol': coin.get('symbol', ''),
                    'name': coin.get('name', ''),
                    'score': score,
                    'factors': factors,
                    'metrics': {
                        'market_cap': mcap,
                        'volume_24h': volume,
                        'price': current,
                        'change_24h': change_24h,
                        'change_7d': change_7d,
                        'change_30d': change_30d
                    }
                })
            
            # Sort by score descending
            ranked.sort(key=lambda x: x['score'], reverse=True)
            
            # Add rankings
            for i, coin in enumerate(ranked):
                coin['rank'] = i + 1
            
            return ToolResult(
                success=True,
                data={
                    'ranked_candidates': ranked,
                    'total': len(ranked),
                    'top_pick': ranked[0] if ranked else None
                },
                source="research",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                source="research",
                timestamp=datetime.utcnow(),
                error=str(e)
            )


# Tool function wrappers
async def _fetch_coin_data(symbol: str) -> Optional[Dict]:
    """Fetch market data for a symbol from the market data provider."""
    from providers.market_data import get_market_data_provider
    provider = await get_market_data_provider()
    coins = await provider.get_coins_markets(order="market_cap_desc", per_page=500)
    for coin in coins:
        if coin.symbol.upper() == symbol.upper():
            return asdict(coin)
    results = await provider.search_coin(symbol)
    if results:
        return asdict(results[0])
    return None


async def _fetch_ohlcv(symbol: str, days: int = 200) -> Optional[Dict]:
    """Fetch OHLCV data for a symbol."""
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


def _missing(message: str) -> Dict:
    return {
        "success": False,
        "data": None,
        "source": "research",
        "timestamp": datetime.utcnow().isoformat(),
        "error": message,
        "metadata": {},
    }


async def compare_coins(coins_data: Optional[List[Dict]] = None, symbols: Optional[List[str]] = None) -> Dict:
    if not coins_data and symbols:
        coins_data = []
        for sym in symbols:
            coin = await _fetch_coin_data(sym)
            if coin:
                coins_data.append(coin)
    if not coins_data:
        return _missing("No coin data or symbols supplied")
    return (await ResearchTools().compare_coins(coins_data)).to_dict()


async def search_historical_patterns(symbol: str = "", ohlcv: Optional[Dict] = None, pattern_type: str = "all", days: int = 365) -> Dict:
    data = ohlcv or (await _fetch_ohlcv(symbol, days) if symbol else None)
    if not data:
        return _missing(f"No OHLCV data for {symbol or 'input'}")
    return (await ResearchTools().search_historical_patterns(data, pattern_type)).to_dict()


async def calculate_potential_upside(symbol: str = "", coin_data: Optional[Dict] = None, ohlcv: Optional[Dict] = None, days: int = 365) -> Dict:
    if not coin_data and symbol:
        coin_data = await _fetch_coin_data(symbol)
    if not coin_data:
        return _missing(f"No market data for {symbol or 'input'}")
    data = ohlcv or (await _fetch_ohlcv(symbol, days) if symbol else None)
    if not data:
        return _missing(f"No OHLCV data for {symbol or 'input'}")
    return (await ResearchTools().calculate_potential_upside(coin_data, data)).to_dict()


async def evaluate_tokenomics(symbol: str = "", coin_data: Optional[Dict] = None) -> Dict:
    if not coin_data and symbol:
        coin_data = await _fetch_coin_data(symbol)
    if not coin_data:
        return _missing(f"No market data for {symbol or 'input'}")
    return (await ResearchTools().evaluate_tokenomics(coin_data)).to_dict()


async def analyze_token_unlocks(symbol: str = "", coin_data: Optional[Dict] = None, unlock_schedule: List[Dict] = None) -> Dict:
    if not coin_data and symbol:
        coin_data = await _fetch_coin_data(symbol)
    if not coin_data:
        return _missing(f"No market data for {symbol or 'input'}")
    return (await ResearchTools().analyze_token_unlocks(coin_data, unlock_schedule)).to_dict()


async def calculate_risk_score(symbol: str = "", coin_data: Optional[Dict] = None, ohlcv: Optional[Dict] = None, days: int = 200) -> Dict:
    if not coin_data and symbol:
        coin_data = await _fetch_coin_data(symbol)
    if not coin_data:
        return _missing(f"No market data for {symbol or 'input'}")
    data = ohlcv or (await _fetch_ohlcv(symbol, days) if symbol else None)
    return (await ResearchTools().calculate_risk_score(coin_data, data)).to_dict()


async def rank_candidates(candidates: List[Dict]) -> Dict:
    return (await ResearchTools().rank_candidates(candidates)).to_dict()


async def web_search(query: str, max_results: int = 10) -> Dict:
    """Search the web for news, context and research about a topic or coin."""
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = await client.get(
                "https://news.google.com/rss/search",
                params={"q": query, "hl": "en", "gl": "US", "ceid": "US:en"},
            )
            resp.raise_for_status()
            root = xml.etree.ElementTree.fromstring(resp.text)
            entries = root.findall(".//item")
            results = []
            for e in entries[:max_results]:
                title = e.findtext("title") or ""
                link = e.findtext("link") or ""
                pub = e.findtext("pubDate") or ""
                if title.strip():
                    results.append({"title": title.strip(), "url": link.strip(), "published": pub.strip()})
        if not results:
            return _missing(f"No web results found for: {query}")
        return {
            "success": True,
            "data": results,
            "source": "google_news_rss",
            "timestamp": datetime.utcnow().isoformat(),
            "error": None,
            "metadata": {"query": query, "count": len(results), "results": results},
        }
    except Exception as e:
        return _missing(f"Web search failed: {e}")


# Tool definitions for AI function calling
RESEARCH_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for news, context and research about a topic or coin",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'SOL news this week')"},
                    "max_results": {"type": "integer", "description": "Maximum number of results to return", "default": 10}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_coins",
            "description": "Compare multiple coins across key metrics",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {"type": "array", "items": {"type": "string"}, "description": "Coin symbols to compare (e.g. [\"BTC\", \"ETH\"])"},
                    "coins_data": {"type": "array", "items": {"type": "object"}, "description": "Optional pre-fetched coin data objects"}
                },
                "required": ["symbols"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_historical_patterns",
            "description": "Search for historical chart patterns for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "ohlcv": {"type": "object", "description": "OHLCV data"},
                    "pattern_type": {"type": "string", "description": "Pattern type to search", "enum": ["all", "double_bottom", "double_top", "head_shoulders", "cup_handle", "flags", "triangles"], "default": "all"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_potential_upside",
            "description": "Calculate potential upside with risk/reward scenarios for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "coin_data": {"type": "object", "description": "Optional pre-fetched coin market data"},
                    "ohlcv": {"type": "object", "description": "Optional pre-fetched OHLCV data"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_tokenomics",
            "description": "Evaluate tokenomics quality and dilution risk for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "coin_data": {"type": "object", "description": "Optional pre-fetched coin market data with supply info"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_token_unlocks",
            "description": "Analyze upcoming token unlocks and potential impact for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "coin_data": {"type": "object", "description": "Optional pre-fetched coin market data"},
                    "unlock_schedule": {"type": "array", "items": {"type": "object"}, "description": "Optional custom unlock schedule"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_risk_score",
            "description": "Calculate comprehensive risk score for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Coin symbol (e.g. SOL, BTC)"},
                    "coin_data": {"type": "object", "description": "Optional pre-fetched coin market data"},
                    "ohlcv": {"type": "object", "description": "Optional pre-fetched OHLCV data for volatility calculation"}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rank_candidates",
            "description": "Rank candidate coins by opportunity score",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidates": {"type": "array", "items": {"type": "object"}, "description": "List of candidate coin data"}
                },
                "required": ["candidates"]
            }
        }
    }
]