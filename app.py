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
from collector.horizontal_lines import get_horizontal_lines_reader

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
    symbol: str = "XAUUSDp"
    screenshot_interval: int = 30


class SessionStartRequest(BaseModel):
    thought: str


class SessionHoldRequest(BaseModel):
    thought: str


class SessionEndRequest(BaseModel):
    action: str  # SELL or STOP_LOSS
    thought: str


# ============ Original endpoints ============

@app.get("/", response_class=HTMLResponse)
async def index():
    """メインページ"""
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_page():
    """セッション閲覧ページ"""
    html_path = Path(__file__).parent / "templates" / "sessions.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/api/symbols")
async def get_symbols():
    """利用可能な銘柄一覧を取得"""
    symbols = mt5_data.get_available_symbols()
    # よく使う銘柄を優先的に表示（XAUUSDpは一部ブローカーの金シンボル）
    priority = ["XAUUSDp", "XAUUSD", "USDJPY", "EURUSD", "GBPUSD", "EURJPY", "GBPJPY", "AUDUSD"]
    priority_symbols = [s for s in priority if s in symbols]
    other_symbols = [s for s in symbols if s not in priority]
    return {"symbols": priority_symbols + other_symbols}


@app.get("/api/ohlc")
async def get_ohlc(
    symbol: str = Query(default="XAUUSDp", description="通貨ペア"),
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


# ============ Session endpoints ============

@app.get("/api/sessions")
async def list_sessions(limit: int = Query(default=10, ge=1, le=50)):
    """セッション一覧を取得"""
    service = get_collector_service()
    sessions = service.list_sessions(limit)

    return {
        "count": len(sessions),
        "sessions": [
            {
                "session_id": s.session_id,
                "symbol": s.symbol,
                "status": s.status.value,
                "entry": {
                    "time": s.entry.time.isoformat() if s.entry else None,
                    "price": s.entry.price if s.entry else None,
                    "thought": s.entry.thought if s.entry else None
                } if s.entry else None,
                "exit": {
                    "time": s.exit.time.isoformat() if s.exit else None,
                    "action": s.exit.action.value if s.exit else None,
                    "price": s.exit.price if s.exit else None
                } if s.exit else None,
                "hold_count": len(s.holds),
                "result": {
                    "duration_minutes": s.result.duration_minutes,
                    "profit": s.result.profit,
                    "profit_pips": s.result.profit_pips
                } if s.result else None
            }
            for s in sessions
        ]
    }


@app.get("/api/sessions/active")
async def get_active_session():
    """アクティブなセッションを取得"""
    service = get_collector_service()
    session = service.get_active_session()

    if not session:
        return {"session": None}

    return {
        "session": {
            "session_id": session.session_id,
            "symbol": session.symbol,
            "status": session.status.value,
            "entry": {
                "time": session.entry.time.isoformat() if session.entry else None,
                "price": session.entry.price if session.entry else None,
                "thought": session.entry.thought if session.entry else None
            } if session.entry else None,
            "hold_count": len(session.holds),
            "snapshot_count": session.snapshot_count
        }
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """セッション詳細を取得"""
    service = get_collector_service()
    session = service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session": {
            "session_id": session.session_id,
            "symbol": session.symbol,
            "status": session.status.value,
            "entry": {
                "time": session.entry.time.isoformat() if session.entry else None,
                "action": session.entry.action.value if session.entry else None,
                "price": session.entry.price if session.entry else None,
                "thought": session.entry.thought if session.entry else None
            } if session.entry else None,
            "exit": {
                "time": session.exit.time.isoformat() if session.exit else None,
                "action": session.exit.action.value if session.exit else None,
                "price": session.exit.price if session.exit else None,
                "thought": session.exit.thought if session.exit else None
            } if session.exit else None,
            "holds": [
                {
                    "time": h.time.isoformat(),
                    "thought": h.thought
                }
                for h in session.holds
            ],
            "result": {
                "duration_minutes": session.result.duration_minutes,
                "profit": session.result.profit,
                "profit_pips": session.result.profit_pips
            } if session.result else None,
            "snapshot_count": session.snapshot_count,
            "timeframes": session.timeframes
        }
    }


@app.get("/api/sessions/{session_id}/snapshots")
async def list_snapshots(session_id: str):
    """セッションのスナップショット一覧を取得"""
    import json

    snapshots_dir = Path("data/sessions") / f"session_{session_id}" / "snapshots"

    if not snapshots_dir.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    snapshots = []
    for snapshot_dir in sorted(snapshots_dir.iterdir()):
        if snapshot_dir.is_dir():
            # Read thought.json for action and thought
            thought_file = snapshot_dir / "thought.json"
            thought_data = {}
            if thought_file.exists():
                with open(thought_file, "r", encoding="utf-8") as f:
                    thought_data = json.load(f)

            snapshots.append({
                "name": snapshot_dir.name,
                "timestamp": thought_data.get("timestamp", ""),
                "action": thought_data.get("action", "UNKNOWN"),
                "thought": thought_data.get("thought", "")
            })

    return {
        "session_id": session_id,
        "snapshots": snapshots
    }


