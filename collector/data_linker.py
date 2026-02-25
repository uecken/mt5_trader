"""
Data linker module.
Links screenshots, market data, actions, and thoughts into unified training data.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path
import json
import logging

from models.market_data import (
    Action, PositionInfo, MarketState, CollectedData,
    OHLC, Indicators, TimeframeData
)

logger = logging.getLogger(__name__)


class DataLinker:
    """Links and stores collected trading data."""

    def __init__(
        self,
        training_dir: Path,
        actions_dir: Path
    ):
        """
        Initialize the data linker.

        Args:
            training_dir: Directory for unified training data
            actions_dir: Directory for action logs
        """
        self.training_dir = Path(training_dir)
        self.training_dir.mkdir(parents=True, exist_ok=True)
        self.actions_dir = Path(actions_dir)
        self.actions_dir.mkdir(parents=True, exist_ok=True)

        self._data_points: List[CollectedData] = []
        self._action_log: List[Dict] = []

    def link_data(
        self,
        timestamp: datetime,
        screenshot_path: str,
        action: Action,
        thought: Optional[str] = None,
        position_info: Optional[PositionInfo] = None,
        market_state: Optional[MarketState] = None
    ) -> CollectedData:
        """
        Link all collected data into a single training data point.

        Args:
            timestamp: When this data was collected
            screenshot_path: Path to the screenshot file
            action: Trading action (BUY, SELL, STOP_LOSS, HOLD)
            thought: Trader's reasoning
            position_info: Position information if applicable
            market_state: Market state with OHLC and indicators

        Returns:
            CollectedData object
        """
        data = CollectedData(
            timestamp=timestamp,
            screenshot_path=screenshot_path,
            action=action,
            thought=thought,
            position_info=position_info,
            market_state=market_state
        )

        self._data_points.append(data)
        self._save_data_point(data)

        logger.info(f"Data linked: {timestamp.isoformat()} - {action.value}")

        return data

    def log_action(
        self,
        timestamp: datetime,
        action: Action,
        position_info: Optional[PositionInfo] = None,
        screenshot_path: Optional[str] = None
    ):
        """
        Log an action to the action log.

        Args:
            timestamp: When the action occurred
            action: Trading action
            position_info: Position information
            screenshot_path: Associated screenshot path
        """
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "action": action.value,
            "screenshot_path": screenshot_path
        }

        if position_info:
            log_entry["position"] = {
                "ticket": position_info.ticket,
                "symbol": position_info.symbol,
                "volume": position_info.volume,
                "price": position_info.price,
                "profit": position_info.profit,
                "type": position_info.type
            }

        self._action_log.append(log_entry)
        self._save_action_log(log_entry, timestamp)

    def _save_data_point(self, data: CollectedData):
        """Save a data point to the training directory."""
        timestamp_str = data.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp_str}_{data.action.value}.json"
        filepath = self.training_dir / filename

        # Convert to serializable dict
        data_dict = {
            "timestamp": data.timestamp.isoformat(),
            "screenshot_path": data.screenshot_path,
            "action": data.action.value,
            "thought": data.thought
        }

        if data.position_info:
            data_dict["position_info"] = {
                "ticket": data.position_info.ticket,
                "symbol": data.position_info.symbol,
                "volume": data.position_info.volume,
                "price": data.position_info.price,
                "profit": data.position_info.profit,
                "sl": data.position_info.sl,
                "tp": data.position_info.tp,
                "type": data.position_info.type
            }

        if data.market_state:
            data_dict["market_state"] = self._market_state_to_dict(data.market_state)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)

        logger.debug(f"Data point saved: {filepath}")

    def _market_state_to_dict(self, market_state: MarketState) -> Dict:
        """Convert MarketState to serializable dictionary."""
        result = {"timeframes": {}}

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
                    for ohlc in tf_data.ohlc[-10:]  # Only save last 10 candles
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

    def _save_action_log(self, log_entry: Dict, timestamp: datetime):
        """Save action log entry."""
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp_str}_action.json"
        filepath = self.actions_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(log_entry, f, ensure_ascii=False, indent=2)

    def get_recent_data(self, limit: int = 10) -> List[CollectedData]:
        """
        Get recent collected data points.

        Args:
            limit: Maximum number of data points to return

        Returns:
            List of CollectedData objects
        """
        return self._data_points[-limit:]

    def get_action_history(self, limit: int = 50) -> List[Dict]:
        """
        Get action history.

        Args:
            limit: Maximum number of actions to return

        Returns:
            List of action log entries
        """
        return self._action_log[-limit:]

    def load_from_storage(self) -> int:
        """
        Load existing data from storage.

        Returns:
            Number of data points loaded
        """
        count = 0
        for filepath in sorted(self.training_dir.glob("*.json")):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data_dict = json.load(f)

                data = CollectedData(
                    timestamp=datetime.fromisoformat(data_dict["timestamp"]),
                    screenshot_path=data_dict["screenshot_path"],
                    action=Action(data_dict["action"]),
                    thought=data_dict.get("thought")
                )
                self._data_points.append(data)
                count += 1
            except Exception as e:
                logger.error(f"Error loading {filepath}: {e}")

        logger.info(f"Loaded {count} data points from storage")
        return count

    def get_statistics(self) -> Dict:
        """
        Get statistics about collected data.

        Returns:
            Dictionary with statistics
        """
        action_counts = {action.value: 0 for action in Action}
        for data in self._data_points:
            action_counts[data.action.value] += 1

        thoughts_count = sum(1 for d in self._data_points if d.thought)

        return {
            "total_data_points": len(self._data_points),
            "action_counts": action_counts,
            "thoughts_count": thoughts_count,
            "thoughts_percentage": thoughts_count / len(self._data_points) * 100 if self._data_points else 0
        }


if __name__ == "__main__":
    # Test the data linker
    logging.basicConfig(level=logging.INFO)

    linker = DataLinker(
        training_dir=Path("data/training"),
        actions_dir=Path("data/actions")
    )

    # Test linking data
    data = linker.link_data(
        timestamp=datetime.now(timezone.utc),
        screenshot_path="data/screenshots/test.png",
        action=Action.BUY,
        thought="Test thought - RSI oversold"
    )

    print(f"Data linked: {data}")
    print(f"Statistics: {linker.get_statistics()}")
