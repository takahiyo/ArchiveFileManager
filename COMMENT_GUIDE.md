# コメント・ドキュメント規約

本ドキュメントは、コード内のコメントおよびドキュメントの記述規則を定める。
適切なコメントは、AIによる後続の修正においてコードの破壊を防ぐ最重要の防衛線である。

---

## コメントの目的

1. **意図の伝達**: 「何をしているか」ではなく「なぜそうするか」
2. **制約の明示**: 変更してはいけない理由を伝える
3. **依存の記録**: 他のコードとの関係を明示する
4. **将来への引き継ぎ**: 次の修正者（AI含む）への情報提供

---

## ファイルヘッダーコメント

### JavaScript

```javascript
/**
 * sync-logic.js - 同期ロジック
 *
 * クラウド同期に関するビジネスロジックを集約する。
 * UIとの連携はコールバック経由で行い、
 * ストレージやクラウド同期インスタンスは初期化時に注入される。
 *
 * 依存: constants.js, i18n.js
 * 参照元: app.js（初期化）, renderers.js（UI描画時）
 */
```

### Python

```python
"""sync_logic.py - 同期ロジック

クラウド同期に関するビジネスロジックを集約する。
UIとの連携はコールバック経由で行い、
ストレージやクラウド同期インスタンスはコンストラクタで注入される。

依存: config, storage, cloud_sync
参照元: main.py（初期化）, ui.py（イベント経由）
"""
```

---

## セクション区切りコメント

関連する機能をグループ化する際に使用する。JS / Python 共通。

```python
# ============================================
# 定数定義
# ============================================

# ============================================
# 初期化
# ============================================

# ============================================
# 公開API
# ============================================

# ============================================
# 内部ヘルパー
# ============================================
```

---

## 関数ドキュメント

### JavaScript（JSDoc）

```javascript
/**
 * ライブラリエントリを構築
 *
 * クラウドとローカルのライブラリ情報を統合し、
 * 表示用のエントリリストを生成する。
 *
 * @param {string} uiLanguage - UI言語コード（"ja" | "en"）
 * @returns {Array<LibraryEntry>} ソート済みのライブラリエントリ
 *
 * @typedef {Object} LibraryEntry
 * @property {string} type - "cloud" | "local"
 * @property {string} title - 書籍タイトル
 * @property {number} progressPercentage - 進捗（0-100）
 */
export function buildLibraryEntries(uiLanguage) {
  // ...
}
```

### Python（Google Style docstring + 型ヒント）

```python
def build_library_entries(ui_language: str) -> list[LibraryEntry]:
    """ライブラリエントリを構築する。

    クラウドとローカルのライブラリ情報を統合し、
    表示用のエントリリストを生成する。

    Args:
        ui_language: UI言語コード（"ja" | "en"）

    Returns:
        最終更新日時の降順でソート済みのライブラリエントリ。

    Raises:
        ValueError: ui_language が未対応の場合。
    """
    ...
```

> **規約**: Python では **Google Style docstring** を標準とする。型情報は型ヒントに任せ、docstring では説明に集中する。

### Python 型ヒントの基本

```python
from typing import Optional
from pathlib import Path

def load_data(file_path: Path, encoding: str = "utf-8") -> dict:
    """データファイルを読み込む。"""
    ...

def find_user(user_id: int) -> Optional[User]:
    """ユーザーを検索する。見つからない場合は None。"""
    ...
```

### Python dataclass の docstring

```python
@dataclass
class LibraryEntry:
    """ライブラリの1エントリを表す。

    Attributes:
        entry_type: "cloud" | "local"
        title: 書籍タイトル
        progress: 進捗率（0-100）
    """
    entry_type: str
    title: str
    progress: float
```

---

## 警告・注意コメント

### 変更禁止の明示

```python
# ⚠️ WARNING: この順序を変更してはならない
# 理由: storageの初期化がcloud_syncより先である必要がある
storage = StorageService(db_path)
cloud_sync = CloudSync(storage=storage)
```

