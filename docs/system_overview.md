# MT5 Trader思考解析 & 売買システム

## システム概要

MT5トレーダーの取引行動と思考を記録・分析し、E2E模倣学習に活用するためのデータ収集システムです。

### 目的
- 利益を出しているトレーダーの取引パターンを記録
- 取引時の思考・判断理由をテキスト化
- 収集データを用いた模倣学習モデルの構築

### 動作環境

| 項目 | 要件 |
|------|------|
| OS | Windows 10/11 (64-bit) **必須** |
| Python | 3.11+ (64-bit) |
| MetaTrader 5 | Build 4620+ |

> **注意**: MetaTrader 5およびMetaTrader5 PythonパッケージはWindows専用です。
> 詳細: [実行環境セットアップガイド](environment_setup.md)

---

## システム画面

### メイン画面

![メイン画面](./images/main_interface.png)

| エリア | 説明 |
|--------|------|
| ヘッダー | 銘柄選択、時間足選択、表示本数設定 |
| チャートエリア | ローソク足チャート表示（Lightweight Charts使用） |
| 水平線 | MT5で描画した水平線をリアルタイム表示 |
| セッション管理パネル | BUY/HOLD/SELL/STOP_LOSS ボタン、思考入力 |

### セッション閲覧画面

![セッション閲覧画面](./images/session_viewer.png)

| エリア | 説明 |
|--------|------|
| スナップショット一覧 | BUY/HOLD などの各時点のスナップショット |
| セッション一覧 | 過去の取引セッション一覧 |
| チャートタブ | OHLCデータと水平線をインタラクティブ表示 |
| スクリーンショットタブ | MT5で取得したスクリーンショット画像 |
| 数値データタブ | 水平線リスト、全時間足のインジケーター一覧 |

---

## 機能一覧

### 1. チャート表示機能
- **対応銘柄**: XAUUSDp（ゴールド）他、MT5で利用可能な全銘柄
- **対応時間足**: M1, M5, M15, M30, H1, H4, D1, W1, MN1
- **表示本数**: 10〜1000本（デフォルト200本）
- **水平線表示**: MT5で描画した水平線をリアルタイム表示（5秒毎自動更新）

### 2. データ収集機能

#### 2.1 スクリーンショット収集
- **取得方法**: MQL5 ChartScreenShot() API（ChartExporterEA使用）
- **対応時間足**: D1, H4, M15, M5, M1 の5時間足を自動キャプチャ
- **水平線対応**: 全チャートから水平線を収集してスクリーンショットに含める
- **保存先**: `data/sessions/session_xxx/snapshots/xxx/screenshots/`
- **ファイル名形式**: `D1.png`, `H4.png`, `M15.png`, `M5.png`, `M1.png`

#### 2.2 マルチタイムフレームOHLCデータ取得
スクリーンショットと同時に以下の時間足データを記録:

| 時間足 | 取得本数 | 用途 |
|--------|----------|------|
| D1（日足） | 30本 | 長期トレンド把握 |
| H4（4時間足） | 180本 | 中期トレンド把握（1ヶ月分） |
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
├── thoughts/        # 思考入力ログ
└── sessions/        # セッションデータ（BUY→SELL/STOP_LOSSの1サイクル）
    └── session_YYYYMMDD_HHMMSS/
        ├── session.json           # セッション概要
        └── snapshots/             # 各スナップショット
            └── YYYYMMDD_HHMMSS_ACTION/
                ├── thought.json
                ├── market_data.json
                ├── horizontal_lines.json  # MT5水平線データ
                └── screenshots/
                    ├── D1.png, H4.png, M15.png, M5.png, M1.png
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
    "symbol": "XAUUSDp",
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