@app.get("/api/sessions/{session_id}/snapshots/{snapshot_name}")
async def get_snapshot_detail(session_id: str, snapshot_name: str):
    """スナップショット詳細を取得"""
    import json

    session_dir = Path("data/sessions") / f"session_{session_id}" / "snapshots" / snapshot_name

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_name}")

    result = {
        "session_id": session_id,
        "snapshot_name": snapshot_name,
        "thought": None,
        "market_data": None,
        "horizontal_lines": []
    }

    # Read thought.json
    thought_file = session_dir / "thought.json"
    if thought_file.exists():
        with open(thought_file, "r", encoding="utf-8") as f:
            thought_data = json.load(f)
            result["thought"] = thought_data.get("thought", "")

    # Read market_data.json
    market_data_file = session_dir / "market_data.json"
    if market_data_file.exists():
        with open(market_data_file, "r", encoding="utf-8") as f:
            result["market_data"] = json.load(f)

    # Read horizontal_lines.json
    hlines_file = session_dir / "horizontal_lines.json"
    if hlines_file.exists():
        with open(hlines_file, "r", encoding="utf-8") as f:
            hlines_data = json.load(f)
            result["horizontal_lines"] = hlines_data.get("lines", [])

    return result


@app.get("/api/sessions/{session_id}/snapshots/{snapshot_name}/image/{timeframe}")
async def get_snapshot_image(session_id: str, snapshot_name: str, timeframe: str):
    """スナップショット画像を取得"""
    from fastapi.responses import FileResponse

    image_path = Path("data/sessions") / f"session_{session_id}" / "snapshots" / snapshot_name / "screenshots" / f"{timeframe}.png"

    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Screenshot not found: {timeframe}")

    return FileResponse(image_path, media_type="image/png")


@app.post("/api/sessions/start")
async def start_session(request: SessionStartRequest):
    """
    新しいセッションを開始（BUYエントリー）
    - 全時間足のスクリーンショットを取得
    - 市場データを保存
    - 思考を記録
    """
    service = get_collector_service()

    if service.has_active_session():
        raise HTTPException(
            status_code=400,
            detail="Active session exists. End it before starting a new one."
        )

    session_id = service.start_session(request.thought)

    if not session_id:
        raise HTTPException(status_code=500, detail="Failed to start session")

    # Notify WebSocket clients
    await notify_clients({
        "type": "session_started",
        "session_id": session_id
    })

    return {
        "status": "started",
        "session_id": session_id,
        "message": "Session started with BUY entry"
    }


@app.post("/api/sessions/hold")
async def add_hold(request: SessionHoldRequest):
    """
    現在のセッションにHOLDを追加
    - 全時間足のスクリーンショットを取得
    - 市場データを保存
    - 思考を記録
    """
    service = get_collector_service()

    if not service.has_active_session():
        raise HTTPException(status_code=400, detail="No active session")

    success = service.add_hold(request.thought)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to add HOLD")

    # Notify WebSocket clients
    await notify_clients({
        "type": "hold_added",
        "thought": request.thought
    })

    return {
        "status": "added",
        "message": "HOLD recorded"
    }


@app.post("/api/sessions/end")
async def end_session(request: SessionEndRequest):
    """
    現在のセッションを終了（SELL/STOP_LOSS）
    - 全時間足のスクリーンショットを取得
    - 市場データを保存
    - 結果を計算
    """
    service = get_collector_service()

    if not service.has_active_session():
        raise HTTPException(status_code=400, detail="No active session")

    try:
        action = Action(request.action)
        if action not in [Action.SELL, Action.STOP_LOSS]:
            raise ValueError("Invalid action for ending session")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action: {request.action}. Must be SELL or STOP_LOSS"
        )

    completed_session = service.end_session(action, request.thought)

    if not completed_session:
        raise HTTPException(status_code=500, detail="Failed to end session")

    # Notify WebSocket clients
    await notify_clients({
        "type": "session_ended",
        "session_id": completed_session.session_id,
        "action": action.value,
        "result": {
            "profit": completed_session.result.profit if completed_session.result else None,
            "duration_minutes": completed_session.result.duration_minutes if completed_session.result else None
        }
    })

    return {
        "status": "ended",
        "session_id": completed_session.session_id,
        "action": action.value,
        "result": {
            "duration_minutes": completed_session.result.duration_minutes,
            "profit": completed_session.result.profit,
            "profit_pips": completed_session.result.profit_pips
        } if completed_session.result else None
    }


# ============ Horizontal Lines endpoints ============

@app.get("/api/horizontal-lines")
async def get_horizontal_lines():
    """
    MT5から取得した水平線データを返す
    MQL5スクリプトで出力されたJSONファイルを読み込む
    """
    reader = get_horizontal_lines_reader()
    data = reader.read_raw()

    return {
        "symbol": data.get("symbol", ""),
        "timestamp": data.get("timestamp", ""),
        "lines": [
            {
                "name": line.get("name", ""),
                "price": line.get("price", 0),
                "color": line.get("color", "#FF0000")
            }
            for line in data.get("lines", [])
        ],
        "file_path": reader.get_file_path()
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
