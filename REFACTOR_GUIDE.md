# 分割・リファクタリング安全規則

本ドキュメントは、コードの分割・リファクタリング時に機能を破壊しないための手順と規則を定める。
コード分割は**設計作業ではなく、設計に基づく物理作業**である。

---

## 大原則

> **参照元を調べずにコードを分割してはならない**

コードは見た目以上に複雑な依存関係を持つ。
「動いているコード」を分割する際、以下を破壊しやすい：

- 読み込み順序・初期化順序
- 変数のスコープ
- モジュール間の暗黙の依存
- CSS の評価順序（Webの場合）

---

## フェーズ定義

分割・リファクタリングは必ず以下のフェーズに従って実施する。

### フェーズ0: 計画立案

**作業内容**: 分割の目的と範囲を明確化

```markdown
## 分割計画書
- 対象: storage.py（または storage.js）
- 目的: 肥大化したファイルの責務分離
- 分割後の構成:
  - storage/core.py  （永続化IO）
  - storage/library.py（ライブラリ管理）
  - storage/cloud.py （クラウド関連）
  - storage/__init__.py（再エクスポート）
- 既存APIの互換性: 維持する
```

### フェーズ1: 参照元調査（編集禁止）

**作業内容**: 依存関係の完全な把握。このフェーズでは**一切のコード編集を行わない**。

```bash
# 関数・変数の使用箇所を検索
grep -rn "function_name" src/ tests/

# インポート元を検索（Python）
grep -rn "from storage\|import storage" src/ tests/

# インポート元を検索（JS）
grep -rn "from.*storage" src/ assets/

# クラス名・IDの使用箇所を検索（Web）
grep -rn "className\|getElementById" src/ assets/ *.html
```

**成果物**: 参照元マップ（どこから何が参照されているか）

### フェーズ2: 参照元情報の付記

**作業内容**: 調査結果をコメントとして記録

```python
# [REF] 参照元情報
# - CALLER: main.py L45, sync_logic.py L120
# - IMPORT: ui.py, cloud_sync.py
# - DEPENDS: self._storage（__init__ で注入）
# - SPLIT: GROUP（core.py と同一ファイル必須）
def save_progress(self, book_id: str, progress: dict) -> None:
    ...
```

```javascript
/**
 * [REF] 参照元情報
 * - CALLER: app.js L123, sync-logic.js L456
 * - IMPORT: renderers.js, ui.js
 * - DEPENDS: _storage（init で注入）
 * - SPLIT: GROUP（core.js と同一ファイル必須）
 */
export function saveProgress(bookId, progress) { ... }
```

### フェーズ3: 分割計画の確定

**作業内容**: 具体的なファイル構成と移動計画

```markdown
## 移動計画

### storage/core.py へ移動
- __init__()
- load()
- save()
- export_data()
- import_data()

### storage/library.py へ移動
- upsert_book()
- add_bookmark()
- get_bookmarks()

### 移動順序
1. core.py を作成（他に依存されない関数から）
2. library.py を作成
3. __init__.py で再エクスポート
4. 既存の storage.py を削除
```

### フェーズ4: 物理分割（内容変更禁止）

**作業内容**: コードの移動のみ

**絶対禁止事項**:
- 関数名・変数名の変更
- ロジックの修正・改善
- フォーマットの変更
- 「ついでに」の修正

```python
# ✅ 正しい分割: 完全なコピー
# storage/core.py
def load(self):
    # 元のコードをそのままコピー
    ...

# ❌ 間違った分割: 変更を加えている
# storage/core.py
def load(self):
    # ここでリファクタリングしよう ← 禁止
    ...
```

### フェーズ5: インポートパスの更新

**作業内容**: 参照元のインポート文を更新

```python
# Before
from storage import save_progress

# After（__init__.py 経由）
from storage import save_progress  # __init__.py で再エクスポートすれば変更不要
# または
from storage.core import save_progress
```

```javascript
// Before
import { saveProgress } from "./storage.js";

// After（バレルファイル経由）
import { saveProgress } from "./storage/index.js";
```

