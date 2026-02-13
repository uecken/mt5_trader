"""
FastAPI Webサーバー - MT5 Trader思考解析 & 売買システム
"""
from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel
import asyncio
import logging

import mt5_data
from models.market_data import Action, ThoughtInput as ThoughtInputModel
from collector.collector_service import get_collector_service, CollectorService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MT5 Trader思考解析 & 売買システム",
    description="MT5取引データ収集・分析・学習システム",
    version="1.0.0"
)

# Global state for WebSocket connections
connected_clients: List[WebSocket] = []


# Request models
class ThoughtSubmitRequest(BaseModel):
    thought: str
    action: str


class CollectorStartRequest(BaseModel):
    symbol: str = "XAUUSD"
    screenshot_interval: int = 30


# ============ Original endpoints ============

@app.get("/", response_class=HTMLResponse)
async def index():
    """メインページ"""
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/api/symbols")
async def get_symbols():
    """利用可能な銘柄一覧を取得"""
    symbols = mt5_data.get_available_symbols()
    # よく使う銘柄を優先的に表示
    priority = ["XAUUSD", "USDJPY", "EURUSD", "GBPUSD", "EURJPY", "GBPJPY", "AUDUSD"]
    priority_symbols = [s for s in priority if s in symbols]
    other_symbols = [s for s in symbols if s not in priority]
    return {"symbols": priority_symbols + other_symbols}


@app.get("/api/ohlc")
async def get_ohlc(
    symbol: str = Query(default="XAUUSD", description="通貨ペア"),
    timeframe: str = Query(default="H1", description="時間足"),
    count: int = Query(default=200, ge=10, le=1000, description="バー数")
):
    """ローソク足データを取得"""
    data = mt5_data.get_ohlc_as_dict(symbol, timeframe, count)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(data),
        "data": data
    }


@app.get("/api/timeframes")
async def get_timeframes():
    """利用可能な時間足一覧"""
    return {
        "timeframes": [
            {"value": "M1", "label": "1分足"},
            {"value": "M5", "label": "5分足"},
            {"value": "M15", "label": "15分足"},
            {"value": "M30", "label": "30分足"},
            {"value": "H1", "label": "1時間足"},
            {"value": "H4", "label": "4時間足"},
            {"value": "D1", "label": "日足"},
            {"value": "W1", "label": "週足"},
            {"value": "MN1", "label": "月足"},
        ]
    }


# ============ Collector endpoints ============

@app.post("/api/collector/start")
async def start_collector(request: CollectorStartRequest = None):
    """
    データ収集を開始
    - スクリーンショット: 30秒毎
    - ポジション監視: 1秒毎
    - アクション検出: 自動
    """
    service = get_collector_service()

    if service.is_running:
        return {"status": "already_running", "message": "Collector is already running"}

    if request:
        # Recreate service with new settings if needed
        pass

    success = service.start()
    if success:
        return {"status": "started", "message": "Data collection started"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start collector")


@app.post("/api/collector/stop")
async def stop_collector():
    """データ収集を停止"""
    service = get_collector_service()

    if not service.is_running:
        return {"status": "not_running", "message": "Collector is not running"}

    service.stop()
    return {"status": "stopped", "message": "Data collection stopped"}


@app.get("/api/collector/status")
async def get_collector_status():
    """コレクターの状態を取得"""
    service = get_collector_service()
    status = service.get_status()

    return {
        "is_running": status.is_running,
        "started_at": status.started_at.isoformat() if status.started_at else None,
        "screenshots_count": status.screenshots_count,
        "actions_count": status.actions_count,
        "last_screenshot_at": status.last_screenshot_at.isoformat() if status.last_screenshot_at else None,
        "last_action_at": status.last_action_at.isoformat() if status.last_action_at else None
    }


@app.get("/api/collector/pending-actions")
async def get_pending_actions():
    """思考入力待ちのアクション一覧を取得"""
    service = get_collector_service()
    pending = service.get_pending_actions()
    return {"pending_actions": pending}


@app.post("/api/collector/thought")
async def submit_thought(request: ThoughtSubmitRequest):
    """
    トレーダーの思考を入力
    アクションに対する判断理由を記録
    """
    service = get_collector_service()

    try:
        action = Action(request.action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")

    thought_input = service.submit_thought(request.thought, action)

    # Notify WebSocket clients
    await notify_clients({
        "type": "thought_submitted",
        "action": action.value,
        "thought": request.thought
    })

    return {
        "status": "submitted",
        "thought": request.thought,
        "action": action.value
    }


@app.get("/api/collector/statistics")
async def get_statistics():
    """収集データの統計情報を取得"""
    service = get_collector_service()
    return service.get_statistics()


@app.get("/api/collector/recent-data")
async def get_recent_data(limit: int = Query(default=10, ge=1, le=100)):
    """最近の収集データを取得"""
    service = get_collector_service()
    data = service.get_recent_data(limit)

    return {
        "count": len(data),
        "data": [
            {
                "timestamp": d.timestamp.isoformat(),
                "screenshot_path": d.screenshot_path,
                "action": d.action.value,
                "thought": d.thought
            }
            for d in data
        ]
    }


# ============ WebSocket for real-time updates ============

@app.websocket("/ws/collector")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket接続でリアルタイム更新を受信
    - アクション検出時の通知
    - 思考入力リクエスト
    """
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")

    try:
        while True:
            # Keep connection alive and receive messages
            data = await websocket.receive_text()
            logger.debug(f"Received from WebSocket: {data}")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")


async def notify_clients(message: dict):
    """WebSocket接続中の全クライアントに通知"""
    import json
    message_str = json.dumps(message, ensure_ascii=False)

    disconnected = []
    for client in connected_clients:
        try:
            await client.send_text(message_str)
        except:
            disconnected.append(client)

    # Clean up disconnected clients
    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)


# ============ Startup/Shutdown events ============

@app.on_event("startup")
async def startup_event():
    """アプリ起動時の初期化"""
    logger.info("MT5 Trader思考解析 & 売買システム starting...")

    # Ensure data directories exist
    from config.settings import ensure_directories
    ensure_directories()


@app.on_event("shutdown")
async def shutdown_event():
    """アプリ終了時のクリーンアップ"""
    logger.info("Shutting down...")

    # Stop collector if running
    service = get_collector_service()
    if service.is_running:
        service.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
