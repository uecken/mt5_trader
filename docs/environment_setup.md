# 実行環境セットアップガイド

## 動作確認済み環境

| 項目 | バージョン |
|------|-----------|
| OS | Windows 11 Home |
| Python | 3.11+ |
| MetaTrader 5 | Build 4620+ |

---

## 必要条件

### システム要件

- **OS**: Windows 10/11 (64-bit) **必須**
- **RAM**: 8GB以上推奨
- **ストレージ**: 1GB以上（セッションデータ用）

### ソフトウェア要件

1. **MetaTrader 5** - 公式サイトまたはブローカーからインストール
2. **Python 3.11+** - [python.org](https://www.python.org/)
3. **Git** - バージョン管理用（オプション）

---

## Python依存関係

### requirements.txt

```
# MT5連携（Windows専用）
MetaTrader5

# Webフレームワーク
fastapi
uvicorn[standard]

# データ処理
pandas

# スクリーンショット（Windows専用）
mss>=9.0.0                   # 画面キャプチャ
pillow>=10.0.0               # 画像処理
pywin32                      # Windows API
pyautogui>=0.9.54            # GUI自動化

# テクニカル分析
ta>=0.10.2                   # RSI, MACD, MA, BB

# 設定管理
pydantic>=2.0
pydantic-settings>=2.0
pyyaml>=6.0
python-dotenv>=1.0.0

# タイムゾーン
pytz>=2024.1
```

### インストール

```bash
pip install -r requirements.txt
```

---

## Windows専用コンポーネント

このシステムはWindows専用です。以下のコンポーネントがWindows APIに依存しています：

### 1. MetaTrader5 Pythonパッケージ

```python
import MetaTrader5 as mt5
```

- **理由**: MetaQuotes社の公式PythonパッケージはWindows専用
- **用途**: OHLC取得、ポジション監視、アカウント情報取得
- **代替**: なし（MT5自体がWindows専用）

### 2. Windows API (ctypes.windll)

```python
user32 = ctypes.windll.user32
user32.FindWindowW()
user32.GetWindowRect()
```

- **理由**: MT5ウィンドウの位置・サイズ取得
- **用途**: スクリーンショット範囲の特定
- **代替**: MQL5 ChartScreenShot()で代替可能（実装済み）

### 3. pywin32

```python
import win32gui
import win32con
```

- **理由**: 高度なウィンドウ操作
- **用途**: ウィンドウ検索、フォーカス制御
- **代替**: 基本的な機能はctypesで代替可能

### 4. APPDATAパス

```python
appdata = os.environ.get("APPDATA", "")
path = Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files"
```

- **理由**: MT5の共通ファイルフォルダへのアクセス
- **用途**: 水平線データ、スクリーンショット完了通知の読み取り
- **代替**: 環境変数で設定可能に変更すればLinux Wine環境でも動作可能

---

## Linux互換性分析

### 結論: **Linuxネイティブ動作は不可**

MetaTrader 5自体がWindows専用アプリケーションのため、このシステムはLinuxでネイティブ動作しません。

### 代替案

#### 案1: Wine + MT5 (実験的)

```
Linux
├── Wine 8.0+
│   └── MetaTrader 5
└── Python (ネイティブ)
    └── 本システム（修正必要）
```

**必要な修正:**
1. `MetaTrader5` パッケージ → Wine経由で動作させる必要あり
2. `ctypes.windll` → Wine環境で動作確認必要
3. `APPDATA` → Wineの仮想Windowsパスに変更
4. `pywin32` → 削除またはWine互換に変更

**制限事項:**
- MetaTrader5 Pythonパッケージ自体がWineで動作するか未検証
- パフォーマンス低下の可能性
- GUI自動化（pyautogui）が正常動作しない可能性

#### 案2: リモートデータ収集（推奨）

```
Windows Server/VM
├── MetaTrader 5
└── 本システム（データ収集のみ）
    └── API経由でデータ送信

Linux Server
├── FastAPI（Web UI）
├── データベース
└── 機械学習処理
```

**メリット:**
- Windows依存部分を最小化
- 学習・推論処理をLinux GPUサーバーで実行可能
- スケーラビリティ向上

**実装方法:**
1. Windows側: データ収集 → JSON/DBに保存 → API公開
2. Linux側: APIからデータ取得 → 学習・推論

#### 案3: Docker + Windows Container

```
Windows Host
└── Docker (Windows Containers)
    └── MT5 + 本システム
```

**制限事項:**
- Windows Serverライセンスが必要
- MT5のGUI操作が困難

---

## 推奨構成

### 開発環境

```
Windows 11 Home/Pro
├── MetaTrader 5
├── Python 3.11 (venv)
├── VS Code
└── 本システム
```

### 本番環境（将来）

```
┌─────────────────────────────────────┐
│ Windows VM (Azure/AWS/GCP)          │
│ ├── MetaTrader 5                    │
│ └── Data Collector (本システム)     │
│     └── API: POST /api/sessions     │
└──────────────┬──────────────────────┘
               │ HTTPS
┌──────────────┴──────────────────────┐
│ Linux Server (GPU)                  │
│ ├── FastAPI (Web UI)                │
│ ├── PostgreSQL (セッションDB)       │
│ └── PyTorch (学習・推論)            │
└─────────────────────────────────────┘
```

---

## トラブルシューティング

### MetaTrader5パッケージがインストールできない

```bash
# Python 64-bit が必要
python --version  # Python 3.11.x
python -c "import struct; print(struct.calcsize('P') * 8)"  # 64

# 再インストール
pip uninstall MetaTrader5
pip install MetaTrader5
```

### MT5に接続できない

```python
import MetaTrader5 as mt5
mt5.initialize()
print(mt5.last_error())  # エラー確認
```

**よくある原因:**
1. MT5が起動していない
2. MT5が別のPythonプロセスに接続中
3. アルゴリズム取引が無効

### pywin32のインポートエラー

```bash
pip uninstall pywin32
pip install pywin32
python -c "import win32gui"  # 確認
```

---

## 関連ドキュメント

- [MT5セットアップ手順](mt5_indicator_setup.md)
- [システム概要](system_overview.md)
- [変更履歴](CHANGELOG.md)

---

## 作成日
2026年2月25日

## 最終更新日
2026年2月25日
