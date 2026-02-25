"""
Position monitor module.
Monitors MT5 positions and detects trading actions (BUY, SELL, STOP_LOSS, HOLD).
"""
import MetaTrader5 as mt5
from datetime import datetime
from typing import Dict, List, Optional, Callable
import logging
import time
import threading

from models.market_data import Action, PositionInfo

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitors MT5 positions and detects trading actions."""

    def __init__(
        self,
        symbol: str = "XAUUSDp",
        poll_interval: float = 1.0,
        on_action_callback: Optional[Callable[[Action, Optional[PositionInfo]], None]] = None
    ):
        """
        Initialize the position monitor.

        Args:
            symbol: Trading symbol to monitor
            poll_interval: Interval between position checks (seconds)
            on_action_callback: Callback function when action is detected
        """
        self.symbol = symbol
        self.poll_interval = poll_interval
        self.on_action_callback = on_action_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._previous_positions: Dict[int, PositionInfo] = {}
        self._initialized = False
        self._last_action: Optional[Action] = None
        self._last_position_info: Optional[PositionInfo] = None

    def _initialize_mt5(self) -> bool:
        """Initialize MT5 connection."""
        if self._initialized:
            return True

        if not mt5.initialize():
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False

        self._initialized = True
        return True

    def _shutdown_mt5(self):
        """Shutdown MT5 connection."""
        if self._initialized:
            mt5.shutdown()
            self._initialized = False

    def _get_current_positions(self) -> Dict[int, PositionInfo]:
        """
        Get current open positions for the symbol.

        Returns:
            Dictionary mapping ticket to PositionInfo
        """
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return {}

        result = {}
        for pos in positions:
            result[pos.ticket] = PositionInfo(
                ticket=pos.ticket,
                symbol=pos.symbol,
                volume=pos.volume,
                price=pos.price_open,
                profit=pos.profit,
                sl=pos.sl if pos.sl > 0 else None,
                tp=pos.tp if pos.tp > 0 else None,
                type="BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
            )

        return result

    def _detect_action(
        self,
        previous: Dict[int, PositionInfo],
        current: Dict[int, PositionInfo]
    ) -> tuple[Action, Optional[PositionInfo]]:
        """
        Detect trading action by comparing previous and current positions.

        Args:
            previous: Previous positions
            current: Current positions

        Returns:
            Tuple of (Action, PositionInfo or None)
        """
        previous_tickets = set(previous.keys())
        current_tickets = set(current.keys())

        # New position opened (BUY)
        new_tickets = current_tickets - previous_tickets
        if new_tickets:
            ticket = list(new_tickets)[0]
            position = current[ticket]
            logger.info(f"New position detected: {ticket} ({position.type})")
            return Action.BUY, position

        # Position closed
        closed_tickets = previous_tickets - current_tickets
        if closed_tickets:
            ticket = list(closed_tickets)[0]
            position = previous[ticket]

            # Determine if it was a profit or loss
            if position.profit >= 0:
                logger.info(f"Position closed with profit: {ticket} (profit: {position.profit})")
                return Action.SELL, position
            else:
                logger.info(f"Position closed with loss (stop loss): {ticket} (loss: {position.profit})")
                return Action.STOP_LOSS, position

        # No change
        return Action.HOLD, None

    def _poll_loop(self):
        """Main polling loop."""
        logger.info("Position monitor started")

        while self._running:
            try:
                current_positions = self._get_current_positions()
                action, position_info = self._detect_action(
                    self._previous_positions,
                    current_positions
                )

                self._last_action = action
                self._last_position_info = position_info

                # Trigger callback for non-HOLD actions
                if action != Action.HOLD and self.on_action_callback:
                    self.on_action_callback(action, position_info)

                self._previous_positions = current_positions

            except Exception as e:
                logger.error(f"Error in position monitoring: {e}")

            time.sleep(self.poll_interval)

        logger.info("Position monitor stopped")

    def start(self) -> bool:
        """
        Start the position monitor.

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Position monitor already running")
            return True

        if not self._initialize_mt5():
            return False

        # Get initial positions
        self._previous_positions = self._get_current_positions()
        logger.info(f"Initial positions: {len(self._previous_positions)}")

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

        return True

    def stop(self):
        """Stop the position monitor."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._shutdown_mt5()

    def get_last_action(self) -> tuple[Action, Optional[PositionInfo]]:
        """
        Get the last detected action.

        Returns:
            Tuple of (Action, PositionInfo or None)
        """
        return self._last_action or Action.HOLD, self._last_position_info

    def get_current_positions(self) -> List[PositionInfo]:
        """
        Get list of current positions.

        Returns:
            List of PositionInfo objects
        """
        if not self._initialize_mt5():
            return []

        try:
            positions = self._get_current_positions()
            return list(positions.values())
        finally:
            if not self._running:
                self._shutdown_mt5()

    @property
    def is_running(self) -> bool:
        """Check if the monitor is running."""
        return self._running


if __name__ == "__main__":
    # Test the position monitor
    logging.basicConfig(level=logging.INFO)

    def on_action(action: Action, position: Optional[PositionInfo]):
        print(f"Action detected: {action.value}")
        if position:
            print(f"  Position: {position.ticket} {position.type} {position.volume} @ {position.price}")

    monitor = PositionMonitor(
        symbol="XAUUSDp",
        poll_interval=1.0,
        on_action_callback=on_action
    )

    print("Starting position monitor (press Ctrl+C to stop)...")
    if monitor.start():
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
            monitor.stop()
    else:
        print("Failed to start position monitor")
