# 変更履歴 (CHANGELOG)

## [1.4.1] - 2026-02-25

### ドキュメント更新 & バグ修正

#### 追加ファイル
- `README.md` - プロジェクトのメインREADME
- `docs/environment_setup.md` - 実行環境セットアップガイド（Linux互換性分析含む）
- `docs/images/` - スクリーンショット画像フォルダ
  - `main_interface.png` - メイン画面
  - `session_viewer.png` - セッション閲覧画面
  - `mt5_setup_complete.png` - MT5セットアップ完了画面

#### 変更ファイル
- `docs/system_overview.md`
  - システム画面セクションを更新
  - H4取得本数を50本→180本に修正
  - snapshots構造にhorizontal_lines.json追加
  - シンボルをXAUUSDpに統一
- `docs/session_management_plan.md`
  - シンボルをXAUUSDpに修正
  - snapshots構造にhorizontal_lines.json追加
- `docs/mt5_indicator_setup.md` - MT5セットアップ画面のスクリーンショット追加
- `mql5/HorizontalLinesExporter.mq5` - `_copied_`水平線を除外
- `collector/horizontal_lines.py` - 重複水平線のフィルタリング追加
- `templates/sessions.html`
  - LightweightCharts v3.8.0に固定（API互換性）
  - インタラクティブチャート表示機能追加
- 全collectorファイル - タイムスタンプをUTCに統一

#### バグ修正
- セッション閲覧画面で水平線が重複表示される問題を修正
- `chart.addCandlestickSeries is not a function` エラーを修正
- 水平線の`_copied_`による重複問題を修正

---

## [1.4.0] - 2026-02-25

### ChartExporterEA & 水平線マルチチャート対応

**目的:** スクリーンショットにユーザー描画の水平線を含め、複数チャートの水平線を統合

#### 追加ファイル
- `mql5/ChartExporterEA.mq5` - Expert Advisor版スクリーンショットエクスポーター
  - ChartOpen()がインジケータで使用不可（Error 4105）のためEA化
  - 全開チャートから水平線を収集してスクリーンショットに含める

#### 変更ファイル
- `mql5/HorizontalLinesExporter.mq5`
  - 全開チャートの水平線をスキャン（同一銘柄）
  - ChartFirst()/ChartNext()で全チャート走査
- `mql5/ChartExporter.mq5`
  - 非推奨化（EA版を使用）
  - count=0時は完了ファイルを作成しないよう変更
- `collector/screen_capture.py`
  - EA版完了ファイル（`screenshot_complete_ea.txt`）を優先
  - Windowsパスのバックスラッシュエスケープ処理追加
  - 読み込み不可ファイルの自動削除（5回試行後）
- `templates/index.html`
  - MT5水平線ボタンの不要なアラート削除
  - `updateRecentData()` → `updateRecentSessions()` 修正
- `templates/sessions.html`
  - APIレスポンス構造の修正（`data.session`抽出）
  - スナップショットをセッション一覧の上に表示

#### デフォルトシンボル変更
以下のファイルでデフォルトシンボルを `XAUUSD` → `XAUUSDp` に変更:
- `config/settings.py`
- `app.py`
- `models/market_data.py`
- `collector/screen_capture.py`
- `collector/session_manager.py`
- `collector/collector_service.py`
- `collector/position_monitor.py`
- `collector/market_data_collector.py`

#### 機能詳細
- **水平線マルチチャート対応**: MT5で複数の時間足チャートを開いている場合、すべてのチャートから水平線を収集
- **スクリーンショットに水平線表示**: ChartExporterEAが他チャートの水平線をコピーしてからスクリーンショット取得
- **エンコーディング修正**: MQL5のFILE_ANSIとWindowsパス処理の互換性問題を解決

#### MT5設定（重要）
```
MQL5/
├── Experts/
│   └── ChartExporterEA.mq5  ← EAとしてアタッチ（アルゴ取引許可必要）
└── Indicators/
    └── HorizontalLinesExporter.mq5  ← インジケータとしてアタッチ
```

**ChartExporter.mq5（インジケータ版）は使用不可** - Error 4105が発生

---

## [1.3.0] - 2026-02-25

### Web UI改善 & セッションビューア

**目的:** UI改善と過去セッションの閲覧機能追加

#### 追加ファイル
- `templates/sessions.html` - セッション閲覧ページ
- `mql5/ChartExporter.mq5` - MQL5 ChartScreenShot()によるスクリーンショット

#### 変更ファイル
- `templates/index.html`
  - 時間足タブ切り替え機能（4チャート同時 → 1チャート + タブ）
  - MT5水平線自動更新（5秒毎）
- `app.py`
  - `/sessions` ページ追加
  - `/api/sessions/{id}/snapshots/{name}` エンドポイント追加
  - `/api/sessions/{id}/snapshots/{name}/image/{tf}` エンドポイント追加
- `collector/screen_capture.py`
  - MQL5ScreenCaptureクラス追加
  - フルスクリーンフォールバック無効化オプション追加
- `collector/session_manager.py`
  - 水平線をスナップショットに保存
- `models/market_data.py`
  - HorizontalLineDataモデル追加

