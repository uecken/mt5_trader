"""
Market data collector module.
Collects OHLC data from multiple timeframes and calculates technical indicators.
"""
import MetaTrader5 as mt5
import pandas as pd
import ta
from datetime import datetime
from typing import Dict, Optional, List
import logging

from models.market_data import OHLC, Indicators, TimeframeData, MarketState

logger = logging.getLogger(__name__)


# Timeframe mapping
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

# Default candle counts per timeframe
# D1, H4: 1 month of data
# M15, M5, M1: 100 candles
DEFAULT_CANDLE_COUNTS = {
    "D1": 30,     # 1 month
    "H4": 180,    # 1 month (6 candles/day * 30 days)
    "M15": 100,   # ~1 day
    "M5": 100,    # ~8 hours
    "M1": 100,    # ~1.5 hours
}


class MarketDataCollector:
    """Collects market data from MT5 across multiple timeframes."""

    def __init__(
        self,
        symbol: str = "XAUUSD",
        timeframes: List[str] = None,
        candle_counts: Dict[str, int] = None
    ):
        """
        Initialize the market data collector.

        Args:
            symbol: Trading symbol to collect data for
            timeframes: List of timeframes to collect
            candle_counts: Number of candles per timeframe
        """
        self.symbol = symbol
        self.timeframes = timeframes or ["D1", "H4", "M15", "M5", "M1"]
        self.candle_counts = candle_counts or DEFAULT_CANDLE_COUNTS
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize MT5 connection."""
        if self._initialized:
            return True

        if not mt5.initialize():
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False

        self._initialized = True
        return True

    def shutdown(self):
        """Shutdown MT5 connection."""
        if self._initialized:
            mt5.shutdown()
            self._initialized = False

    def _get_ohlc_data(self, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get OHLC data for a single timeframe.

        Args:
            timeframe: Timeframe string (M1, M5, M15, H1, H4, D1, etc.)

        Returns:
            DataFrame with OHLC data
        """
        tf = TIMEFRAME_MAP.get(timeframe.upper())
        if tf is None:
            logger.warning(f"Unknown timeframe: {timeframe}")
            return None

        count = self.candle_counts.get(timeframe, 100)
        rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, count)

        if rates is None or len(rates) == 0:
            logger.warning(f"Failed to get data: {self.symbol} {timeframe}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
        df = df.rename(columns={'tick_volume': 'volume'})

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> Indicators:
        """
        Calculate technical indicators for the given OHLC data.

        Args:
            df: DataFrame with OHLC data

        Returns:
            Indicators object with calculated values
        """
        if df is None or len(df) < 20:
            return Indicators()

        try:
            close = df['close']
            high = df['high']
            low = df['low']

            # RSI
            rsi = ta.momentum.RSIIndicator(close, window=14)
            rsi_value = rsi.rsi().iloc[-1] if len(rsi.rsi()) > 0 else None

            # MACD
            macd = ta.trend.MACD(close)
            macd_value = macd.macd().iloc[-1] if len(macd.macd()) > 0 else None
            macd_signal_value = macd.macd_signal().iloc[-1] if len(macd.macd_signal()) > 0 else None
            macd_hist_value = macd.macd_diff().iloc[-1] if len(macd.macd_diff()) > 0 else None

            # SMAs
            sma_20 = ta.trend.SMAIndicator(close, window=20).sma_indicator().iloc[-1] if len(close) >= 20 else None
            sma_50 = ta.trend.SMAIndicator(close, window=50).sma_indicator().iloc[-1] if len(close) >= 50 else None

            # EMA
            ema_20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1] if len(close) >= 20 else None

            # Bollinger Bands
            bb = ta.volatility.BollingerBands(close, window=20)
            bb_upper = bb.bollinger_hband().iloc[-1] if len(bb.bollinger_hband()) > 0 else None
            bb_middle = bb.bollinger_mavg().iloc[-1] if len(bb.bollinger_mavg()) > 0 else None
            bb_lower = bb.bollinger_lband().iloc[-1] if len(bb.bollinger_lband()) > 0 else None

            return Indicators(
                rsi=float(rsi_value) if rsi_value is not None and not pd.isna(rsi_value) else None,
                macd=float(macd_value) if macd_value is not None and not pd.isna(macd_value) else None,
                macd_signal=float(macd_signal_value) if macd_signal_value is not None and not pd.isna(macd_signal_value) else None,
                macd_hist=float(macd_hist_value) if macd_hist_value is not None and not pd.isna(macd_hist_value) else None,
                sma_20=float(sma_20) if sma_20 is not None and not pd.isna(sma_20) else None,
                sma_50=float(sma_50) if sma_50 is not None and not pd.isna(sma_50) else None,
                ema_20=float(ema_20) if ema_20 is not None and not pd.isna(ema_20) else None,
                bb_upper=float(bb_upper) if bb_upper is not None and not pd.isna(bb_upper) else None,
                bb_middle=float(bb_middle) if bb_middle is not None and not pd.isna(bb_middle) else None,
                bb_lower=float(bb_lower) if bb_lower is not None and not pd.isna(bb_lower) else None,
            )
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return Indicators()

    def _df_to_ohlc_list(self, df: pd.DataFrame) -> List[OHLC]:
        """Convert DataFrame to list of OHLC objects."""
        if df is None:
            return []

        return [
            OHLC(
                time=row['time'],
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume'])
            )
            for _, row in df.iterrows()
        ]

    def collect_all_timeframes(self) -> Optional[MarketState]:
        """
        Collect data from all configured timeframes.

        Returns:
            MarketState object with all timeframe data
        """
        if not self.initialize():
            return None

        try:
            timeframes_data = {}

            for tf in self.timeframes:
                df = self._get_ohlc_data(tf)
                if df is not None:
                    ohlc_list = self._df_to_ohlc_list(df)
                    indicators = self._calculate_indicators(df)
                    timeframes_data[tf] = TimeframeData(
                        ohlc=ohlc_list,
                        indicators=indicators
                    )
                else:
                    logger.warning(f"Skipping timeframe {tf} due to data fetch failure")

            if not timeframes_data:
                logger.error("Failed to collect any timeframe data")
                return None

            return MarketState(timeframes=timeframes_data)

        except Exception as e:
            logger.error(f"Error collecting market data: {e}")
            return None

        finally:
            self.shutdown()

    def collect_single_timeframe(self, timeframe: str) -> Optional[TimeframeData]:
        """
        Collect data for a single timeframe.

        Args:
            timeframe: Timeframe string

        Returns:
            TimeframeData object
        """
        if not self.initialize():
            return None

        try:
            df = self._get_ohlc_data(timeframe)
            if df is None:
                return None

            ohlc_list = self._df_to_ohlc_list(df)
            indicators = self._calculate_indicators(df)

            return TimeframeData(ohlc=ohlc_list, indicators=indicators)

        finally:
            self.shutdown()


if __name__ == "__main__":
    # Test the market data collector
    logging.basicConfig(level=logging.INFO)

    collector = MarketDataCollector(symbol="XAUUSD")
    market_state = collector.collect_all_timeframes()

    if market_state:
        for tf, data in market_state.timeframes.items():
            print(f"\n{tf}:")
            print(f"  Candles: {len(data.ohlc)}")
            print(f"  RSI: {data.indicators.rsi}")
            print(f"  MACD: {data.indicators.macd}")
    else:
        print("Failed to collect market data")
