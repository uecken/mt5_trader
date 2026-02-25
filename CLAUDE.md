# CLAUDE.md - プロジェクトコンテキスト

このファイルはClaude（AI）がプロジェクトを理解するためのコンテキストを提供します。

## プロジェクト概要

**MT5 Trader思考解析 & 売買システム** - MetaTrader 5トレーダーの取引行動と思考を記録し、E2E模倣学習に活用するためのデータ収集システム。

## 最重要目標

**リアルタイムのデータでエントリーポイント（買いと売り）を判断すること**

- 模倣学習/推論またはルールベースで判断
- 収集したデータを学習し、リアルタイムでBUY/SELL/HOLDを判断
- トレーダーの意思決定を再現・自動化

## 技術スタック

| カテゴリ | 技術 |
|---------|------|
| バックエンド | Python 3.11+, FastAPI, uvicorn |
| フロントエンド | HTML5, JavaScript, Lightweight Charts |
| MT5連携 | MetaTrader5 Python API, MQL5 |
| テクニカル分析 | ta (Technical Analysis Library) |
| データ形式 | JSON, PNG |

## 動作環境

- **Windows 10/11 (64-bit) 必須** - MetaTrader5 Python APIがWindows専用
- Linux/macOSでは動作しない（詳細: docs/environment_setup.md）

## ファイル構成

```
MT5/
├── app.py                      # FastAPI メインアプリケーション
├── requirements.txt            # Python依存関係
├── CLAUDE.md                   # このファイル
├── 条件.txt                    # トレード条件・分析方法
├── config/settings.py          # 設定管理
├── collector/                  # データ収集モジュール
│   ├── session_manager.py      # セッション管理（BUY→SELL）
│   ├── screen_capture.py       # スクリーンショット取得
│   ├── market_data_collector.py # OHLC + インジケーター取得
│   ├── horizontal_lines.py     # MT5水平線読み込み
│   └── collector_service.py    # 収集サービス統合
├── models/market_data.py       # Pydanticデータモデル
├── mql5/                       # MQL5ファイル（MT5用）
│   ├── HorizontalLinesExporter.mq5  # 水平線エクスポート
│   └── ChartExporterEA.mq5          # スクリーンショットEA
├── templates/                  # Webフロントエンド
│   ├── index.html              # メイン画面
│   └── sessions.html           # セッション閲覧
├── data/                       # 収集データ
│   ├── screenshots/            # 一時スクリーンショット（gitignore）
│   └── sessions/               # セッションデータ
└── docs/                       # ドキュメント
```

## 主要コンポーネント

### 1. セッション管理 (collector/session_manager.py)
- BUY → HOLD → SELL/STOP_LOSS を1セッションとして管理
- 各アクション時にスナップショット（スクリーンショット + OHLC + 水平線 + 思考）を保存

### 2. MQL5連携
- **HorizontalLinesExporter**: MT5で描画した水平線をJSON出力
- **ChartExporterEA**: 5時間足（D1/H4/M15/M5/M1）のスクリーンショット取得

### 3. データ収集
- OHLC: D1(30本), H4(180本), M15/M5/M1(100本)
- インジケーター: RSI, MACD, SMA(20/50), EMA(20), BB
- 水平線: 価格、色、名前
- スクリーンショット: 5時間足のPNG

## API エンドポイント

| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/ohlc` | OHLCデータ取得 |
| GET | `/api/horizontal-lines` | 水平線取得 |
| POST | `/api/sessions/start` | セッション開始（BUY） |
| POST | `/api/sessions/hold` | HOLD追加 |
| POST | `/api/sessions/end` | セッション終了（SELL/STOP_LOSS） |
| GET | `/api/sessions` | セッション一覧 |

## 開発フェーズ

| Phase | 状態 | 内容 |
|-------|------|------|
| 1.5 | ✅ 完了 | セッション管理・データ収集 |
| 2 | 🔜 次 | E2E模倣学習（PyTorch） |
| 3 | 📋 計画 | ルールベース判定 |
| 4 | 📋 計画 | マルチエージェントシステム |

## 重要な制約

1. **デフォルトシンボル**: `XAUUSDp`（ゴールド）
2. **タイムスタンプ**: すべてUTC
3. **水平線**: `_copied_` 接尾辞はフィルタリング（ChartExporterEAがコピーしたもの）
4. **スクリーンショット**: MQL5 ChartScreenShot()使用（Error 4105回避のためEA版必須）

## コーディング規約

- Python: PEP 8準拠
- 型ヒント使用（Pydanticモデル）
- ログ: logging モジュール使用
- エラーハンドリング: 適切な例外処理

## 関連ドキュメント

- [README.md](README.md) - プロジェクト概要
- [docs/system_overview.md](docs/system_overview.md) - システム詳細
- [docs/environment_setup.md](docs/environment_setup.md) - 環境構築
- [docs/mt5_indicator_setup.md](docs/mt5_indicator_setup.md) - MT5セットアップ
- [docs/session_management_plan.md](docs/session_management_plan.md) - セッション管理計画
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - 変更履歴
- [条件.txt](条件.txt) - トレード条件・分析方法
