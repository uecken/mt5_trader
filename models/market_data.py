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


# ===== Session Management Models =====

class SessionStatus(str, Enum):
    """Trading session status."""
    ACTIVE = "active"
    COMPLETED = "completed"


class HoldRecord(BaseModel):
    """Record of a HOLD action within a session."""
    time: datetime
    thought: str


class HorizontalLineData(BaseModel):
    """Data for a horizontal line from MT5."""
    name: str
    price: float
    color: str = "#FF0000"


class SessionEntry(BaseModel):
    """Entry point of a trading session."""
    time: datetime
    action: Action = Action.BUY
    price: float
    thought: str


class SessionExit(BaseModel):
    """Exit point of a trading session."""
    time: datetime
    action: Action  # SELL or STOP_LOSS
    price: float
    thought: str


class SessionResult(BaseModel):
    """Result of a completed trading session."""
    duration_minutes: int
    profit: float
    profit_pips: float


class SnapshotData(BaseModel):
    """Data for a single snapshot within a session."""
    timestamp: datetime
    action: Action
    thought: str
    screenshots: Dict[str, str]  # {"D1": "path/to/D1.png", ...}
    market_data_path: str
    horizontal_lines: Optional[List[HorizontalLineData]] = None


class TradingSession(BaseModel):
    """Complete trading session from BUY to SELL/STOP_LOSS."""
    session_id: str
    symbol: str = "XAUUSDp"
    status: SessionStatus = SessionStatus.ACTIVE

    entry: Optional[SessionEntry] = None
    exit: Optional[SessionExit] = None
    holds: List[HoldRecord] = Field(default_factory=list)

    result: Optional[SessionResult] = None
    snapshot_count: int = 0
    timeframes: List[str] = Field(default_factory=lambda: ["D1", "H4", "M15", "M5", "M1"])
