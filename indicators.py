"""
Technical Indicators - pure numpy/pandas implementation
No external TA library needed (works on free tiers)
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(window=d_period).mean()
    return k, d


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    avg_vol = volume.rolling(window=period).mean()
    return volume / avg_vol.replace(0, np.nan)


def analyze_timeframe(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze a single timeframe dataframe (must have columns: open, high, low, close, volume)
    Returns a dict of key metrics and signals.
    """
    if len(df) < 50:
        return {"valid": False}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Moving averages
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200) if len(df) >= 200 else ema(close, 100)

    # Momentum
    rsi_val = rsi(close, 14)
    macd_line, signal_line, hist = macd(close)
    stoch_k, stoch_d = stochastic(high, low, close)

    # Volatility & Volume
    atr_val = atr(high, low, close, 14)
    vol_ratio = volume_ratio(volume, 20)

    # Latest values
    last = {
        "close": float(close.iloc[-1]),
        "ema20": float(ema20.iloc[-1]),
        "ema50": float(ema50.iloc[-1]),
        "ema200": float(ema200.iloc[-1]),
        "rsi": float(rsi_val.iloc[-1]),
        "macd": float(macd_line.iloc[-1]),
        "macd_signal": float(signal_line.iloc[-1]),
        "macd_hist": float(hist.iloc[-1]),
        "stoch_k": float(stoch_k.iloc[-1]),
        "stoch_d": float(stoch_d.iloc[-1]),
        "atr": float(atr_val.iloc[-1]),
        "vol_ratio": float(vol_ratio.iloc[-1]) if not np.isnan(vol_ratio.iloc[-1]) else 1.0,
        "prev_close": float(close.iloc[-2]),
    }

    # Trend direction
    bullish_trend = last["ema20"] > last["ema50"] > last["ema200"]
    bearish_trend = last["ema20"] < last["ema50"] < last["ema200"]

    # Momentum bias
    bullish_mom = (
        last["rsi"] > 50 and
        last["macd"] > last["macd_signal"] and
        last["macd_hist"] > 0 and
        last["stoch_k"] > last["stoch_d"]
    )
    bearish_mom = (
        last["rsi"] < 50 and
        last["macd"] < last["macd_signal"] and
        last["macd_hist"] < 0 and
        last["stoch_k"] < last["stoch_d"]
    )

    # Overbought / Oversold (not extreme only)
    oversold = last["rsi"] < 35 and last["stoch_k"] < 25
    overbought = last["rsi"] > 65 and last["stoch_k"] > 75

    return {
        "valid": True,
        "last": last,
        "bullish_trend": bullish_trend,
        "bearish_trend": bearish_trend,
        "bullish_mom": bullish_mom,
        "bearish_mom": bearish_mom,
        "oversold": oversold,
        "overbought": overbought,
        "atr": last["atr"],
        "vol_ratio": last["vol_ratio"],
        "price": last["close"],
    }


def generate_signal(tf_15m: Dict, tf_1h: Dict, symbol: str, price_change_24h: float = 0.0) -> Dict[str, Any] | None:
    """
    Multi-timeframe confluence signal generator.
    Returns a rich signal dict or None if no good setup.
    """
    if not tf_15m.get("valid") or not tf_1h.get("valid"):
        return None

    score = 0
    direction = None
    reasons = []

    # === Higher timeframe bias (1h has more weight) ===
    if tf_1h["bullish_trend"]:
        score += 2
        reasons.append("اتجاه صاعد على الساعة")
    elif tf_1h["bearish_trend"]:
        score += 2
        reasons.append("اتجاه هابط على الساعة")

    if tf_1h["bullish_mom"]:
        score += 1.5
        reasons.append("زخم إيجابي 1س")
    elif tf_1h["bearish_mom"]:
        score += 1.5
        reasons.append("زخم سلبي 1س")

    # === 15m alignment ===
    if tf_15m["bullish_trend"] and tf_1h["bullish_trend"]:
        score += 1.5
        reasons.append("محاذاة صاعدة 15د+1س")
    elif tf_15m["bearish_trend"] and tf_1h["bearish_trend"]:
        score += 1.5
        reasons.append("محاذاة هابطة 15د+1س")

    if tf_15m["bullish_mom"] and tf_1h["bullish_trend"]:
        score += 1
    if tf_15m["bearish_mom"] and tf_1h["bearish_trend"]:
        score += 1

    # Volume confirmation
    if tf_15m["vol_ratio"] > 1.4:
        score += 1
        reasons.append("حجم مرتفع")
    if tf_15m["vol_ratio"] > 2.0:
        score += 0.5

    # RSI / Stochastic zones
    if tf_15m["oversold"] and tf_1h["bullish_trend"]:
        score += 1.5
        reasons.append("تشبع بيعي + اتجاه صاعد")
    if tf_15m["overbought"] and tf_1h["bearish_trend"]:
        score += 1.5
        reasons.append("تشبع شرائي + اتجاه هابط")

    # Determine direction
    long_conditions = (
        tf_1h["bullish_trend"] and
        (tf_15m["bullish_mom"] or tf_15m["oversold"] or tf_15m["bullish_trend"])
    )
    short_conditions = (
        tf_1h["bearish_trend"] and
        (tf_15m["bearish_mom"] or tf_15m["overbought"] or tf_15m["bearish_trend"])
    )

    if long_conditions and score >= 5:
        direction = "LONG"
    elif short_conditions and score >= 5:
        direction = "SHORT"
    else:
        return None

    # Cap score
    score = min(round(score, 1), 10.0)

    # Only keep relatively strong signals
    if score < 5.5:
        return None

    # Calculate levels using ATR from 15m (more reactive)
    atr = tf_15m["atr"]
    price = tf_15m["price"]

    if direction == "LONG":
        entry = price
        stop = entry - (atr * 1.4)
        t1 = entry + (atr * 1.2)   # ~0.85R
        t2 = entry + (atr * 2.2)   # ~1.5R
        t3 = entry + (atr * 3.5)   # ~2.5R
        risk_pct = ((entry - stop) / entry) * 100
    else:
        entry = price
        stop = entry + (atr * 1.4)
        t1 = entry - (atr * 1.2)
        t2 = entry - (atr * 2.2)
        t3 = entry - (atr * 3.5)
        risk_pct = ((stop - entry) / entry) * 100

    return {
        "symbol": symbol,
        "direction": direction,
        "score": score,
        "entry": round(entry, 8),
        "stop": round(stop, 8),
        "targets": [round(t1, 8), round(t2, 8), round(t3, 8)],
        "risk_pct": round(risk_pct, 2),
        "atr": round(atr, 8),
        "vol_ratio": round(tf_15m["vol_ratio"], 2),
        "rsi_15m": round(tf_15m["last"]["rsi"], 1),
        "rsi_1h": round(tf_1h["last"]["rsi"], 1),
        "change_24h": round(price_change_24h, 2),
        "reasons": reasons[:5],  # top reasons
        "timeframe": "15m + 1h",
    }
