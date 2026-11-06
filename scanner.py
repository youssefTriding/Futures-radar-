"""
Binance Futures Scanner
Fetches liquid USDT-M perpetuals and generates multi-TF signals.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import httpx
import pandas as pd
import numpy as np

from indicators import analyze_timeframe, generate_signal

logger = logging.getLogger("scanner")

BASE_URL = "https://fapi.binance.com"
# Conservative rate limiting
MAX_CONCURRENT = 8
KLINES_LIMIT = 150  # enough for EMA200 on 15m ≈ 37 hours


class FuturesScanner:
    def __init__(self):
        self.signals: List[Dict[str, Any]] = []
        self.last_scan: Optional[datetime] = None
        self.scan_duration: float = 0.0
        self.symbols_scanned: int = 0
        self.status: str = "idle"
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=10.0),
                headers={"User-Agent": "FuturesRadar/1.0"},
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_liquid_symbols(self, min_volume_usdt: float = 3_000_000, limit: int = 280) -> List[Dict]:
        """Return top liquid USDT perpetual symbols by 24h quote volume."""
        client = await self.get_client()
        try:
            resp = await client.get(f"{BASE_URL}/fapi/v1/ticker/24hr")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch tickers: {e}")
            return []

        pairs = []
        for item in data:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            # Skip some non-crypto / weird ones if needed
            try:
                quote_vol = float(item.get("quoteVolume", 0))
                price_change = float(item.get("priceChangePercent", 0))
                last_price = float(item.get("lastPrice", 0))
            except (TypeError, ValueError):
                continue

            if quote_vol >= min_volume_usdt and last_price > 0:
                pairs.append({
                    "symbol": symbol,
                    "volume": quote_vol,
                    "change_24h": price_change,
                    "price": last_price,
                })

        # Sort by volume descending and take top N
        pairs.sort(key=lambda x: x["volume"], reverse=True)
        return pairs[:limit]

    async def fetch_klines(self, symbol: str, interval: str, limit: int = KLINES_LIMIT) -> Optional[pd.DataFrame]:
        client = await self.get_client()
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            resp = await client.get(f"{BASE_URL}/fapi/v1/klines", params=params)
            if resp.status_code != 200:
                return None
            raw = resp.json()
            if not raw or len(raw) < 40:
                return None

            df = pd.DataFrame(raw, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close"])
            return df
        except Exception as e:
            logger.debug(f"Klines error {symbol} {interval}: {e}")
            return None

    async def analyze_symbol(self, symbol_info: Dict, semaphore: asyncio.Semaphore) -> Optional[Dict]:
        async with semaphore:
            symbol = symbol_info["symbol"]
            try:
                # Fetch both timeframes concurrently
                df_15m, df_1h = await asyncio.gather(
                    self.fetch_klines(symbol, "15m"),
                    self.fetch_klines(symbol, "1h"),
                )
                if df_15m is None or df_1h is None:
                    return None

                tf_15m = analyze_timeframe(df_15m)
                tf_1h = analyze_timeframe(df_1h)

                signal = generate_signal(
                    tf_15m, tf_1h, symbol,
                    price_change_24h=symbol_info.get("change_24h", 0.0)
                )
                return signal
            except Exception as e:
                logger.debug(f"Analyze error {symbol}: {e}")
                return None

    async def run_scan(self) -> List[Dict[str, Any]]:
        """Full scan cycle. Returns sorted signals (strongest first)."""
        async with self._lock:
            self.status = "scanning"
            start = datetime.now(timezone.utc)
            logger.info("Starting scan...")

            symbols = await self.get_liquid_symbols(min_volume_usdt=2_500_000, limit=260)
            self.symbols_scanned = len(symbols)
            logger.info(f"Scanning {len(symbols)} liquid pairs...")

            if not symbols:
                self.status = "error"
                self.signals = []
                return []

            semaphore = asyncio.Semaphore(MAX_CONCURRENT)
            tasks = [self.analyze_symbol(s, semaphore) for s in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            signals = []
            for r in results:
                if isinstance(r, dict) and r is not None:
                    signals.append(r)

            # Sort by score descending
            signals.sort(key=lambda x: x["score"], reverse=True)

            self.signals = signals
            self.last_scan = datetime.now(timezone.utc)
            self.scan_duration = (self.last_scan - start).total_seconds()
            self.status = "ok"

            logger.info(f"Scan done: {len(signals)} signals in {self.scan_duration:.1f}s")
            return signals

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "scan_duration_sec": round(self.scan_duration, 1),
            "symbols_scanned": self.symbols_scanned,
            "signals_count": len(self.signals),
            "server_time": datetime.now(timezone.utc).isoformat(),
        }
