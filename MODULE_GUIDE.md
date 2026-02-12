# モジュール化・依存注入ガイド

本ドキュメントは、コードをモジュール化し、依存関係を安全に管理するための実践方法を定める。

---

## モジュール化の目的

1. **機能の独立性**: 各モジュールが単一の責務を持つ
2. **依存関係の明示**: 何が何に依存しているかが明確
3. **安全な変更**: 一部の変更が全体に波及しない
4. **テスト容易性**: モジュール単位でテスト可能

---

## 依存注入パターン

### JavaScript：init(config) パターン

モジュールは外部依存を `init()` 関数で受け取る。

```javascript
/**
 * sync-logic.js - 同期ロジック
 *
 * 外部依存はinit()で注入される。
 * 直接importによるグローバル依存は最小限にする。
 */

let _storage = null;
let _cloudSync = null;
let _callbacks = {};

/**
 * モジュールの初期化
 * @param {Object} config
 * @param {Object} config.storage - ストレージサービス
 * @param {Object} config.cloudSync - クラウド同期サービス
 * @param {Object} config.callbacks - UIコールバック群
 */
export function init(config) {
  _storage = config.storage;
  _cloudSync = config.cloudSync;
  _callbacks = config.callbacks ?? {};
}
```

### Python：コンストラクタ注入パターン（推奨）

```python
"""sync_logic.py - 同期ロジック

外部依存はコンストラクタで注入される。
"""

class SyncLogic:
    """同期処理を管理するクラス。

    Args:
        storage: ストレージサービス
        cloud_sync: クラウド同期サービス
        on_complete: 同期完了時コールバック（任意）
    """

    def __init__(self, storage, cloud_sync, on_complete=None):
        self._storage = storage
        self._cloud_sync = cloud_sync
        self._on_complete = on_complete

    def sync_data(self):
        """同期を実行する。"""
        if not self._storage or not self._cloud_sync:
            raise RuntimeError("依存が未設定です")
        # 処理...
```

### Python：関数ベースの注入（軽量な場合）

```python
"""converter.py - ファイル変換"""

from config import DEFAULT_OUTPUT_DIR

def convert_file(input_path, output_dir=None, *, formatter=None):
    """ファイルを変換する。

    Args:
        input_path: 入力ファイルのパス
        output_dir: 出力先ディレクトリ（デフォルト: config値）
        formatter: フォーマッタ関数（注入可能、テスト時に差し替え）
    """
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    fmt = formatter or _default_formatter
    # 処理...
```

---

## 初期化順序の重要性

### JavaScript

```javascript
// app.js - 初期化セクション

// ============================================
// Phase 1: 基盤サービス（依存なし）
// ============================================
const storage = new StorageService(STORAGE_KEY);

// ============================================
// Phase 2: 外部連携（storageに依存）
// ============================================
const cloudSync = new CloudSync();
cloudSync.init({ storage });

// ============================================
// Phase 3: ビジネスロジック（複数に依存）
// ============================================
syncLogic.init({ storage, cloudSync, callbacks: { ... } });

// ============================================
// Phase 4: UI層（全てに依存）
// ============================================
renderers.init({ storage, syncLogic, state: appState });
```

### Python

```python
# main.py - エントリポイント

from config import CONFIG
from storage import StorageService
from cloud_sync import CloudSync
from sync_logic import SyncLogic
from ui import UIController

def main():
    # --- Phase 1: 基盤サービス ---
    storage = StorageService(CONFIG.db_path)

    # --- Phase 2: 外部連携 ---
    cloud = CloudSync(storage=storage, api_url=CONFIG.api_url)

    # --- Phase 3: ビジネスロジック ---
    sync = SyncLogic(storage=storage, cloud_sync=cloud)

    # --- Phase 4: UI層 ---
    ui = UIController(sync_logic=sync)
    ui.run()

if __name__ == "__main__":
    main()
```

> **ポイント**: 依存される側から先に生成する。依存グラフを上流から下流へ辿る順序で初期化する。

---

## モジュール境界の設計

### 単一責務の原則

```
✅ 良い分割：
  storage.py       → データ永続化のみ
  cloud_sync.py    → クラウド通信のみ
  sync_logic.py    → 同期判断ロジックのみ
  ui.py            → UI描画のみ

❌ 悪い分割：
  utils.py         → 雑多な関数の集合
  helpers.py       → 何でも入りのファイル
```

### 循環依存の禁止

A → B → A のような循環依存を作ってはならない。

```python
# ❌ 循環依存（禁止）
# a.py
from b import func_b
def func_a(): func_b()

# b.py
from a import func_a  # 循環！
def func_b(): func_a()

# ✅ 解決策1: コールバックで解決
# a.py
def func_a(callback): callback()

# b.py
from a import func_a
def func_b(): ...
func_a(func_b)

# ✅ 解決策2: 共通モジュールに抽出
# common.py に共通処理を移動
```