### フェーズ6: 検証

- [ ] アプリケーションが起動するか
- [ ] 主要機能が動作するか
- [ ] エラーが出ていないか（コンソール / ログ / stderr）
- [ ] 初期化順序が維持されているか
- [ ] テストが通るか（テストがある場合）

---

## 危険な操作とその対策

### 危険度: 高

| 操作 | リスク | 対策 |
|------|--------|------|
| 初期化関数の移動 | 初期化順序の破壊 | 呼び出し元を全て確認、順序をドキュメント化 |
| グローバル変数・共有状態の分割 | 参照切れ | 全使用箇所を洗い出し、一括で移行 |
| CSSの順序変更（Web） | スタイル崩れ | 順序を絶対に変えない。[CSS_GUIDE.md](./CSS_GUIDE.md) 参照 |

### 危険度: 中

| 操作 | リスク | 対策 |
|------|--------|------|
| 関数名の変更 | 呼び出し元の漏れ | 全ファイル検索、一括置換 |
| ファイル名の変更 | インポートパスの不整合 | 全インポート文を検索・更新 |
| デフォルト値の変更 | 暗黙の依存の破壊 | 呼び出し元の引数を確認 |

### 危険度: 低

| 操作 | リスク | 対策 |
|------|--------|------|
| コメントの追加 | なし | - |
| 内部変数名の変更 | スコープ内なら低い | 関数内で完結していることを確認 |

---

## 分割作業のチェックリスト

### 作業前

- [ ] 分割の目的を明文化したか
- [ ] 参照元調査を完了したか
- [ ] 参照元コメントを付記したか
- [ ] 分割計画書を作成したか
- [ ] 既存APIの互換性方針を決めたか

### 作業中

- [ ] コードの内容を変更していないか（移動のみ）
- [ ] 順序を変更していないか
- [ ] 「ついでに」の修正をしていないか

### 作業後

- [ ] アプリケーションが起動するか
- [ ] 主要機能が動作するか
- [ ] エラーがないか
- [ ] 新規ファイルが再エクスポートされているか（JS: `index.js`、Python: `__init__.py`）
- [ ] ドキュメント（機能マップ等）を更新したか
- [ ] テストが通るか（存在する場合）

---

## 分割後のドキュメント更新

### 機能マップの更新/作成

```markdown
# storage/ 機能マップ（分割後）

## ファイル構成
- core.py: 永続化IO
- library.py: ライブラリCRUD
- cloud.py: クラウド連携
- __init__.py: 再エクスポート

## 依存関係
core ← library, cloud
       ↑
    __init__（公開）
```

### 変更履歴の記録

```markdown
## 2025-XX-XX storage.py 分割

### 変更内容
- storage.py を storage/ パッケージに分割
- 既存のインポートは __init__.py により互換性維持

### 影響範囲
- なし（APIは維持）

### 確認事項
- [x] 全機能の動作確認完了
```

---

## 中断・ロールバック手順

### 中断する場合

1. 作業中のファイルを一旦保存
2. 現在の状態をコミット（WIP: 作業中断）
3. 問題点を記録
4. ユーザーに報告

### ロールバックする場合

```bash
# 直前のコミットに戻す
git checkout HEAD -- path/to/file

# 特定のコミットに戻す
git checkout <commit-hash> -- path/to/file
```

---

## CSS分割の特別規則

CSSは評価順序に強く依存するため、追加の規則が適用される。
詳細は **[CSS_GUIDE.md](./CSS_GUIDE.md)** を参照。

要点：
- セレクタを変更してはならない
- プロパティ値を変更してはならない
- 元の出現順序を維持しなければならない
- `!important` を追加・削除してはならない

---

## 関連ドキュメント

- [CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md) - 基本原則
- [MODULE_GUIDE.md](./MODULE_GUIDE.md) - モジュール設計
- [COMMENT_GUIDE.md](./COMMENT_GUIDE.md) - 参照元コメントの書式
- [CSS_GUIDE.md](./CSS_GUIDE.md) - CSS分割の詳細規則（Web専用）
