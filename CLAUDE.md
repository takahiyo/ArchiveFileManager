# ArchiveFileManager - Claude Code 設定

## プロジェクト概要

Windows向けアーカイブファイル一括変換・正規化GUIアプリケーション。
Python + Tkinter で構築。WinRAR を内部で利用し、ZIP / RAR / 7z 形式の相互変換、
拡張子修正、フォルダ階層正規化をバッチ処理で行う。

## 最上位ルール

**すべての作業の前に [CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md) を読むこと。**

- SSOT: 定数は `src/config.py` に集約。コード内にハードコーディング禁止
- 既存構造の保護: モジュール構造・初期化順序・依存関係を破壊しない
- コメント必須: 新規コードにはdocstring・コメントを付与
- 変更前確認: 影響範囲を `grep` / 参照元調査で確認してから変更
- 機密情報分離: ソースコードに秘密情報を含めない

## モジュール構成

```
src/
├── main.py              # エントリポイント（Tkinter root 生成）
├── config.py            # 定数・設定の一元管理（SSOT）
├── gui.py               # GUI層（ArchiveFileManagerGUI クラス）
├── archive_handler.py   # アーカイブ操作（展開・圧縮・変換・一括変換）
├── extension_fixer.py   # 拡張子検証・修正（マジックバイト判定）
└── folder_normalizer.py # フォルダ階層正規化
```

## 依存関係の方向

```
config.py（定数・設定）
    ↑
archive_handler.py / extension_fixer.py / folder_normalizer.py（コア機能）
    ↑
gui.py（UI層 — コールバック経由でコア機能を呼び出す）
    ↑
main.py（エントリポイント）
```

## エージェント構成

本プロジェクトでは4つの専門エージェントを定義し、役割分担で開発を進める。

| エージェント | 役割 | 担当範囲 |
|-------------|------|----------|
| **統括** | 全体管理 | 進捗管理、ルール遵守、タスク分解、品質統制 |
| **GUI** | UI設計・実装 | デザイン、操作性、視認性、レイアウト |
| **コア** | 機能実装 | アーカイブ処理、仕様実現、軽量化、拡張性 |
| **デバッガ** | 品質保証 | 障害想定、影響分析、テスト、修正 |

詳細は [agents/](./agents/) ディレクトリの各指示書を参照。

### エージェント連携フロー

```
1. 統括: 要件分析 → タスク分解 → 担当割り振り
2. コア / GUI: 並行して設計・実装
3. デバッガ: 変更ごとに影響分析・テスト
4. 統括: 成果物レビュー → 完了判定
```

### エージェント間のルール

- **統括**が常にタスクリスト（TodoWrite）を管理する
- 各エージェントは担当外のファイルを変更する前に**統括**に報告する
- **GUI** と **コア** の間のインターフェース変更は双方の合意が必要
- **デバッガ**は全エージェントの変更に対して影響分析を行う権限を持つ
- 既存ガイドライン（CORE_PRINCIPLES.md 等）は全エージェントが遵守する

## 開発ガイドライン参照先

| 作業内容 | 参照ドキュメント |
|----------|------------------|
| 基本原則 | [CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md) |
| 定数・設定の追加 | [SSOT_GUIDE.md](./SSOT_GUIDE.md) |
| 新機能の追加 | [MODULE_GUIDE.md](./MODULE_GUIDE.md) |
| コメント・ドキュメント | [COMMENT_GUIDE.md](./COMMENT_GUIDE.md) |
| コード分割・リファクタリング | [REFACTOR_GUIDE.md](./REFACTOR_GUIDE.md) |

## ビルド・テスト

```bash
# テスト実行
python test_logic.py

# ビルド（Windows exe 生成）
python build.py
```
