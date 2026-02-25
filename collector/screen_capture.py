"""
Screen capture module for MT5 window.
Captures screenshots at regular intervals.
Supports multi-timeframe captures with tab switching.
"""
import mss
import mss.tools
from PIL import Image
from datetime import datetime, timezone
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

    def capture_mt5(self, allow_fullscreen_fallback: bool = False) -> Optional[str]:
        """
        Capture the MT5 window and save to file.

        Args:
            allow_fullscreen_fallback: If False, return None when MT5 not found

        Returns:
            Path to the saved screenshot or None if failed
        """
        try:
            # Find MT5 window
            window_rect = self.find_mt5_window()

            if window_rect is None:
                if allow_fullscreen_fallback:
                    logger.warning(f"MT5 window not found: {self.window_title}, falling back to full screen")
                    monitor = self.sct.monitors[1]  # Primary monitor
                    window_rect = monitor
                else:
                    logger.error(f"MT5 window not found: {self.window_title}")
                    return None

            # Generate filename with timestamp
            timestamp = datetime.now(timezone.utc)
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
            timestamp = datetime.now(timezone.utc)
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

    def capture_to_path(self, filepath: Path, allow_fullscreen_fallback: bool = False) -> bool:
        """
        Capture the MT5 window and save to specified path.

        Args:
            filepath: Path to save the screenshot
            allow_fullscreen_fallback: If False, return error when MT5 not found

        Returns:
            True if successful
        """
        try:
            window_rect = self.find_mt5_window()
            if window_rect is None:
                if allow_fullscreen_fallback:
                    logger.warning(f"MT5 window not found, falling back to full screen")
                    monitor = self.sct.monitors[1]
                    window_rect = monitor
                else:
                    logger.error(f"MT5 window not found: {self.window_title}")
                    return False

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


