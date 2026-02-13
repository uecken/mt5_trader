# MT5 Trader思考解析 & 売買システム

## システム概要

MT5トレーダーの取引行動と思考を記録・分析し、E2E模倣学習に活用するためのデータ収集システムです。

### 目的
- 利益を出しているトレーダーの取引パターンを記録
- 取引時の思考・判断理由をテキスト化
- 収集データを用いた模倣学習モデルの構築

---

## システム画面

![MT5 Trader思考解析 & 売買システム](./screenshots/main_interface.png)

### 画面構成

| エリア | 説明 |
|--------|------|
| ヘッダー | 銘柄選択、時間足選択、表示本数設定 |
| チャートエリア | ローソク足チャート表示（Lightweight Charts使用） |
| データ収集パネル | コレクター制御、思考入力 |

---

## 機能一覧

### 1. チャート表示機能
- **対応銘柄**: XAUUSD（ゴールド）他、MT5で利用可能な全銘柄
- **対応時間足**: M1, M5, M15, M30, H1, H4, D1, W1, MN1
- **表示本数**: 10〜1000本（デフォルト200本）

### 2. データ収集機能

#### 2.1 スクリーンショット収集
- **取得間隔**: 30秒毎（設定変更可能）
- **保存先**: `data/screenshots/`
- **ファイル名形式**: `YYYYMMDD_HHMMSS.png`

#### 2.2 マルチタイムフレームOHLCデータ取得
スクリーンショットと同時に以下の時間足データを記録:

| 時間足 | 取得本数 | 用途 |
|--------|----------|------|
| D1（日足） | 30本 | 長期トレンド把握 |
| H4（4時間足） | 50本 | 中期トレンド把握 |
| M15（15分足） | 100本 | 短期トレンド把握 |
| M5（5分足） | 100本 | エントリータイミング |
| M1（1分足） | 100本 | 詳細な値動き |

#### 2.3 テクニカル指標計算
各時間足に対して以下の指標を自動計算:
- **RSI** (14期間)
- **MACD** (12, 26, 9)
- **SMA** (20, 50期間)
- **EMA** (20期間)
- **Bollinger Bands** (20期間, 2σ)

#### 2.4 アクション自動検出
MT5 APIでポジション変化を1秒毎に監視:

| アクション | 検出条件 | 説明 |
|-----------|----------|------|
| BUY | 新規ポジション発生 | 買いエントリー |
| SELL | ポジションクローズ（利益） | 利確決済 |
| STOP_LOSS | ポジションクローズ（損失） | 損切り決済 |
| HOLD | 30秒間変化なし | 見送り・保持 |

#### 2.5 思考入力機能
- アクション検出時にWebフォームで思考を入力
- 入力例: 「RSI30以下で反発、サポートラインで買いエントリー」
- HOLDの場合は任意入力

---

## データ構造

### 保存ディレクトリ
```
data/
├── screenshots/     # スクリーンショット画像
├── training/        # 学習用統合データ（JSON）
├── actions/         # アクションログ
└── thoughts/        # 思考入力ログ
```

### 統合データ形式（JSON）
```json
{
  "timestamp": "2026-02-13T10:30:00",
  "screenshot_path": "data/screenshots/20260213_103000.png",
  "action": "BUY",
  "thought": "ダブルトップ形成後、ネックライン割れを確認。RSI30以下からの反発も確認したのでエントリー",
  "position_info": {
    "ticket": 12345678,
    "symbol": "XAUUSD",
    "volume": 0.1,
    "price": 2050.50,
    "profit": 0.0,
    "sl": 2045.00,
    "tp": 2070.00,
    "type": "BUY"
  },
  "market_state": {
    "timeframes": {
      "D1": {
        "ohlc": [...],
        "indicators": {"rsi": 45.2, "macd": 1.5, ...}
      },
      "H4": {...},
      "M15": {...},
      "M5": {...},
      "M1": {...}
    }
  }
}
```

---

## システムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (HTML/JS)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Chart View  │  │ Controls    │  │ Thought Input Form  │ │
│  │ (LW Charts) │  │ Start/Stop  │  │ Action + Text       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP / WebSocket
┌────────────────────────────┴────────────────────────────────┐
│                    FastAPI Backend                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ API Endpoints                                        │   │
│  │ /api/collector/start, stop, status, thought, ...    │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Collector Service                                    │   │
│  │ ┌───────────────┐ ┌───────────────┐ ┌─────────────┐ │   │
│  │ │ScreenCapture │ │PositionMonitor│ │MarketData   │ │   │
│  │ │ (30秒毎)     │ │ (1秒毎)       │ │Collector    │ │   │
│  │ └───────────────┘ └───────────────┘ └─────────────┘ │   │
│  │ ┌───────────────┐ ┌───────────────┐                 │   │
│  │ │ThoughtManager │ │ DataLinker    │                 │   │
│  │ │ (思考入力)    │ │ (データ統合)  │                 │   │
│  │ └───────────────┘ └───────────────┘                 │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────┘
                             │ MT5 API
┌────────────────────────────┴────────────────────────────────┐
│                    MetaTrader 5                             │
│  - OHLC Data                                                │
│  - Position Information                                     │
│  - Account Information                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## API エンドポイント

### チャートデータ
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/symbols` | 利用可能な銘柄一覧 |
| GET | `/api/timeframes` | 利用可能な時間足一覧 |
| GET | `/api/ohlc` | OHLCデータ取得 |

### データ収集
| Method | Endpoint | 説明 |
|--------|----------|------|
| POST | `/api/collector/start` | 収集開始 |
| POST | `/api/collector/stop` | 収集停止 |
| GET | `/api/collector/status` | 状態取得 |
| GET | `/api/collector/pending-actions` | 思考入力待ちアクション |
| POST | `/api/collector/thought` | 思考入力 |
| GET | `/api/collector/statistics` | 統計情報 |
| GET | `/api/collector/recent-data` | 最近の収集データ |

### WebSocket
| Endpoint | 説明 |
|----------|------|
| `/ws/collector` | リアルタイム更新通知 |

---

## プロジェクト構成

```
MT5/
├── app.py                      # FastAPI メインアプリケーション
├── mt5_data.py                 # MT5データ取得ユーティリティ
├── requirements.txt            # 依存関係
│
├── config/
│   └── settings.py             # 設定管理
│
├── collector/                  # データ収集モジュール
│   ├── screen_capture.py       # スクリーンショット取得
│   ├── market_data_collector.py # マルチタイムフレームOHLC
│   ├── position_monitor.py     # ポジション監視
│   ├── thought_input.py        # 思考入力管理
│   ├── data_linker.py          # データ紐付け
│   └── collector_service.py    # 収集サービス統合
│
├── models/
│   └── market_data.py          # データモデル定義
│
├── data/                       # 収集データ保存先
│   ├── screenshots/
│   ├── training/
│   ├── actions/
│   └── thoughts/
│
├── templates/
│   └── index.html              # Webフロントエンド
│
└── docs/
    └── system_overview.md      # このドキュメント
```

---

## 使用技術

| カテゴリ | 技術 |
|----------|------|
| バックエンド | Python 3.11, FastAPI, uvicorn |
| フロントエンド | HTML5, JavaScript, Lightweight Charts |
| MT5連携 | MetaTrader5 Python API |
| スクリーンショット | mss, Pillow, pywin32 |
| テクニカル分析 | ta (Technical Analysis Library) |
| データ管理 | pandas, JSON |
| 設定管理 | pydantic, pydantic-settings |

---

## 起動方法

```bash
# 依存関係インストール
pip install -r requirements.txt

# サーバー起動
python app.py

# ブラウザでアクセス
# http://127.0.0.1:8000
```

**前提条件:**
- MetaTrader 5 が起動していること
- MT5でXAUUSD等の銘柄が表示可能なこと

---

## 将来の拡張計画

### Phase 2: E2E模倣学習
- PyTorch Dataset/DataLoader
- CNN/ViTモデル構築
- 学習・推論パイプライン

### Phase 3: ルールベース判定
- テクニカル指標ルールエンジン
- エントリー条件YAML定義
- シグナル生成

### Phase 4: マルチエージェントシステム
- MT5情報取得Agent
- 解析Agent
- 経済指標Agent
- 売買決定Agent
- システム管理Agent

---

## 作成日
2026年2月13日

## バージョン
1.0.0