### 依存関係の明示

```python
# ⚠️ DEPENDENCY: この関数は ui モジュールの display に依存
# display が None の場合、早期リターンする
def show_modal(content):
    if not _display:
        return
    ...
```

### 暫定実装の明示

```python
# TODO: 暫定実装 - APIv2リリース後に修正予定
# 現在はv1のレスポンス形式を前提としている
def parse_response(data):
    return data["result"]  # v2では data["payload"] になる予定
```

---

## 参照元情報の付記

### CSS用（Web、分割時の安全確保）

```css
/* =====================================
[REF]
- HTML: #viewer 内の img 要素に適用
- JS: reader.js で .zoomed クラスを付与
- STATE: 画像ズーム時のみ有効
- LAYER: z-index: 100（モーダルより下）
- SPLIT: GROUP（.viewer-container と同一ファイル必須）
===================================== */
.viewer-image.zoomed {
  transform: scale(2);
  z-index: 100;
}
```

### JS / Python 用（関数の依存明示）

```javascript
/**
 * 進捗バーを更新
 *
 * [REF]
 * - DOM: DOM_IDS.PROGRESS_FILL, DOM_IDS.PROGRESS_THUMB
 * - STATE: _state.pageDirection により RTL/LTR が切り替わる
 * - CALLER: app.js の onProgress コールバックから呼び出し
 */
```

```python
def update_progress_bar(percentage: float) -> None:
    """進捗バーを更新する。

    [REF]
    - CALLER: main.py の on_progress コールバックから呼び出し
    - DEPENDS: self._display（init 時に注入）
    - STATE: self._direction により RTL/LTR が切り替わる
    """
    ...
```

---

## コメントの禁止事項

### 書いてはいけないコメント

```python
# ❌ コードをそのまま言い換えただけ
# iを1増やす
i += 1

# ❌ 自明な処理の説明
# リストをループ
for item in items:
    ...

# ❌ 古い情報を残したまま
# このAPIは非推奨（2023年に削除予定）← 実際は2025年で未削除
```

### 書くべきコメント

```python
# ✅ なぜその処理が必要かを説明
# macOS ではファイル名の正規化が異なるため、NFD→NFC変換が必要
normalized = unicodedata.normalize("NFC", filename)

# ✅ 非自明な値の根拠
# 300ms: iOS Safari のダブルタップ判定を避けるための遅延
TAP_DELAY_MS = 300

# ✅ エッジケースの説明
# 空リストの場合は早期リターン（後続の reduce が例外を投げるため）
if not items:
    return None
```

---

## ドキュメントファイルの作成基準

| 状況 | 作成するドキュメント |
|------|----------------------|
| 新規モジュール追加 | 機能マップ（`docs/モジュール名-map.md`） |
| 複雑な初期化順序 | 境界整理（`docs/初期化名-boundaries.md`） |
| 分割作業の実施 | 分割計画（作業前）+ 完了報告（作業後） |
| API/インターフェース変更 | 変更履歴（CHANGELOG.md） |

---

## コメント更新の義務

### コード変更時のルール

1. **関数の動作を変更したら**、JSDoc / docstring も更新すること
2. **依存関係を変更したら**、[REF]コメントも更新すること
3. **ファイルの責務を変更したら**、ヘッダーコメントも更新すること
4. **TODOを解消したら**、TODOコメントを削除すること

### 整合性チェック

コードとコメントの不整合は、誤った修正を誘発する最大の原因である。
コメントが古い場合は、**コメントを削除する方がまだ安全**である。

---

## 関連ドキュメント

- [CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md) - コメント必須の原則
- [MODULE_GUIDE.md](./MODULE_GUIDE.md) - JSDoc型定義 / Python型ヒントの詳細
- [REFACTOR_GUIDE.md](./REFACTOR_GUIDE.md) - 分割時の参照元コメント