### セッション管理
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/sessions` | セッション一覧 |
| GET | `/api/sessions/active` | アクティブセッション取得 |
| GET | `/api/sessions/{session_id}` | セッション詳細 |
| POST | `/api/sessions/start` | セッション開始（BUY） |
| POST | `/api/sessions/hold` | HOLD追加 |
| POST | `/api/sessions/end` | セッション終了（SELL/STOP_LOSS） |

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
│   ├── screen_capture.py       # スクリーンショット取得（MQL5連携）
│   ├── market_data_collector.py # マルチタイムフレームOHLC
│   ├── position_monitor.py     # ポジション監視
│   ├── thought_input.py        # 思考入力管理
│   ├── data_linker.py          # データ紐付け
│   ├── horizontal_lines.py     # MT5水平線読み込み
│   ├── session_manager.py      # セッション管理
│   └── collector_service.py    # 収集サービス統合
│
├── models/
│   └── market_data.py          # データモデル定義
│
├── mql5/                       # MQL5ファイル（MT5にコピーして使用）
│   ├── HorizontalLinesExporter.mq5  # 水平線エクスポートIndicator
│   ├── ChartExporterEA.mq5          # スクリーンショットEA（推奨）
│   └── ChartExporter.mq5            # スクリーンショットIndicator（非推奨）
│
├── data/                       # 収集データ保存先
│   ├── screenshots/
│   ├── training/
│   ├── actions/
│   ├── thoughts/
│   └── sessions/               # セッションデータ
│
├── templates/
│   ├── index.html              # メインWebフロントエンド
│   └── sessions.html           # セッション閲覧ページ
│
└── docs/
    ├── system_overview.md      # このドキュメント
    ├── mt5_indicator_setup.md  # MT5セットアップ手順
    ├── session_management_plan.md # セッション管理実装計画
    └── CHANGELOG.md            # 変更履歴
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
- MT5でXAUUSDp等の銘柄が表示可能なこと
- MQL5ファイルがセットアップ済みであること（詳細: [mt5_indicator_setup.md](./mt5_indicator_setup.md)）
  - HorizontalLinesExporter（Indicator）
  - ChartExporterEA（Expert Advisor）
- MT5のアルゴリズム取引が有効（緑色）であること

---

## 将来の拡張計画

### Phase 1.5: セッション管理機能（実装完了）
→ 詳細: [session_management_plan.md](./session_management_plan.md)

- BUY → HOLD → SELL/STOP_LOSS を1セッションとして管理
- 各時間足（D1, H4, M15, M5, M1）のスクリーンショット
- HOLDも思考付きで記録
- E2E模倣学習用データ収集

### Phase 2: E2E模倣学習
- PyTorch Dataset/DataLoader
- CNN/ViTモデル構築
- 学習・推論パイプライン
- **リアルタイムエントリーポイント判断**

### Phase 3: ルールベース判定
- テクニカル指標ルールエンジン
- エントリー条件YAML定義
- シグナル生成
- **リアルタイムエントリーポイント判断**

---

## 最重要: リアルタイムエントリーポイント判断

**模倣学習/推論またはルールベースにおいて、リアルタイムのデータでエントリーポイント（買いと売り）を判断することが非常に重要である。**

### 目標

```
┌─────────────────────────────────────────────────────────────┐
│ リアルタイムデータ入力                                        │
│ ├── OHLC (MT5 API)                                          │
│ ├── 水平線 (MQL5 Indicator)                                 │
│ └── スクリーンショット (ChartExporterEA)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 判断エンジン                                                 │
│ ├── E2E模倣学習モデル (CNN/ViT)                             │
│ └── ルールベースエンジン (テクニカル指標)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 出力: エントリーシグナル                                     │
│ ├── BUY（買いエントリー推奨）                               │
│ ├── SELL（売り決済推奨）                                    │
│ ├── HOLD（様子見）                                          │
│ └── STOP_LOSS（損切り推奨）                                 │
└─────────────────────────────────────────────────────────────┘
```

### データフロー

| Phase | 入力 | 処理 | 出力 |
|-------|------|------|------|
| Phase 1.5 | トレーダー操作 | データ収集・保存 | セッションデータ |
| Phase 2/3 | セッションデータ | 学習/ルール定義 | モデル/ルール |
| **推論時** | **リアルタイムデータ** | **モデル推論/ルール適用** | **エントリーシグナル** |

### Phase 4: マルチエージェントシステム
- MT5情報取得Agent
- 解析Agent
- 経済指標Agent
- 売買決定Agent
- システム管理Agent

---

## 作成日
2026年2月13日

## 最終更新日
2026年2月25日

## バージョン
1.4.1