#### 機能詳細
- **時間足切り替え**: H4/M15/M5/M1をタブボタンで切り替え
- **水平線自動更新**: 5秒毎にMT5から最新の水平線を取得
- **セッション閲覧**: `/sessions`で過去のセッションを閲覧可能
  - スナップショット詳細（思考、スクリーンショット、水平線、インジケーター）
  - チャートタブ / 数値データタブ切り替え

---

## [1.2.0] - 2026-02-25

### MT5水平線エクスポート機能

**目的:** MT5で手動描画した水平線をWebチャートに表示

#### 追加ファイル
- `mql5/HorizontalLinesExporter.mq5` - Indicator（チャート常駐、自動更新）
- `collector/horizontal_lines.py` - Python読み込みモジュール

#### 変更ファイル
- `app.py` - `/api/horizontal-lines` エンドポイント追加
- `templates/index.html` - 「MT5水平線を読込」ボタン追加

#### 削除ファイル
- `mql5/ExportHorizontalLines.mq5` - 旧Script版（Indicatorに置換）

#### 機能詳細
- **自動検知**: 水平線の作成/削除/移動をOnChartEvent()で検知
- **自動エクスポート**: イベント発生時 + 1秒毎にJSON更新
- **出力先**: `%APPDATA%\MetaQuotes\Terminal\Common\Files\horizontal_lines.json`

---

## [1.1.0] - 2026-02-25

### Web UI注意書き追加

**目的:** 自動売買機能がないことを明示

#### 変更ファイル
- `templates/index.html` - セッション管理パネルに注意書き追加

#### 注意書き内容
```
このシステムはデータ記録のみです。MT5での自動売買は行いません。
実際の売買はMT5で手動で行ってください。
```

---

## [1.0.0] - 2026-02-25

### セッション管理機能（Phase 1.5）

**目的:** BUY → HOLD → SELL/STOP_LOSS を1セッションとして管理し、E2E模倣学習用データを収集

#### 追加ファイル
- `collector/session_manager.py` - セッション管理モジュール
- `docs/session_management_plan.md` - 実装計画ドキュメント

#### 変更ファイル
- `models/market_data.py` - セッション関連モデル追加
  - `SessionStatus`, `SessionEntry`, `SessionExit`, `HoldRecord`, `TradingSession`
- `collector/screen_capture.py` - マルチタイムフレームキャプチャ機能
- `collector/market_data_collector.py` - OHLC取得本数調整
  - D1: 30本, H4: 180本, M15/M5/M1: 100本
- `collector/collector_service.py` - SessionManager統合
- `app.py` - セッション管理APIエンドポイント追加
- `templates/index.html` - セッション管理UIパネル追加
- `requirements.txt` - pyautogui追加
- `.gitignore` - data/ディレクトリをgit管理対象に変更
- `docs/system_overview.md` - Phase 1.5セクション追加

#### APIエンドポイント
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/sessions` | セッション一覧 |
| GET | `/api/sessions/active` | アクティブセッション取得 |
| GET | `/api/sessions/{session_id}` | セッション詳細 |
| POST | `/api/sessions/start` | セッション開始（BUY） |
| POST | `/api/sessions/hold` | HOLD追加 |
| POST | `/api/sessions/end` | セッション終了（SELL/STOP_LOSS） |

#### データ構造
```
data/sessions/
  session_YYYYMMDD_HHMMSS/
    session.json              # セッション全体の概要・結果
    snapshots/
      YYYYMMDD_HHMMSS_BUY/    # エントリー時点
        thought.json          # 思考
        market_data.json      # 全時間足のOHLC + 指標
        horizontal_lines.json # 水平線データ
        screenshots/
          D1.png, H4.png, M15.png, M5.png, M1.png
```

---

## [0.1.0] - 2026-02-13

### 初期リリース（Phase 1）

**目的:** MT5トレーダーの取引行動と思考を記録するデータ収集システム

#### 機能
- チャート表示（Lightweight Charts）
- スクリーンショット収集（30秒毎）
- マルチタイムフレームOHLCデータ取得
- テクニカル指標計算（RSI, MACD, SMA, EMA, BB）
- ポジション監視（1秒毎）
- アクション自動検出（BUY, SELL, STOP_LOSS, HOLD）
- 思考入力機能

#### ファイル構成
```
MT5/
├── app.py                      # FastAPI メインアプリケーション
├── mt5_data.py                 # MT5データ取得ユーティリティ
├── config/settings.py          # 設定管理
├── collector/                  # データ収集モジュール
│   ├── screen_capture.py
│   ├── market_data_collector.py
│   ├── position_monitor.py
│   ├── thought_input.py
│   ├── data_linker.py
│   └── collector_service.py
├── models/market_data.py       # データモデル定義
├── templates/index.html        # Webフロントエンド
└── docs/system_overview.md     # システム概要
```

---

## 将来の計画

### Phase 2: E2E模倣学習
- PyTorch Dataset/DataLoader
- CNN/ViTモデル構築
- 学習・推論パイプライン

### Phase 3: ルールベース判定
- テクニカル指標ルールエンジン
- エントリー条件YAML定義

### Phase 4: マルチエージェントシステム
- MT5情報取得Agent
- 解析Agent
- 経済指標Agent
- 売買決定Agent
