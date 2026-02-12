# AI Coding Guidelines

AIによるコーディング作業において、コードの品質と安全性を確保するための汎用ガイドライン集です。

> **対象**: Webアプリ（HTML/CSS/JS）およびローカルアプリ（Python等）

## 目的

- **SSOT（Single Source of Truth）の徹底** - 定数の重複を防ぎ、保守性を確保
- **モジュール化とコメントの完備** - 機能追加や分割時の破壊を防止
- **ガイドラインの整備** - 以降の開発をスムーズに行うための基盤

## 使い方

### 新規プロジェクトへの導入

1. このリポジトリの内容（README.md以外）を**プロジェクトのルートにコピー**
2. プロジェクト固有の調整があれば各ガイドに追記

### AIへの指示

開発セッション開始時：
```
まず CORE_PRINCIPLES.md を読んでください。
その後、このプロジェクトの構造を確認し、既存パターンを把握してから作業を開始してください。
```

## ドキュメント構成

| ファイル | 内容 | 読むタイミング | 対象 |
|----------|------|----------------|------|
| [INDEX.md](./INDEX.md) | 目次・運用説明 | 最初に | 全体 |
| [CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md) | **基本原則（最重要）** | 毎回の作業開始時 | 全言語 |
| [SSOT_GUIDE.md](./SSOT_GUIDE.md) | 定数管理・SSOT実践 | 定数追加時 | 全言語 |
| [MODULE_GUIDE.md](./MODULE_GUIDE.md) | モジュール化・依存注入 | 機能追加時 | 全言語 |
| [COMMENT_GUIDE.md](./COMMENT_GUIDE.md) | コメント・ドキュメント規約 | 常時 | 全言語 |
| [REFACTOR_GUIDE.md](./REFACTOR_GUIDE.md) | 分割・リファクタリング全般 | コード整理時 | 全言語 |
| [CSS_GUIDE.md](./CSS_GUIDE.md) | CSS分割の詳細規則 | CSS改修時 | **Web専用** |

## 基本原則（概要）

詳細は [CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md) を参照。

### 絶対遵守事項

1. **SSOT の厳守** - 定数をコード内に直接記述しない
2. **既存構造の保護** - モジュール構造・初期化順序を破壊しない
3. **コメントによる意図の明示** - コメントなしでコードを追加しない
4. **変更前の確認義務** - 影響範囲を確認してから変更する
5. **環境・機密情報の分離** - APIキー等をソースコードに記述しない

## プロジェクトへの適用例

導入後のプロジェクト構成（ルート配置）：

```
your-project/
├── CORE_PRINCIPLES.md     ← AIが最初に発見しやすい
├── INDEX.md
├── SSOT_GUIDE.md
├── MODULE_GUIDE.md
├── COMMENT_GUIDE.md
├── REFACTOR_GUIDE.md
├── CSS_GUIDE.md           ← Webプロジェクトのみ
├── src/
├── tests/
├── config.py              ← Python の場合
├── .env                   ← 環境変数（.gitignore対象）
├── .env.example           ← テンプレート
└── README.md              ← プロジェクト固有の説明
```

**ルート配置を推奨する理由**：
- AIがプロジェクト構造を確認する際、最初に目に入る
- 「CORE_PRINCIPLES.md を読んで」という指示が簡潔
- 毎回読ませるファイルは発見しやすい場所に置くべき

## ライセンス

このガイドラインは自由に利用・改変できます。
