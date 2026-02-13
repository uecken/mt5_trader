"""
MT5からローソク足データを取得するモジュール
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from typing import Optional


def initialize_mt5() -> bool:
    """MT5を初期化"""
    if not mt5.initialize():
        print(f"MT5初期化失敗: {mt5.last_error()}")
        return False
    return True


def shutdown_mt5():
    """MT5を終了"""
    mt5.shutdown()


def get_timeframe(tf_str: str) -> int:
    """文字列からMT5のタイムフレーム定数に変換"""
    timeframes = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }
    return timeframes.get(tf_str.upper(), mt5.TIMEFRAME_H1)


def get_ohlc_data(
    symbol: str = "USDJPY",
    timeframe: str = "H1",
    count: int = 100
) -> Optional[pd.DataFrame]:
    """
    指定した銘柄・時間足のローソク足データを取得

    Args:
        symbol: 通貨ペア（例: "USDJPY", "EURUSD"）
        timeframe: 時間足（M1, M5, M15, M30, H1, H4, D1, W1, MN1）
        count: 取得するバーの数

    Returns:
        DataFrame with columns: time, open, high, low, close, volume
    """
    if not initialize_mt5():
        return None

    try:
        tf = get_timeframe(timeframe)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

        if rates is None or len(rates) == 0:
            print(f"データ取得失敗: {symbol} {timeframe}")
            return None

        df = pd.DataFrame(rates)
        # Unix時間をdatetimeに変換
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # 必要な列のみ選択
        df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
        df = df.rename(columns={'tick_volume': 'volume'})

        return df

    finally:
        shutdown_mt5()


def get_available_symbols() -> list:
    """利用可能な銘柄一覧を取得"""
    if not initialize_mt5():
        return []

    try:
        symbols = mt5.symbols_get()
        if symbols is None:
            return []
        return [s.name for s in symbols if s.visible]
    finally:
        shutdown_mt5()


def get_ohlc_as_dict(
    symbol: str = "USDJPY",
    timeframe: str = "H1",
    count: int = 100
) -> list:
    """
    ローソク足データをJSON用の辞書リストで返す
    （Lightweight Charts用のフォーマット）
    """
    df = get_ohlc_data(symbol, timeframe, count)
    if df is None:
        return []

    result = []
    for _, row in df.iterrows():
        result.append({
            "time": int(row['time'].timestamp()),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": int(row['volume'])
        })

    return result


if __name__ == "__main__":
    # テスト実行
    print("利用可能な銘柄:")
    symbols = get_available_symbols()
    print(symbols[:10] if symbols else "取得失敗")

    print("\nUSDJPY H1 直近10本:")
    df = get_ohlc_data("USDJPY", "H1", 10)
    if df is not None:
        print(df)
