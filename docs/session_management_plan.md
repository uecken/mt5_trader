# MT5 セッション管理機能 実装計画

**ステータス: 実装完了**

## Context

現在のシステムは各アクション（BUY/SELL/HOLD/STOP_LOSS）を個別JSONファイルとして保存している。
ユーザーは「BUY → SELL/STOP_LOSS」を1セッションとして扱い、その間のすべてのデータを統合して保存したい。

**目的：**
- 利益を出すトレーダーのデータを学習するため
- 将来的にリアルタイムチャートでエントリー/決済タイミングを推論またはルールベース判定させるため
- 将来的にWebで水平線ボタンを押すと自動推論した水平線を表示（今回は対象外）

**今回のスコープ：**
- データ収集機能の実装に集中
- 水平線の自動推論機能は将来フェーズ（収集データで学習後）

**重要な仕様：**
- 水平線はMT5で手動描画済み（自動描画不要）
- スナップショットはユーザー入力時（BUY/SELL/HOLD等）のみ取得（定期30秒毎ではない）
- OHLCデータは1ヶ月分を保存

---

## データ構造

### ディレクトリ構造
```
data/sessions/
  session_20260216_224703/
    session.json              # セッション全体の概要・結果
    snapshots/
      20260216_224703_BUY/    # エントリー時点
        thought.json          # 思考
        market_data.json      # 全時間足のOHLC + 指標
        screenshots/
          D1.png, H4.png, M15.png, M5.png, M1.png
      20260216_225000_HOLD/   # HOLD時点（思考付き）
        thought.json
        market_data.json
        screenshots/
          D1.png, H4.png, M15.png, M5.png, M1.png
      20260216_230500_SELL/   # 決済時点
        thought.json
        market_data.json
        screenshots/
          D1.png, H4.png, M15.png, M5.png, M1.png
```

### session.json
```json
{
  "session_id": "20260216_224703",
  "symbol": "XAUUSD",
  "status": "active" | "completed",

  "entry": {
    "time": "2026-02-16T22:47:03",
    "action": "BUY",
    "price": 2850.50,
    "thought": "15分足でダブルボトム確認"
  },

  "exit": {
    "time": "2026-02-17T01:30:00",
    "action": "SELL",
    "price": 2855.20,
    "thought": "4時間足のネックライン到達"
  },

  "holds": [
    {
      "time": "2026-02-16T22:50:00",
      "thought": "まだネックラインに到達していない、継続"
    },
    {
      "time": "2026-02-16T23:15:00",
      "thought": "1分足でリテスト確認、ポジション維持"
    }
  ],

  "result": {
    "duration_minutes": 163,
    "profit": 47.0,
    "profit_pips": 47
  },

  "snapshot_count": 5,
  "timeframes": ["D1", "H4", "M15", "M5", "M1"]
}
```

### OHLC取得本数
| 時間足 | 取得本数 | 備考 |
|-------|---------|-----|
| D1 | 30本 | 1ヶ月分 |
| H4 | 180本 | 1ヶ月分（6本/日 × 30日） |
| M15 | 100本 | 約1日分 |
| M5 | 100本 | 約8時間分 |
| M1 | 100本 | 約1.5時間分 |

---

## 実装ファイル

| ファイル | 変更内容 |
|---------|---------|
| `models/market_data.py` | セッション関連モデル追加 |
| `collector/session_manager.py` | **新規作成** - セッション管理 |
| `collector/screen_capture.py` | 全時間足キャプチャ機能追加 |
| `collector/market_data_collector.py` | OHLC取得本数を調整 |
| `collector/collector_service.py` | SessionManager統合 |
| `templates/index.html` | セッションUI追加 |
| `app.py` | セッションAPIエンドポイント追加 |

---

## API エンドポイント

### セッション管理
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/sessions` | セッション一覧 |
| GET | `/api/sessions/active` | アクティブセッション |
| GET | `/api/sessions/{session_id}` | セッション詳細 |
| POST | `/api/sessions/start` | セッション開始（BUY） |
| POST | `/api/sessions/hold` | HOLD追加 |
| POST | `/api/sessions/end` | セッション終了（SELL/STOP_LOSS） |

---

## 将来フェーズ（今回は対象外）

- **水平線の自動推論機能**
  - 収集したデータ（トレーダーの水平線入りスクリーンショット + OHLC）を使用
  - 機械学習で「どこに水平線を引くか」を予測
  - Webで「水平線ボタン」を押すと自動表示

---

## 作成日
2026年2月25日
