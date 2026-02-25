"""
Horizontal lines reader module.
Reads horizontal line data exported from MT5 via MQL5 script.
"""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HorizontalLine:
    """Represents a horizontal line from MT5."""
    name: str
    price: float
    color: str = "#FF0000"


class HorizontalLinesReader:
    """
    Reads horizontal line data from JSON file exported by MT5.

    The MQL5 script exports to MT5's common data folder:
    C:\\Users\\<user>\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\
    """

    def __init__(self, file_path: Optional[Path] = None):
        """
        Initialize the reader.

        Args:
            file_path: Path to the JSON file. If None, uses MT5 common folder.
        """
        if file_path:
            self.file_path = Path(file_path)
        else:
            # Default to MT5 common files folder
            self.file_path = self._get_mt5_common_path() / "horizontal_lines.json"

    def _get_mt5_common_path(self) -> Path:
        """Get MT5 common files folder path."""
        # MT5 common folder location on Windows
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            common_path = Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files"
            if common_path.exists():
                return common_path

        # Fallback to local data folder
        return Path("data")

    def _read_file_with_encoding(self) -> Optional[dict]:
        """
        Read JSON file trying multiple encodings.
        MQL5 FileWriteString outputs UTF-16 LE on Windows.
        """
        # Try different encodings (MQL5 typically uses UTF-16 LE)
        encodings = ['utf-16', 'utf-16-le', 'utf-8-sig', 'utf-8']

        for encoding in encodings:
            try:
                with open(self.file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    # Remove any null bytes that might be present
                    content = content.replace('\x00', '')
                    return json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            except Exception as e:
                logger.debug(f"Failed with {encoding}: {e}")
                continue

        return None

    def read_lines(self) -> List[HorizontalLine]:
        """
        Read horizontal lines from the JSON file.

        Returns:
            List of HorizontalLine objects
        """
        if not self.file_path.exists():
            logger.warning(f"Horizontal lines file not found: {self.file_path}")
            return []

        try:
            data = self._read_file_with_encoding()
            if data is None:
                logger.error("Could not read file with any encoding")
                return []

            lines = []
            seen_prices = set()  # 重複除去用

            for line_data in data.get("lines", []):
                name = line_data.get("name", "")

                # ChartExporterEAがコピーした水平線は除外
                if "_copied_" in name:
                    continue

                price = float(line_data.get("price", 0))

                # 同じ価格の水平線は重複として除外
                price_key = round(price, 2)
                if price_key in seen_prices:
                    continue
                seen_prices.add(price_key)

                line = HorizontalLine(
                    name=name,
                    price=price,
                    color=line_data.get("color", "#FF0000")
                )
                lines.append(line)

            logger.info(f"Loaded {len(lines)} horizontal lines from {self.file_path}")
            return lines

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading horizontal lines: {e}")
            return []

    def read_raw(self) -> dict:
        """
        Read raw JSON data including metadata.
        Filters out copied lines and duplicates.

        Returns:
            Raw dictionary from JSON file
        """
        if not self.file_path.exists():
            return {"symbol": "", "timestamp": "", "lines": []}

        try:
            data = self._read_file_with_encoding()
            if data is None:
                logger.error("Could not read file with any encoding")
                return {"symbol": "", "timestamp": "", "lines": []}

            # フィルタリング: コピーされた水平線と重複を除外
            filtered_lines = []
            seen_prices = set()

            for line in data.get("lines", []):
                name = line.get("name", "")

                # _copied_ を含む水平線は除外
                if "_copied_" in name:
                    continue

                price = float(line.get("price", 0))
                price_key = round(price, 2)

                # 同じ価格の重複は除外
                if price_key in seen_prices:
                    continue
                seen_prices.add(price_key)

                filtered_lines.append(line)

            data["lines"] = filtered_lines
            return data
        except Exception as e:
            logger.error(f"Error reading raw data: {e}")
            return {"symbol": "", "timestamp": "", "lines": []}

    def get_file_path(self) -> str:
        """Return the current file path as string."""
        return str(self.file_path)


# Global reader instance
_reader: Optional[HorizontalLinesReader] = None


def get_horizontal_lines_reader() -> HorizontalLinesReader:
    """Get or create the global reader instance."""
    global _reader
    if _reader is None:
        _reader = HorizontalLinesReader()
    return _reader


if __name__ == "__main__":
    # Test the reader
    logging.basicConfig(level=logging.INFO)

    reader = HorizontalLinesReader()
    print(f"Looking for file at: {reader.get_file_path()}")

    lines = reader.read_lines()
    print(f"Found {len(lines)} horizontal lines:")
    for line in lines:
        print(f"  {line.name}: {line.price} ({line.color})")