class MQL5ScreenCapture:
    """
    MQL5 ChartScreenShot() based screenshot capture.
    Communicates with ChartExporter.mq5 indicator via files.
    Captures all timeframes (D1, H4, M15, M5, M1) automatically.
    """

    DEFAULT_TIMEFRAMES = ["D1", "H4", "M15", "M5", "M1"]

    def __init__(
        self,
        output_dir: Path = Path("data/screenshots"),
        timeout: float = 30.0  # Increased for multi-timeframe capture
    ):
        """
        Initialize MQL5 screen capture.

        Args:
            output_dir: Directory to save screenshots
            timeout: Timeout waiting for MQL5 to complete (seconds)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

        # MT5 Common Files path
        import os
        appdata = os.environ.get("APPDATA", "")
        self.mt5_common_path = Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files"

    def request_screenshot(self, symbol: str = "") -> bool:
        """
        Send screenshot request to MQL5 ChartExporter.

        Args:
            symbol: Symbol name (optional, for filename)

        Returns:
            True if request file was created successfully
        """
        request_file = self.mt5_common_path / "screenshot_request.txt"
        try:
            content = f"symbol={symbol}\ntimestamp={datetime.now(timezone.utc).isoformat()}"
            with open(request_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Screenshot request created: {request_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to create request file: {e}")
            return False

    def wait_for_completion(self) -> Optional[dict]:
        """
        Wait for MQL5 to complete the screenshot.

        Returns:
            Completion data dict or None if timeout
        """
        import json
        # EA版の完了ファイルを優先（より信頼性が高い）
        completion_file_ea = self.mt5_common_path / "screenshot_complete_ea.txt"
        completion_file_indicator = self.mt5_common_path / "screenshot_complete.txt"

        # デバッグ: Common/Filesディレクトリの内容を確認
        try:
            files_in_dir = list(self.mt5_common_path.glob("screenshot*"))
            logger.info(f"Files matching 'screenshot*' in {self.mt5_common_path}: {[f.name for f in files_in_dir]}")
        except Exception as e:
            logger.debug(f"Could not list directory: {e}")

        start_time = time.time()
        read_fail_count = 0
        max_read_fails = 5  # 5回読み込み失敗したらファイルを削除

        while time.time() - start_time < self.timeout:
            # EA版を優先的にチェック
            completion_file = None
            if completion_file_ea.exists():
                completion_file = completion_file_ea
                logger.info(f"Found EA completion file: {completion_file}")
            elif completion_file_indicator.exists():
                completion_file = completion_file_indicator
                logger.info(f"Found indicator completion file: {completion_file}")

            if completion_file:
                data = self._read_completion_file(completion_file)
                if data:
                    read_fail_count = 0  # リセット
                    # count > 0 のファイルのみ処理（失敗した古いファイルを無視）
                    count = data.get("count", 0)
                    if count > 0 or data.get("file"):
                        logger.info(f"Valid completion file: count={count}")
                        # Delete completion file
                        try:
                            completion_file.unlink()
                        except Exception:
                            pass
                        # 古いインジケータ版のファイルも削除
                        try:
                            if completion_file_indicator.exists():
                                completion_file_indicator.unlink()
                        except Exception:
                            pass
                        return data
                    else:
                        # count=0は失敗を意味する、削除して待機を継続
                        logger.warning("Completion file has count=0, deleting and waiting for EA...")
                        try:
                            completion_file.unlink()
                        except Exception:
                            pass
                        time.sleep(0.2)
                        continue
                else:
                    # File exists but couldn't be parsed
                    read_fail_count += 1
                    if read_fail_count >= max_read_fails:
                        # 読み込み失敗が続く場合は削除（壊れたファイル）
                        logger.warning(f"Deleting unreadable file after {read_fail_count} attempts")
                        try:
                            completion_file.unlink()
                        except Exception:
                            pass
                        read_fail_count = 0
                    time.sleep(0.2)
                    continue

            time.sleep(0.1)

        logger.warning("Timeout waiting for MQL5 screenshot")
        return None

    def _read_completion_file(self, filepath: Path) -> Optional[dict]:
        """
        Read completion file with multiple encoding attempts.
        MQL5 FileWriteString outputs UTF-16 by default, FILE_ANSI uses cp1252.
        """
        import json

        # Try multiple encodings
        # FILE_ANSI = cp1252 (Windows), FILE_TXT = UTF-16
        encodings = ['cp1252', 'latin-1', 'utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le']

        # First, try to read raw bytes to debug
        try:
            with open(filepath, 'rb') as f:
                raw_bytes = f.read(300)
            logger.info(f"Raw file bytes: {raw_bytes}")
            logger.info(f"File size: {len(raw_bytes)} bytes")
        except Exception as e:
            logger.error(f"Could not read raw bytes: {e}")

        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()

                # Remove null characters that may appear
                content = content.replace('\x00', '')

                # Strip whitespace and check if it looks like JSON
                content = content.strip()
                if not content.startswith('{'):
                    logger.debug(f"Content with {encoding} doesn't start with '{{': {repr(content[:80])}")
                    continue

                # Fix Windows path backslashes for JSON parsing
                # MQL5 writes C:\Users\... but JSON needs C:\\Users\\...
                import re
                content = re.sub(
                    r'"terminal_path":\s*"([^"]*)"',
                    lambda m: '"terminal_path": "' + m.group(1).replace('\\', '\\\\') + '"',
                    content
                )

                # Try to parse as JSON
                data = json.loads(content)
                logger.info(f"Successfully read completion file with {encoding} encoding")
                return data

            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.debug(f"Failed to read with {encoding}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Unexpected error with {encoding}: {e}")
                continue

        logger.error("Failed to read completion file with any encoding")
        return None

    def capture_current_chart(self, output_path: Path = None) -> Optional[str]:
        """
        Capture screenshot of the current chart via MQL5.

        Args:
            output_path: Path to save the screenshot

        Returns:
            Path to screenshot or None
        """
        # Send request
        if not self.request_screenshot():
            return None

        # Wait for completion
        result = self.wait_for_completion()
        if not result:
            return None

        # Find the screenshot file
        screenshot_name = result.get("file", "")
        if not screenshot_name:
            logger.error("No screenshot filename in completion data")
            return None

        # MQL5 saves to MQL5/Files folder, not Common/Files
        # We need to check both locations
        source_paths = [
            self.mt5_common_path / screenshot_name,
        ]

        for source_path in source_paths:
            if source_path.exists():
                if output_path:
                    import shutil
                    shutil.copy2(source_path, output_path)
                    logger.info(f"Screenshot copied to: {output_path}")
                    return str(output_path)
                else:
                    return str(source_path)

        logger.error(f"Screenshot file not found: {screenshot_name}")
        return None

    def get_mt5_files_path(self) -> Path:
        """Return the MT5 Common Files path."""
        return self.mt5_common_path

    def capture_all_timeframes(self, output_dir: Path = None) -> Dict[str, str]:
        """
        Capture screenshots for all timeframes via MQL5 ChartExporter.

        The ChartExporter.mq5 indicator opens charts for all timeframes
        (D1, H4, M15, M5, M1) and captures screenshots for each.

        Args:
            output_dir: Directory to save screenshots (optional override)

        Returns:
            Dict[str, str]: timeframe -> screenshot path
        """
        import shutil

        results = {}
        save_dir = output_dir or self.output_dir
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Send request to MQL5
        if not self.request_screenshot():
            logger.error("Failed to send screenshot request to MQL5")
            return results

        # Wait for completion
        completion = self.wait_for_completion()
        if not completion:
            logger.warning("MQL5 screenshot timeout or failed")
            return results

        # Get info from completion data
        symbol = completion.get("symbol", "XAUUSDp")
        timeframes = completion.get("timeframes", self.DEFAULT_TIMEFRAMES)
        prefix = completion.get("prefix", f"chart_{symbol}_")
        count = completion.get("count", 0)
        terminal_path = completion.get("terminal_path", "")

        logger.info(f"MQL5 captured {count} timeframes for {symbol}")

        # Determine source path - use terminal_path if provided, otherwise Common/Files
        if terminal_path:
            # Screenshots are in terminal's MQL5/Files folder
            # terminal_path contains backslashes from Windows, normalize it
            terminal_path = terminal_path.replace("\\", "/")
            source_dir = Path(terminal_path) / "MQL5" / "Files"
            logger.info(f"Using terminal MQL5/Files path: {source_dir}")
        else:
            # Fallback to Common/Files
            source_dir = self.mt5_common_path
            logger.info(f"Using Common/Files path: {source_dir}")

        # Copy all timeframe screenshots to output directory
        for tf in timeframes:
            screenshot_name = f"{prefix}{tf}.png"
            source_path = source_dir / screenshot_name

            if source_path.exists():
                dst_path = save_dir / f"{tf}.png"
                try:
                    shutil.copy2(source_path, dst_path)
                    results[tf] = str(dst_path)
                    logger.info(f"Copied screenshot: {tf} -> {dst_path}")
                except Exception as e:
                    logger.error(f"Failed to copy screenshot {tf}: {e}")
            else:
                logger.warning(f"Screenshot not found: {source_path}")

        return results


# Global MQL5 screen capture instance
_mql5_capture: Optional[MQL5ScreenCapture] = None


def get_mql5_capture() -> MQL5ScreenCapture:
    """Get or create the global MQL5 screen capture instance."""
    global _mql5_capture
    if _mql5_capture is None:
        _mql5_capture = MQL5ScreenCapture()
    return _mql5_capture


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
