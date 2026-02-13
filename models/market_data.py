"""
Data models for market data and collector system.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class Action(str, Enum):
    """Trading action types."""
    BUY = "BUY"
    SELL = "SELL"
    STOP_LOSS = "STOP_LOSS"
    HOLD = "HOLD"


class OHLC(BaseModel):
    """OHLC candle data."""
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0


class Indicators(BaseModel):
    """Technical indicators."""
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_20: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None


class TimeframeData(BaseModel):
    """Data for a single timeframe."""
    ohlc: List[OHLC]
    indicators: Indicators


class MarketState(BaseModel):
    """Complete market state across timeframes."""
    timeframes: Dict[str, TimeframeData]


class PositionInfo(BaseModel):
    """Information about a trading position."""
    ticket: int
    symbol: str
    volume: float
    price: float
    profit: float = 0
    sl: Optional[float] = None
    tp: Optional[float] = None
    type: str = "BUY"  # BUY or SELL


class CollectedData(BaseModel):
    """Single data point collected by the system."""
    timestamp: datetime
    screenshot_path: str
    action: Action
    thought: Optional[str] = None
    position_info: Optional[PositionInfo] = None
    market_state: Optional[MarketState] = None


class CollectorStatus(BaseModel):
    """Status of the data collector."""
    is_running: bool = False
    started_at: Optional[datetime] = None
    screenshots_count: int = 0
    actions_count: int = 0
    last_screenshot_at: Optional[datetime] = None
    last_action_at: Optional[datetime] = None


class ThoughtInput(BaseModel):
    """Input model for trader thought."""
    thought: str
    action: Action
    timestamp: Optional[datetime] = None
