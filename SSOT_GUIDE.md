# SSOT（Single Source of Truth）実践ガイド

本ドキュメントは、コード内の定数・設定値・識別子を一元管理するための具体的な実践方法を定める。

---

## SSOTとは

**「すべての情報は唯一の場所で定義され、他はそこを参照する」** という原則。

### JavaScript の例

```
❌ 悪い例：同じ値が複数箇所に存在
  app.js:    const API_URL = "https://api.example.com";
  sync.js:   const API_URL = "https://api.example.com";

✅ 良い例：一箇所で定義し、他は参照
  constants/api.js: export const API_URL = "https://api.example.com";
  app.js:    import { API_URL } from "./constants/api.js";
  sync.js:   import { API_URL } from "./constants/api.js";
```

### Python の例

```
❌ 悪い例
  app.py:    API_URL = "https://api.example.com"
  sync.py:   API_URL = "https://api.example.com"

✅ 良い例
  config.py: API_URL = "https://api.example.com"
  app.py:    from config import API_URL
  sync.py:   from config import API_URL
```

---

## SSOT化の対象

### 必須（絶対にSSOT化する）

| カテゴリ | 例 | 理由 |
|----------|-----|------|
| URL・エンドポイント | API URL, CDN パス | 環境変更時に一括修正が必要 |
| 設定値・閾値 | タイムアウト秒数, 上限値, リトライ回数 | 調整時に漏れが発生 |
| 状態を表す文字列 | `"loading"`, `"error"` | タイポによるバグの温床 |
| ファイルパス | アセットパス, 出力先, ログ出力先 | 構成変更時に追従が必要 |
| DOM ID・セレクタ（Web） | `#viewer`, `.modal` | HTML変更時に不整合が発生 |

### 推奨（SSOT化が望ましい）

| カテゴリ | 例 | 判断基準 |
|----------|-----|----------|
| UI表示文字列 | ボタンラベル, メッセージ | 多言語対応の可能性があれば |
| CSSクラス名（Web） | `.active`, `.hidden` | JS/CSSの両方で使用する場合 |
| イベント名 | カスタムイベント, シグナル名 | 複数ファイルで発火/購読する場合 |
| DB テーブル名・カラム名 | `"users"`, `"created_at"` | クエリが複数箇所にある場合 |

### 例外（SSOT化不要）

| カテゴリ | 例 | 理由 |
|----------|-----|------|
| ローカル変数 | ループカウンタ | 関数内で完結 |
| 一時的な計算値 | 中間結果 | 再利用しない |
| 標準的な値 | `true`, `false`, `0`, `1` | 変更の可能性がない |

---

## 定数ファイルの構成パターン

### JavaScript：カテゴリ別ファイル + バレル（推奨）

```
constants/
├── index.js          # 再エクスポート（バレル）
├── api.js            # API関連
├── ui.js             # UI関連（DOM ID, クラス名）
├── storage.js        # ストレージ関連
├── timing.js         # タイミング関連（タイムアウト等）
└── formats.js        # フォーマット関連（MIME, 拡張子）
```

```javascript
// constants/index.js（バレルファイル）
export * from "./api.js";
export * from "./ui.js";
export * from "./storage.js";
export * from "./timing.js";
export * from "./formats.js";
```

### Python：config モジュール（推奨）

#### パターンA：単一 config.py（小〜中規模）

```python
# config.py
"""アプリケーション設定の一元管理"""

import os
from pathlib import Path

# --- パス ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# --- API ---
API_URL = os.getenv("API_URL", "https://api.example.com")
API_TIMEOUT_SEC = 30
MAX_RETRY_COUNT = 3

# --- アプリケーション ---
APP_NAME = "MyApp"
VERSION = "1.0.0"
```

#### パターンB：config パッケージ（大規模）

```
config/
├── __init__.py       # 再エクスポート
├── paths.py          # パス関連
├── api.py            # API関連
├── app.py            # アプリ設定
└── .env              # 環境変数（.gitignore対象）
```

```python
# config/__init__.py
from .paths import *
from .api import *
from .app import *
```

#### パターンC：dataclass による型安全な設定（推奨）

