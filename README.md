# KabaViewer

PyQt5で作成されたシンプルで使いやすい画像ビューアアプリケーションです。

## 特徴

- 🖼️ 様々な画像形式をサポート（PNG, JPG, GIF, BMPなど）
- ⭐ お気に入り機能で画像を管理
- 📝 閲覧履歴の記録と参照
- 🎯 直感的で使いやすいユーザーインターフェース
- 📱 クロスプラットフォーム対応

## システム要件

- Python 3.7以上
- PyQt5
- PIL (Pillow)

## インストール

### 1. リポジトリをクローン

```bash
git clone <repository-url>
cd kabaviewer
```

### 2. 仮想環境の作成と有効化

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate     # Windows
```

### 3. 依存関係のインストール

```bash
pip install PyQt5 Pillow
```

## 使用方法

### 基本的な使用方法

```bash
python main.py
```

### 実行ファイルの作成

PyInstallerを使用して実行ファイルを作成することができます：

```bash
pip install pyinstaller
pyinstaller main.spec
```

## ファイル構成

```
kabaviewer/
├── main.py           # メインアプリケーション
├── image_viewer.py   # 画像表示機能
├── favorite.py       # お気に入り機能
├── history.py        # 履歴機能
├── logo.png          # アプリケーションロゴ
├── main.spec         # PyInstallerビルド設定
└── KabaViewer.spec   # PyInstallerビルド設定（代替）
```

## 機能

### 画像表示
- 高品質な画像表示
- ズーム・パン機能
- 画像間の簡単なナビゲーション

### お気に入り管理
- 画像をお気に入りに追加/削除
- お気に入り一覧の表示と管理

### 閲覧履歴
- 最近閲覧した画像の自動記録
- 履歴からの素早いアクセス

## 開発

### 開発環境のセットアップ

```bash
# 開発用依存関係のインストール
pip install PyQt5 Pillow pyinstaller
```

### ビルド

```bash
# 開発版ビルド
pyinstaller --onefile main.py

# または設定ファイルを使用
pyinstaller main.spec
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

プルリクエストやイシューの報告を歓迎します。

## 作者

開発者: [あなたの名前]

---

## 更新履歴

- v1.0.0: 初回リリース
  - 基本的な画像表示機能
  - お気に入り機能
  - 履歴機能