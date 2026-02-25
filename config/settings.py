"""
Configuration settings for MT5 Trader Data Collection System.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from pathlib import Path
import os


class CollectorSettings(BaseSettings):
    """Settings for the data collector."""

    # Screenshot settings
    screenshot_interval_seconds: int = Field(default=30, description="Interval between screenshots in seconds")
    screenshot_format: str = Field(default="png", description="Screenshot image format")

    # MT5 window settings
    mt5_window_title: str = Field(default="MetaTrader 5", description="MT5 window title for capture")

    # Position monitoring
    position_poll_interval_seconds: float = Field(default=1.0, description="Interval for position polling")

    # Data paths
    data_dir: Path = Field(default=Path("data"), description="Base data directory")
    screenshots_dir: Path = Field(default=Path("data/screenshots"), description="Screenshots directory")
    actions_dir: Path = Field(default=Path("data/actions"), description="Actions log directory")
    thoughts_dir: Path = Field(default=Path("data/thoughts"), description="Thoughts log directory")
    training_dir: Path = Field(default=Path("data/training"), description="Training data directory")


class MT5Settings(BaseSettings):
    """Settings for MT5 connection."""

    terminal_path: str = Field(
        default="C:/Program Files/MetaTrader 5/terminal64.exe",
        description="Path to MT5 terminal"
    )
    timeout: int = Field(default=60000, description="Connection timeout in milliseconds")

    # Trading settings
    default_symbol: str = Field(default="XAUUSDp", description="Default trading symbol")

    # Timeframes for data collection
    timeframes: List[str] = Field(
        default=["D1", "H4", "M15", "M5", "M1"],
        description="Timeframes to collect"
    )

    # Number of candles to fetch per timeframe
    candle_counts: dict = Field(
        default={
            "D1": 30,
            "H4": 50,
            "M15": 100,
            "M5": 100,
            "M1": 100
        },
        description="Number of candles per timeframe"
    )


class AppSettings(BaseSettings):
    """Main application settings."""

    # Server settings
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Sub-settings
    collector: CollectorSettings = Field(default_factory=CollectorSettings)
    mt5: MT5Settings = Field(default_factory=MT5Settings)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"


# Global settings instance
settings = AppSettings()


def ensure_directories():
    """Create necessary directories if they don't exist."""
    dirs = [
        settings.collector.data_dir,
        settings.collector.screenshots_dir,
        settings.collector.actions_dir,
        settings.collector.thoughts_dir,
        settings.collector.training_dir,
    ]
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