```python
# config.py
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class AppConfig:
    """アプリケーション設定（イミュータブル）"""
    app_name: str = "MyApp"
    version: str = "1.0.0"
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    api_url: str = "https://api.example.com"
    api_timeout_sec: int = 30
    max_retry: int = 3

# シングルトンとして使用
CONFIG = AppConfig()
```

### 環境変数の管理（共通）

```
# .env（.gitignore に含める）
API_KEY=sk-abc123...
DATABASE_URL=postgresql://user:pass@localhost/db

# .env.example（リポジトリに含める、値は空）
API_KEY=
DATABASE_URL=
```

```python
# Python: python-dotenv を使用
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ["API_KEY"]  # 必須（なければ例外）
DEBUG = os.getenv("DEBUG", "false").lower() == "true"  # 任意（デフォルトあり）
```

---

## 定数の命名規則

### JavaScript

```javascript
// 単一値：UPPER_SNAKE_CASE
export const API_TIMEOUT_MS = 5000;

// 関連する値のグループ：Object.freeze()
export const THEME_MODES = Object.freeze({
  DARK: "dark",
  LIGHT: "light",
});
```

### Python

```python
# 単一値：UPPER_SNAKE_CASE
API_TIMEOUT_SEC = 30

# 関連する値のグループ：Enum（推奨）
from enum import Enum

class ThemeMode(Enum):
    DARK = "dark"
    LIGHT = "light"

# または frozen dataclass
@dataclass(frozen=True)
class Timeouts:
    API_SEC: int = 30
    SAVE_SEC: int = 5
```

---

## 定数追加時の手順

### 1. 既存定数の確認

```bash
# JS
grep -r "追加したい値" src/ constants/

# Python
grep -r "追加したい値" src/ config.py
```

### 2. 適切なカテゴリの選択

| 追加する定数 | JS 配置先 | Python 配置先 |
|--------------|-----------|--------------|
| API URL, エンドポイント | `constants/api.js` | `config.py` (API セクション) |
| ファイルパス | `constants/paths.js` | `config.py` (パス セクション) |
| タイムアウト, 間隔 | `constants/timing.js` | `config.py` (タイミング セクション) |
| 環境依存値（キー等） | `.env` + `constants/` | `.env` + `config.py` |

### 3. 利用側の更新

```javascript
// JS
import { AUTO_SAVE_DEBOUNCE_MS } from "./constants.js";
setTimeout(save, AUTO_SAVE_DEBOUNCE_MS);
```

```python
# Python
from config import AUTO_SAVE_INTERVAL_SEC
time.sleep(AUTO_SAVE_INTERVAL_SEC)
```

---

## ハードコーディングの発見と修正

### 発見方法

```bash
# マジックナンバーの検索
grep -rn "[0-9]\{3,\}" src/ --include="*.js" --include="*.py" | grep -v "config\|constants"

# 直接書かれたURLの検索
grep -rn 'http://\|https://' src/ --include="*.js" --include="*.py" | grep -v "config\|constants"

# Python: 直接書かれたファイルパス
grep -rn "open(\|Path(" src/ --include="*.py" | grep -v "config"
```

---

## SSOT監査チェックリスト

### コード内のハードコーディング

- [ ] URL・エンドポイントが直接書かれていないか
- [ ] タイムアウト値が数値リテラルで書かれていないか
- [ ] 状態文字列（`"loading"` 等）が直接書かれていないか
- [ ] ファイルパスが直接書かれていないか
- [ ] 機密情報がソースコードに含まれていないか

### 定数ファイルの健全性

- [ ] 同じ値が複数の定数に定義されていないか
- [ ] 未使用の定数が残っていないか
- [ ] イミュータブル保護がされているか（JS: `Object.freeze()`、Python: `frozen=True` / `Enum`）
- [ ] 各定数にコメント（用途説明）があるか

### バレル/再エクスポートの整合性

- [ ] 新規追加したファイルが再エクスポートされているか（JS: `index.js`、Python: `__init__.py`）
- [ ] 削除したファイルが除去されているか

---

## 関連ドキュメント

- [CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md) - 基本原則
- [COMMENT_GUIDE.md](./COMMENT_GUIDE.md) - 定数へのコメント付与規則
