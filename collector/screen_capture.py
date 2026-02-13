"""
Screen capture module for MT5 window.
Captures screenshots at regular intervals.
"""
import mss
import mss.tools
from PIL import Image
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import logging
import ctypes
from ctypes import wintypes

logger = logging.getLogger(__name__)


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
