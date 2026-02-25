"""
Session manager module.
Manages trading sessions from BUY to SELL/STOP_LOSS.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from models.market_data import (
    Action, MarketState, PositionInfo, SessionStatus,
    SessionEntry, SessionExit, SessionResult, HoldRecord,
    TradingSession, SnapshotData, HorizontalLineData
)
from collector.horizontal_lines import get_horizontal_lines_reader

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages trading sessions.
    A session starts with BUY and ends with SELL or STOP_LOSS.
    """

    def __init__(
        self,
        sessions_dir: Path = Path("data/sessions"),
        symbol: str = "XAUUSDp"
    ):
        """
        Initialize the session manager.

        Args:
            sessions_dir: Directory to store session data
            symbol: Trading symbol
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.symbol = symbol

        self._active_session: Optional[TradingSession] = None
        self._active_session_dir: Optional[Path] = None

    def start_session(
        self,
        thought: str,
        price: float,
        market_state: Optional[MarketState],
        screenshots: Dict[str, str],
        position_info: Optional[PositionInfo] = None
    ) -> str:
        """
        Start a new trading session (on BUY action).

        Args:
            thought: Trader's reasoning for the entry
            price: Entry price
            market_state: Current market state
            screenshots: Dict of timeframe -> screenshot path
            position_info: Position information

        Returns:
            Session ID
        """
        if self._active_session is not None:
            logger.warning("Active session exists. Ending it before starting new one.")
            self.end_session(
                action=Action.SELL,
                thought="Session auto-closed due to new session start",
                price=price,
                market_state=market_state,
                screenshots=screenshots
            )

        timestamp = datetime.now(timezone.utc)
        session_id = timestamp.strftime("%Y%m%d_%H%M%S")

        # Create session directory structure
        session_dir = self.sessions_dir / f"session_{session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)
        self._active_session_dir = session_dir

        # Create session entry
        entry = SessionEntry(
            time=timestamp,
            action=Action.BUY,
            price=price,
            thought=thought
        )

        # Create session
        self._active_session = TradingSession(
            session_id=session_id,
            symbol=self.symbol,
            status=SessionStatus.ACTIVE,
            entry=entry,
            snapshot_count=1
        )

        # Save entry snapshot
        self._save_snapshot(
            timestamp=timestamp,
            action=Action.BUY,
            thought=thought,
            market_state=market_state,
            screenshots=screenshots
        )

        # Save session.json
        self._save_session()

        logger.info(f"Session started: {session_id}")
        return session_id

    def add_hold(
        self,
        thought: str,
        market_state: Optional[MarketState],
        screenshots: Dict[str, str]
    ) -> bool:
        """
        Add a HOLD action to the current session.

        Args:
            thought: Trader's reasoning for holding
            market_state: Current market state
            screenshots: Dict of timeframe -> screenshot path

        Returns:
            True if successful
        """
        if self._active_session is None:
            logger.warning("No active session. Cannot add HOLD.")
            return False

        timestamp = datetime.now(timezone.utc)

        # Add hold record
        hold_record = HoldRecord(time=timestamp, thought=thought)
        self._active_session.holds.append(hold_record)
        self._active_session.snapshot_count += 1

        # Save snapshot
        self._save_snapshot(
            timestamp=timestamp,
            action=Action.HOLD,
            thought=thought,
            market_state=market_state,
            screenshots=screenshots
        )

        # Update session.json
        self._save_session()

        logger.info(f"HOLD added to session: {self._active_session.session_id}")
        return True

    def end_session(
        self,
        action: Action,
        thought: str,
        price: float,
        market_state: Optional[MarketState],
        screenshots: Dict[str, str],
        position_info: Optional[PositionInfo] = None
    ) -> Optional[TradingSession]:
        """
        End the current session (on SELL or STOP_LOSS).

        Args:
            action: Exit action (SELL or STOP_LOSS)
            thought: Trader's reasoning for the exit
            price: Exit price
            market_state: Current market state
            screenshots: Dict of timeframe -> screenshot path
            position_info: Position information

        Returns:
            Completed session or None if no active session
        """
        if self._active_session is None:
            logger.warning("No active session to end.")
            return None

        timestamp = datetime.now(timezone.utc)

        # Create session exit
        exit_info = SessionExit(
            time=timestamp,
            action=action,
            price=price,
            thought=thought
        )
        self._active_session.exit = exit_info
        self._active_session.status = SessionStatus.COMPLETED
        self._active_session.snapshot_count += 1

        # Calculate result
        if self._active_session.entry:
            entry_time = self._active_session.entry.time
            duration_minutes = int((timestamp - entry_time).total_seconds() / 60)
            entry_price = self._active_session.entry.price
            profit = price - entry_price
            profit_pips = profit * 10  # Approximate for gold

            self._active_session.result = SessionResult(
                duration_minutes=duration_minutes,
                profit=round(profit, 2),
                profit_pips=round(profit_pips, 1)
            )

        # Save exit snapshot
        self._save_snapshot(
            timestamp=timestamp,
            action=action,
            thought=thought,
            market_state=market_state,
            screenshots=screenshots
        )

        # Save session.json
        self._save_session()

        completed_session = self._active_session
        logger.info(f"Session ended: {completed_session.session_id}")

        # Clear active session
        self._active_session = None
        self._active_session_dir = None

        return completed_session

    def _save_snapshot(
        self,
        timestamp: datetime,
        action: Action,
        thought: str,
        market_state: Optional[MarketState],
        screenshots: Dict[str, str]
    ):
        """Save a snapshot to the session directory."""
        if self._active_session_dir is None:
            return

        # Create snapshot directory
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        snapshot_dir = self._active_session_dir / "snapshots" / f"{timestamp_str}_{action.value}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        screenshots_dir = snapshot_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        # Save thought.json
        thought_data = {
            "timestamp": timestamp.isoformat(),
            "action": action.value,
            "thought": thought
        }
        with open(snapshot_dir / "thought.json", "w", encoding="utf-8") as f:
            json.dump(thought_data, f, ensure_ascii=False, indent=2)

        # Save market_data.json
        if market_state:
            market_data = self._market_state_to_dict(market_state, timestamp)
            with open(snapshot_dir / "market_data.json", "w", encoding="utf-8") as f:
                json.dump(market_data, f, ensure_ascii=False, indent=2)

        # Copy screenshots to snapshot directory
        import shutil
        for tf, src_path in screenshots.items():
            if src_path and Path(src_path).exists():
                dst_path = screenshots_dir / f"{tf}.png"
                shutil.copy2(src_path, dst_path)

        # Save horizontal_lines.json
        try:
            reader = get_horizontal_lines_reader()
            raw_data = reader.read_raw()
            if raw_data.get("lines"):
                with open(snapshot_dir / "horizontal_lines.json", "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, ensure_ascii=False, indent=2)
                logger.debug(f"Horizontal lines saved: {len(raw_data['lines'])} lines")
        except Exception as e:
            logger.warning(f"Failed to save horizontal lines: {e}")

        logger.debug(f"Snapshot saved: {snapshot_dir}")

    def _market_state_to_dict(self, market_state: MarketState, timestamp: datetime) -> Dict:
        """Convert MarketState to serializable dictionary."""
        result = {
            "timestamp": timestamp.isoformat(),
            "symbol": self.symbol,
            "timeframes": {}
        }

        for tf_name, tf_data in market_state.timeframes.items():
            result["timeframes"][tf_name] = {
                "ohlc": [
                    {
                        "time": ohlc.time.isoformat(),
                        "open": ohlc.open,
                        "high": ohlc.high,
                        "low": ohlc.low,
                        "close": ohlc.close,
                        "volume": ohlc.volume
                    }
                    for ohlc in tf_data.ohlc
                ],
                "indicators": {
                    "rsi": tf_data.indicators.rsi,
                    "macd": tf_data.indicators.macd,
                    "macd_signal": tf_data.indicators.macd_signal,
                    "macd_hist": tf_data.indicators.macd_hist,
                    "sma_20": tf_data.indicators.sma_20,
                    "sma_50": tf_data.indicators.sma_50,
                    "ema_20": tf_data.indicators.ema_20,
                    "bb_upper": tf_data.indicators.bb_upper,
                    "bb_middle": tf_data.indicators.bb_middle,
                    "bb_lower": tf_data.indicators.bb_lower
                }
            }

        return result

    def _save_session(self):
        """Save session.json to the session directory."""
        if self._active_session is None or self._active_session_dir is None:
            return

        session_data = {
            "session_id": self._active_session.session_id,
            "symbol": self._active_session.symbol,
            "status": self._active_session.status.value,
            "entry": None,
            "exit": None,
            "holds": [],
            "result": None,
            "snapshot_count": self._active_session.snapshot_count,
            "timeframes": self._active_session.timeframes
        }

        if self._active_session.entry:
            session_data["entry"] = {
                "time": self._active_session.entry.time.isoformat(),
                "action": self._active_session.entry.action.value,
                "price": self._active_session.entry.price,
                "thought": self._active_session.entry.thought
            }

        if self._active_session.exit:
            session_data["exit"] = {
                "time": self._active_session.exit.time.isoformat(),
                "action": self._active_session.exit.action.value,
                "price": self._active_session.exit.price,
                "thought": self._active_session.exit.thought
            }

        for hold in self._active_session.holds:
            session_data["holds"].append({
                "time": hold.time.isoformat(),
                "thought": hold.thought
            })

        if self._active_session.result:
            session_data["result"] = {
                "duration_minutes": self._active_session.result.duration_minutes,
                "profit": self._active_session.result.profit,
                "profit_pips": self._active_session.result.profit_pips
            }

        with open(self._active_session_dir / "session.json", "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

    def get_active_session(self) -> Optional[TradingSession]:
        """Get the current active session."""
        return self._active_session

    def has_active_session(self) -> bool:
        """Check if there is an active session."""
        return self._active_session is not None

    def get_session(self, session_id: str) -> Optional[TradingSession]:
        """
        Load a session from storage.

        Args:
            session_id: Session ID to load

        Returns:
            TradingSession or None if not found
        """
        session_dir = self.sessions_dir / f"session_{session_id}"
        session_file = session_dir / "session.json"

        if not session_file.exists():
            return None

        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self._dict_to_session(data)

    def list_sessions(self, limit: int = 10) -> List[TradingSession]:
        """
        List recent sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of TradingSession objects
        """
        sessions = []
        session_dirs = sorted(
            self.sessions_dir.glob("session_*"),
            key=lambda p: p.name,
            reverse=True
        )

        for session_dir in session_dirs[:limit]:
            session_file = session_dir / "session.json"
            if session_file.exists():
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append(self._dict_to_session(data))

        return sessions

    def _dict_to_session(self, data: Dict) -> TradingSession:
        """Convert dictionary to TradingSession."""
        session = TradingSession(
            session_id=data["session_id"],
            symbol=data["symbol"],
            status=SessionStatus(data["status"]),
            snapshot_count=data.get("snapshot_count", 0),
            timeframes=data.get("timeframes", ["D1", "H4", "M15", "M5", "M1"])
        )

        if data.get("entry"):
            session.entry = SessionEntry(
                time=datetime.fromisoformat(data["entry"]["time"]),
                action=Action(data["entry"]["action"]),
                price=data["entry"]["price"],
                thought=data["entry"]["thought"]
            )

        if data.get("exit"):
            session.exit = SessionExit(
                time=datetime.fromisoformat(data["exit"]["time"]),
                action=Action(data["exit"]["action"]),
                price=data["exit"]["price"],
                thought=data["exit"]["thought"]
            )

        for hold_data in data.get("holds", []):
            session.holds.append(HoldRecord(
                time=datetime.fromisoformat(hold_data["time"]),
                thought=hold_data["thought"]
            ))

        if data.get("result"):
            session.result = SessionResult(
                duration_minutes=data["result"]["duration_minutes"],
                profit=data["result"]["profit"],
                profit_pips=data["result"]["profit_pips"]
            )

        return session


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


if __name__ == "__main__":
    # Test the session manager
    logging.basicConfig(level=logging.INFO)

    manager = SessionManager()

    # Test start session
    session_id = manager.start_session(
        thought="Test entry - RSI oversold",
        price=2850.50,
        market_state=None,
        screenshots={}
    )
    print(f"Session started: {session_id}")

    # Test add hold
    manager.add_hold(
        thought="Still waiting for target",
        market_state=None,
        screenshots={}
    )
    print("HOLD added")

    # Test end session
    completed = manager.end_session(
        action=Action.SELL,
        thought="Target reached",
        price=2855.20,
        market_state=None,
        screenshots={}
    )
    print(f"Session ended: {completed}")
