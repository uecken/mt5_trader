"""
Collector service module.
Main service that orchestrates screen capture, position monitoring, and data collection.
"""
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import logging
import time

from collector.screen_capture import ScreenCapture
from collector.market_data_collector import MarketDataCollector
from collector.position_monitor import PositionMonitor
from collector.thought_input import ThoughtManager
from collector.data_linker import DataLinker
from models.market_data import Action, PositionInfo, CollectorStatus, MarketState

logger = logging.getLogger(__name__)


class CollectorService:
    """
    Main data collection service.
    Coordinates screenshot capture, position monitoring, and data linking.
    """

    def __init__(
        self,
        symbol: str = "XAUUSD",
        screenshot_interval: int = 30,
        screenshots_dir: Path = Path("data/screenshots"),
        actions_dir: Path = Path("data/actions"),
        thoughts_dir: Path = Path("data/thoughts"),
        training_dir: Path = Path("data/training"),
        mt5_window_title: str = "MetaTrader 5",
        on_action_callback: Optional[Callable[[Action, Optional[PositionInfo]], None]] = None
    ):
        """
        Initialize the collector service.

        Args:
            symbol: Trading symbol to monitor
            screenshot_interval: Interval between screenshots (seconds)
            screenshots_dir: Directory to save screenshots
            actions_dir: Directory to save action logs
            thoughts_dir: Directory to save thoughts
            training_dir: Directory for training data
            mt5_window_title: Title of MT5 window
            on_action_callback: External callback for action notifications
        """
        self.symbol = symbol
        self.screenshot_interval = screenshot_interval

        # Initialize components
        self.screen_capture = ScreenCapture(
            output_dir=screenshots_dir,
            window_title=mt5_window_title
        )

        self.market_data_collector = MarketDataCollector(symbol=symbol)

        self.thought_manager = ThoughtManager(
            storage_dir=thoughts_dir,
            on_thought_received=self._on_thought_received
        )

        self.data_linker = DataLinker(
            training_dir=training_dir,
            actions_dir=actions_dir
        )

        self.position_monitor = PositionMonitor(
            symbol=symbol,
            poll_interval=1.0,
            on_action_callback=self._on_action_detected
        )

        self._external_action_callback = on_action_callback

        # State
        self._running = False
        self._screenshot_thread: Optional[threading.Thread] = None
        self._status = CollectorStatus()
        self._last_screenshot_path: Optional[str] = None
        self._last_market_state: Optional[MarketState] = None

    def _on_action_detected(self, action: Action, position_info: Optional[PositionInfo]):
        """Handle detected trading action."""
        timestamp = datetime.now()
        logger.info(f"Action detected: {action.value}")

        # Get current screenshot and market data
        screenshot_path = self._last_screenshot_path
        market_state = self._last_market_state

        # Log the action
        self.data_linker.log_action(
            timestamp=timestamp,
            action=action,
            position_info=position_info,
            screenshot_path=screenshot_path
        )

        # Add to pending for thought input (for non-HOLD actions)
        if action != Action.HOLD:
            self.thought_manager.add_pending_action(action, timestamp)
            self._status.actions_count += 1
            self._status.last_action_at = timestamp

            # Notify external callback
            if self._external_action_callback:
                self._external_action_callback(action, position_info)

    def _on_thought_received(self, thought_input):
        """Handle received thought input."""
        logger.info(f"Thought received for {thought_input.action.value}")

        # Link the data
        timestamp = thought_input.timestamp or datetime.now()
        self.data_linker.link_data(
            timestamp=timestamp,
            screenshot_path=self._last_screenshot_path or "",
            action=thought_input.action,
            thought=thought_input.thought,
            market_state=self._last_market_state
        )

    def _screenshot_loop(self):
        """Main screenshot capture loop."""
        logger.info("Screenshot capture loop started")

        while self._running:
            try:
                # Capture screenshot
                screenshot_path = self.screen_capture.capture_mt5()
                if screenshot_path:
                    self._last_screenshot_path = screenshot_path
                    self._status.screenshots_count += 1
                    self._status.last_screenshot_at = datetime.now()

                # Collect market data
                market_state = self.market_data_collector.collect_all_timeframes()
                if market_state:
                    self._last_market_state = market_state

                # For HOLD actions, also save the data periodically
                last_action, _ = self.position_monitor.get_last_action()
                if last_action == Action.HOLD and screenshot_path:
                    self.data_linker.link_data(
                        timestamp=datetime.now(),
                        screenshot_path=screenshot_path,
                        action=Action.HOLD,
                        market_state=market_state
                    )

            except Exception as e:
                logger.error(f"Error in screenshot loop: {e}")

            # Wait for next interval
            time.sleep(self.screenshot_interval)

        logger.info("Screenshot capture loop stopped")

    def start(self) -> bool:
        """
        Start the collector service.

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Collector service already running")
            return True

        logger.info("Starting collector service...")

        # Start position monitor
        if not self.position_monitor.start():
            logger.error("Failed to start position monitor")
            return False

        # Start screenshot capture loop
        self._running = True
        self._screenshot_thread = threading.Thread(
            target=self._screenshot_loop,
            daemon=True
        )
        self._screenshot_thread.start()

        # Update status
        self._status.is_running = True
        self._status.started_at = datetime.now()

        logger.info("Collector service started successfully")
        return True

    def stop(self):
        """Stop the collector service."""
        logger.info("Stopping collector service...")

        self._running = False

        # Stop position monitor
        self.position_monitor.stop()

        # Wait for screenshot thread
        if self._screenshot_thread:
            self._screenshot_thread.join(timeout=5.0)
            self._screenshot_thread = None

        # Cleanup
        self.screen_capture.cleanup()

        # Update status
        self._status.is_running = False

        logger.info("Collector service stopped")

    def get_status(self) -> CollectorStatus:
        """
        Get current service status.

        Returns:
            CollectorStatus object
        """
        return self._status

    def get_pending_actions(self):
        """Get pending actions waiting for thought input."""
        return self.thought_manager.get_pending_actions()

    def submit_thought(self, thought: str, action: Action):
        """
        Submit a thought for an action.

        Args:
            thought: Trader's reasoning
            action: The action this thought is for
        """
        return self.thought_manager.submit_thought(thought, action)

    def get_statistics(self):
        """Get collection statistics."""
        return {
            **self._status.model_dump(),
            **self.data_linker.get_statistics()
        }

    def get_recent_data(self, limit: int = 10):
        """Get recent collected data."""
        return self.data_linker.get_recent_data(limit)

    @property
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running


# Global service instance
_collector_service: Optional[CollectorService] = None


def get_collector_service() -> CollectorService:
    """Get or create the global collector service instance."""
    global _collector_service
    if _collector_service is None:
        _collector_service = CollectorService()
    return _collector_service


if __name__ == "__main__":
    # Test the collector service
    logging.basicConfig(level=logging.INFO)

    def on_action(action: Action, position: Optional[PositionInfo]):
        print(f"\n>>> ACTION: {action.value}")
        if position:
            print(f"    Position: {position.ticket}")

    service = CollectorService(
        symbol="XAUUSD",
        screenshot_interval=30,
        on_action_callback=on_action
    )

    print("Starting collector service (press Ctrl+C to stop)...")
    if service.start():
        try:
            while True:
                time.sleep(10)
                status = service.get_status()
                print(f"\nStatus: screenshots={status.screenshots_count}, actions={status.actions_count}")
        except KeyboardInterrupt:
            print("\nStopping...")
            service.stop()
    else:
        print("Failed to start collector service")
