"""
Screen capture module for MT5 window.
Captures screenshots at regular intervals.
Supports multi-timeframe captures with tab switching.
"""
import mss
import mss.tools
from PIL import Image
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, List
import logging
import ctypes
from ctypes import wintypes
import time

logger = logging.getLogger(__name__)

# Try to import pyautogui for tab switching
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("pyautogui not available. Multi-timeframe capture will be limited.")


# Windows API for finding windows
user32 = ctypes.windll.user32


def find_window_by_title(title: str) -> Optional[int]:
    """Find a window handle by its title (partial match)."""
    hwnd = user32.FindWindowW(None, None)
    while hwnd:
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            if title.lower() in buffer.value.lower():
                return hwnd
        hwnd = user32.GetWindow(hwnd, 2)  # GW_HWNDNEXT
    return None


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """Get the rectangle (left, top, right, bottom) of a window."""
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None


class ScreenCapture:
    """Screen capture utility for MT5 window."""

    def __init__(
        self,
        output_dir: Path,
        window_title: str = "MetaTrader 5",
        image_format: str = "png"
    ):
        """
        Initialize the screen capture.

        Args:
            output_dir: Directory to save screenshots
            window_title: Title of the MT5 window to capture
            image_format: Image format (png, jpg)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.window_title = window_title
        self.image_format = image_format
        self.sct = mss.mss()

    def find_mt5_window(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Find the MT5 window and return its coordinates.

        Returns:
            Tuple of (left, top, right, bottom) or None if not found
        """
        hwnd = find_window_by_title(self.window_title)
        if hwnd:
            rect = get_window_rect(hwnd)
            if rect:
                left, top, right, bottom = rect
                return {
                    "left": left,
                    "top": top,
                    "width": right - left,
                    "height": bottom - top
                }
        return None

    def capture_mt5(self) -> Optional[str]:
        """
        Capture the MT5 window and save to file.

        Returns:
            Path to the saved screenshot or None if failed
        """
        try:
            # Find MT5 window
            window_rect = self.find_mt5_window()

            if window_rect is None:
                logger.warning(f"MT5 window not found: {self.window_title}")
                # Fall back to full screen capture
                monitor = self.sct.monitors[1]  # Primary monitor
                window_rect = monitor

            # Generate filename with timestamp
            timestamp = datetime.now()
            filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}.{self.image_format}"
            filepath = self.output_dir / filename

            # Capture screenshot
            screenshot = self.sct.grab(window_rect)

            # Save using PIL for better format support
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save(str(filepath))

            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

    def capture_full_screen(self) -> Optional[str]:
        """
        Capture the full screen.

        Returns:
            Path to the saved screenshot or None if failed
        """
        try:
            timestamp = datetime.now()
            filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_full.{self.image_format}"
            filepath = self.output_dir / filename

            # Capture primary monitor
            monitor = self.sct.monitors[1]
            screenshot = self.sct.grab(monitor)

            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save(str(filepath))

            logger.info(f"Full screen saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to capture full screen: {e}")
            return None

    def cleanup(self):
        """Clean up resources."""
        self.sct.close()

    def capture_to_path(self, filepath: Path) -> bool:
        """
        Capture the MT5 window and save to specified path.

        Args:
            filepath: Path to save the screenshot

        Returns:
            True if successful
        """
        try:
            window_rect = self.find_mt5_window()
            if window_rect is None:
                monitor = self.sct.monitors[1]
                window_rect = monitor

            screenshot = self.sct.grab(window_rect)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save(str(filepath))

            logger.debug(f"Screenshot saved: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return False


class MultiTimeframeCapture:
    """
    Captures screenshots for multiple timeframes by switching MT5 tabs.
    """

    # Default timeframes to capture
    DEFAULT_TIMEFRAMES = ["D1", "H4", "M15", "M5", "M1"]

    # Tab positions for each timeframe (can be configured)
    # These are relative positions from left edge of MT5 window
    DEFAULT_TAB_POSITIONS = {
        "D1": 0,
        "H4": 1,
        "M15": 2,
        "M5": 3,
        "M1": 4
    }

    def __init__(
        self,
        output_dir: Path = Path("data/screenshots"),
        window_title: str = "MetaTrader 5",
        timeframes: List[str] = None,
        tab_switch_delay: float = 0.5,
        image_format: str = "png"
    ):
        """
        Initialize multi-timeframe capture.

        Args:
            output_dir: Directory to save screenshots
            window_title: MT5 window title
            timeframes: List of timeframes to capture
            tab_switch_delay: Delay after switching tabs (seconds)
            image_format: Image format
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.window_title = window_title
        self.timeframes = timeframes or self.DEFAULT_TIMEFRAMES
        self.tab_switch_delay = tab_switch_delay
        self.image_format = image_format

        self.screen_capture = ScreenCapture(
            output_dir=output_dir,
            window_title=window_title,
            image_format=image_format
        )

        # Tab click positions (y offset from top of window)
        self._tab_y_offset = 30  # Typical tab bar height
        self._tab_width = 100    # Approximate tab width
        self._tab_start_x = 10   # Start X position of tabs

        # Configured tab positions (timeframe -> (x, y) relative to window)
        self._tab_positions: Dict[str, Tuple[int, int]] = {}

    def configure_tab_positions(self, positions: Dict[str, Tuple[int, int]]):
        """
        Configure tab positions for each timeframe.

        Args:
            positions: Dict of timeframe -> (x, y) position relative to window
        """
        self._tab_positions = positions

    def _click_tab(self, timeframe: str, window_rect: Dict) -> bool:
        """
        Click on a tab for the specified timeframe.

        Args:
            timeframe: Timeframe to switch to
            window_rect: Window rectangle

        Returns:
            True if successful
        """
        if not PYAUTOGUI_AVAILABLE:
            logger.warning("pyautogui not available. Cannot switch tabs.")
            return False

        try:
            # Get tab position
            if timeframe in self._tab_positions:
                rel_x, rel_y = self._tab_positions[timeframe]
            else:
                # Calculate default position based on timeframe index
                idx = self.DEFAULT_TAB_POSITIONS.get(timeframe, 0)
                rel_x = self._tab_start_x + (idx * self._tab_width) + (self._tab_width // 2)
                rel_y = self._tab_y_offset

            # Calculate absolute position
            abs_x = window_rect["left"] + rel_x
            abs_y = window_rect["top"] + rel_y

            # Click on the tab
            pyautogui.click(abs_x, abs_y)
            logger.debug(f"Clicked tab for {timeframe} at ({abs_x}, {abs_y})")

            return True

        except Exception as e:
            logger.error(f"Failed to click tab for {timeframe}: {e}")
            return False

    def capture_all_timeframes(self, output_dir: Path = None) -> Dict[str, str]:
        """
        Capture screenshots for all configured timeframes.

        Args:
            output_dir: Directory to save screenshots (optional override)

        Returns:
            Dict of timeframe -> screenshot path
        """
        results = {}
        save_dir = output_dir or self.output_dir

        # Find MT5 window
        window_rect = self.screen_capture.find_mt5_window()
        if window_rect is None:
            logger.error("MT5 window not found. Cannot capture timeframes.")
            # Fall back to single capture
            path = self.screen_capture.capture_mt5()
            if path:
                for tf in self.timeframes:
                    results[tf] = path
            return results

        for timeframe in self.timeframes:
            try:
                # Switch to the timeframe tab
                if PYAUTOGUI_AVAILABLE:
                    self._click_tab(timeframe, window_rect)
                    time.sleep(self.tab_switch_delay)

                # Capture screenshot
                filepath = save_dir / f"{timeframe}.{self.image_format}"
                if self.screen_capture.capture_to_path(filepath):
                    results[timeframe] = str(filepath)
                    logger.info(f"Captured {timeframe}: {filepath}")
                else:
                    logger.warning(f"Failed to capture {timeframe}")

            except Exception as e:
                logger.error(f"Error capturing {timeframe}: {e}")

        return results

    def capture_single_timeframe(self, timeframe: str, output_dir: Path = None) -> Optional[str]:
        """
        Capture screenshot for a single timeframe.

        Args:
            timeframe: Timeframe to capture
            output_dir: Directory to save screenshot

        Returns:
            Path to screenshot or None
        """
        save_dir = output_dir or self.output_dir

        window_rect = self.screen_capture.find_mt5_window()
        if window_rect and PYAUTOGUI_AVAILABLE:
            self._click_tab(timeframe, window_rect)
            time.sleep(self.tab_switch_delay)

        filepath = save_dir / f"{timeframe}.{self.image_format}"
        if self.screen_capture.capture_to_path(filepath):
            return str(filepath)
        return None

    def cleanup(self):
        """Clean up resources."""
        self.screen_capture.cleanup()


# Global multi-timeframe capture instance
_mtf_capture: Optional[MultiTimeframeCapture] = None


def get_mtf_capture() -> MultiTimeframeCapture:
    """Get or create the global multi-timeframe capture instance."""
    global _mtf_capture
    if _mtf_capture is None:
        _mtf_capture = MultiTimeframeCapture()
    return _mtf_capture


if __name__ == "__main__":
    # Test the screen capture
    logging.basicConfig(level=logging.INFO)

    capture = ScreenCapture(
        output_dir=Path("data/screenshots"),
        window_title="MetaTrader 5"
    )

    # Test capture
    result = capture.capture_mt5()
    if result:
        print(f"Screenshot saved to: {result}")
    else:
        print("Failed to capture screenshot")

    capture.cleanup()