---

## パッケージ構成パターン

### JavaScript（ESM）

```
src/
├── constants/
│   ├── index.js        # バレル（再エクスポート）
│   └── api.js
├── services/
│   ├── storage.js
│   └── cloud-sync.js
├── logic/
│   └── sync-logic.js
└── app.js              # エントリポイント
```

### Python

```
project/
├── config.py              # 設定の一元管理
├── main.py                # エントリポイント
├── services/
│   ├── __init__.py        # 再エクスポート
│   ├── storage.py
│   └── cloud_sync.py
├── logic/
│   ├── __init__.py
│   └── sync_logic.py
├── tests/
│   ├── test_storage.py
│   └── test_sync_logic.py
├── requirements.txt       # 依存パッケージ
└── .env                   # 環境変数（.gitignore対象）
```

> **`__init__.py` の役割**: Python におけるバレルファイル。パッケージの公開APIを制御する。

```python
# services/__init__.py
from .storage import StorageService
from .cloud_sync import CloudSync

__all__ = ["StorageService", "CloudSync"]
```

---

## インターフェース定義

### JavaScript（JSDoc）

```javascript
/**
 * @typedef {Object} StorageInterface
 * @property {function(string): Object} get_progress
 * @property {function(string, Object): void} set_progress
 */
```

### Python（型ヒント + Protocol）

```python
from typing import Protocol

class StorageInterface(Protocol):
    """ストレージサービスのインターフェース定義。"""

    def get_progress(self, book_id: str) -> dict: ...
    def set_progress(self, book_id: str, progress: dict) -> None: ...
```

### 最小インターフェースの原則

モジュールは必要最小限の依存だけを要求する。

```python
# ❌ 過剰な依存（storage全体を要求）
def format_progress(storage):
    return f"{storage.get_progress(book_id).percentage}%"

# ✅ 最小限の依存（必要な値だけを要求）
def format_progress(percentage: float) -> str:
    return f"{percentage}%"
```

---

## 新規モジュール追加の手順

### 1. 責務の明確化

```markdown
## 新モジュール: notification.py
- 責務: ユーザー通知の表示
- 依存: ui（表示先）, config（設定値）
- 公開API: show(), hide(), show_error()
```

### 2. 実装

```python
"""notification.py - 通知モジュール

ユーザーへの通知表示を一元管理する。
依存はコンストラクタで注入される。
"""

from config import NOTIFICATION_TIMEOUT_SEC

class NotificationService:
    """通知の表示・管理を行う。

    Args:
        display: 表示先インターフェース
    """

    def __init__(self, display):
        self._display = display

    def show(self, message: str, level: str = "info") -> None:
        """通知を表示する。"""
        self._display.render(message, level, timeout=NOTIFICATION_TIMEOUT_SEC)
```

### 3. 初期化順序への組み込み

```python
# main.py に追加
notification = NotificationService(display=ui)
```

### 4. 依存グラフの更新

既存の依存関係ドキュメントがあれば更新する。

---

## 依存関係のドキュメント化

新規モジュールまたは大きな変更時は、依存関係を文書化する。

```markdown
# notification.py 機能マップ

## 依存（コンストラクタで受け取る）
| 依存 | 型 | 用途 |
|------|-----|------|
| display | DisplayInterface | 表示先 |

## 公開API
| 関数 | 引数 | 戻り値 | 用途 |
|------|------|--------|------|
| show | message, level | None | 通知表示 |
| hide | - | None | 通知非表示 |

## 他モジュールからの参照
- main.py: 初期化
- sync_logic.py: 同期完了/エラー時に show() を呼び出し
```

---

## トラブルシューティング

### 共通

| 症状 | 確認ポイント |
|------|-------------|
| `undefined` / `AttributeError` | `init()` またはコンストラクタに必要な依存が渡されているか |
| 初期化エラー | 依存グラフの順序が正しいか |
| 変更が反映されない | キャッシュ、インポートパス、バレルファイルの再エクスポート |

### Python 固有

| 症状 | 確認ポイント |
|------|-------------|
| `ImportError` | `__init__.py` の存在、`sys.path` の設定 |
| 循環インポート | モジュール間の依存方向を見直す |
| 型エラー | `Protocol` / 型ヒントと実装の整合性 |

---

## 関連ドキュメント

- [CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md) - 基本原則
- [REFACTOR_GUIDE.md](./REFACTOR_GUIDE.md) - モジュール分割時の安全手順
- [COMMENT_GUIDE.md](./COMMENT_GUIDE.md) - JSDoc / docstring 記述規則
