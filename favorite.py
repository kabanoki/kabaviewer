import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QMessageBox, QSplitter, QLabel, QAbstractItemView, QListWidgetItem,
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt
from PIL import Image


class CustomListWidget(QListWidget):
    """エンターキーでアイテム選択できるカスタムリストウィジェット"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_tab = parent

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            current_item = self.currentItem()
            if current_item and self.parent_tab:
                self.parent_tab.open_selected_entry(current_item)
        else:
            super().keyPressEvent(event)


class FavoriteTab(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent = parent
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)

        # ツールバー
        toolbar_layout = QHBoxLayout()

        self.batch_tag_button = QPushButton("🏷️ 選択したリストを一括タグ付け")
        self.batch_tag_button.clicked.connect(self.batch_auto_tag_selected)
        self.batch_tag_button.setEnabled(False)

        self.toggle_selection_button = QPushButton("複数選択モード")
        self.toggle_selection_button.setCheckable(True)
        self.toggle_selection_button.clicked.connect(self.toggle_selection_mode)

        toolbar_layout.addWidget(self.toggle_selection_button)
        toolbar_layout.addWidget(self.batch_tag_button)
        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        # 左右分割用のスプリッター
        splitter = QSplitter(Qt.Horizontal)

        # 左側: エントリリストとボタン
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.favorite_list = CustomListWidget(self)
        self.favorite_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.load_favorites()
        left_layout.addWidget(self.favorite_list)

        add_button = QPushButton("選択中リストを保存する")
        add_button.clicked.connect(self.parent.add_current_folder_to_favorites)
        left_layout.addWidget(add_button)

        remove_button = QPushButton("選択を削除する")
        remove_button.setStyleSheet("background-color: red; color: white;")
        remove_button.clicked.connect(self.remove_selected_entry)
        left_layout.addWidget(remove_button)

        # 右側: プレビューエリア
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(300, 200)
        self.preview_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.preview_label.setText("フォルダを選択すると\nプレビューが表示されます")

        splitter.addWidget(left_widget)
        splitter.addWidget(self.preview_label)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # イベント接続
        self.favorite_list.itemDoubleClicked.connect(self.open_selected_entry)
        self.favorite_list.itemClicked.connect(self.on_item_clicked)
        self.favorite_list.currentItemChanged.connect(self.on_selection_changed)
        self.favorite_list.itemSelectionChanged.connect(self.on_selection_changed_batch)

    # ------------------------------------------------------------------
    # データ読み書き
    # ------------------------------------------------------------------

    def _migrate_legacy(self):
        """旧 favorite_folders (list[str]) を favorite_entries (list[dict]) に移行"""
        legacy = self.settings.value("favorite_folders", [], type=list)
        if not legacy:
            return []
        entries = []
        for path in legacy:
            entries.append({"type": "folder", "name": os.path.basename(path), "path": path})
        return entries

    def _load_entries(self):
        """QSettings から favorite_entries を読み込む。旧データは自動移行。"""
        stored = self.settings.value("favorite_entries", None)
        if stored is None:
            migrated = self._migrate_legacy()
            if migrated:
                self.settings.setValue("favorite_entries", migrated)
            return migrated
        if isinstance(stored, list):
            return stored
        return []

    def _save_entries(self, entries):
        self.settings.setValue("favorite_entries", entries)

    def _entry_label(self, entry):
        if entry.get("type") == "tag_filter":
            return f"🏷️ {entry['name']}"
        return f"📁 {entry['name']}"

    def load_favorites(self):
        self.favorite_entries = self._load_entries()
        self.favorite_list.clear()
        for entry in self.favorite_entries:
            item = QListWidgetItem(self._entry_label(entry))
            item.setData(Qt.UserRole, entry)
            self.favorite_list.addItem(item)

    # ------------------------------------------------------------------
    # エントリ追加
    # ------------------------------------------------------------------

    def add_to_favorites(self, folder_path):
        """後方互換: フォルダパスから folder エントリを追加（名前はbasename）"""
        entry = {
            "type": "folder",
            "name": os.path.basename(folder_path),
            "path": folder_path,
        }
        self.add_entry(entry)

    def add_entry(self, entry):
        """エントリ dict を登録リストに追加する"""
        if not entry:
            return

        # 重複チェック
        for existing in self.favorite_entries:
            if existing.get("type") == "folder" and entry.get("type") == "folder":
                if existing.get("path") == entry.get("path"):
                    QMessageBox.information(self, "情報", "すでに登録済みです。")
                    return
            elif existing.get("type") == "tag_filter" and entry.get("type") == "tag_filter":
                if (existing.get("name") == entry.get("name")
                        and set(existing.get("search_tags", [])) == set(entry.get("search_tags", []))
                        and set(existing.get("exclude_tags", [])) == set(entry.get("exclude_tags", []))
                        and existing.get("match_all") == entry.get("match_all")
                        and existing.get("only_favorites") == entry.get("only_favorites")):
                    QMessageBox.information(self, "情報", "同じ検索条件がすでに登録済みです。")
                    return

        self.favorite_entries.append(entry)
        self._save_entries(self.favorite_entries)
        item = QListWidgetItem(self._entry_label(entry))
        item.setData(Qt.UserRole, entry)
        self.favorite_list.addItem(item)

    # ------------------------------------------------------------------
    # エントリ削除
    # ------------------------------------------------------------------

    def remove_selected_entry(self):
        selected_items = self.favorite_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            entry = item.data(Qt.UserRole)
            if entry in self.favorite_entries:
                self.favorite_entries.remove(entry)
            self.favorite_list.takeItem(self.favorite_list.row(item))
        self._save_entries(self.favorite_entries)

    # ------------------------------------------------------------------
    # エントリを開く
    # ------------------------------------------------------------------

    def open_selected_entry(self, item):
        entry = item.data(Qt.UserRole)
        if not entry:
            return

        if entry.get("type") == "folder":
            folder_path = entry.get("path", "")
            if folder_path and os.path.exists(folder_path):
                try:
                    self.parent.load_images(folder_path)
                    self.parent.tabs.setCurrentIndex(0)
                except Exception as e:
                    QMessageBox.warning(self, "エラー", f"フォルダの読み込みに失敗しました:\n{folder_path}\n{str(e)}")
            else:
                QMessageBox.warning(self, "エラー", "選択されたフォルダが存在しません")

        elif entry.get("type") == "tag_filter":
            if not hasattr(self.parent, "apply_saved_tag_filter"):
                QMessageBox.warning(self, "エラー", "タグシステムが利用できません。")
                return
            self.parent.apply_saved_tag_filter(entry)

    # ------------------------------------------------------------------
    # プレビュー
    # ------------------------------------------------------------------

    def on_item_clicked(self, item):
        entry = item.data(Qt.UserRole)
        if entry and entry.get("type") == "folder":
            self.show_folder_preview(entry.get("path", ""))
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("🏷️ タグ検索リスト\n(ダブルクリックで再検索・表示)")

    def on_selection_changed(self, current, previous):
        if current:
            self.on_item_clicked(current)

    def show_folder_preview(self, folder_path):
        if not folder_path or not os.path.exists(folder_path):
            self.preview_label.setText("フォルダが存在しません")
            return
        try:
            image_files = [f for f in os.listdir(folder_path)
                           if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
            if not image_files:
                self.preview_label.setText("画像ファイルがありません")
                return
            first_image = os.path.join(folder_path, image_files[0])
            image = Image.open(first_image)
            preview_size = (280, 180)
            image.thumbnail(preview_size, Image.Resampling.LANCZOS)
            image_rgba = image.convert("RGBA")
            w, h = image.size
            qimage = QImage(image_rgba.tobytes("raw", "RGBA"), w, h, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            self.preview_label.setPixmap(pixmap)
        except Exception as e:
            self.preview_label.setText(f"プレビュー読み込みエラー:\n{str(e)}")

    # ------------------------------------------------------------------
    # 複数選択・一括タグ付け
    # ------------------------------------------------------------------

    def toggle_selection_mode(self):
        if self.toggle_selection_button.isChecked():
            self.favorite_list.setSelectionMode(QAbstractItemView.MultiSelection)
            self.toggle_selection_button.setText("単一選択モード")
        else:
            self.favorite_list.setSelectionMode(QAbstractItemView.SingleSelection)
            self.toggle_selection_button.setText("複数選択モード")
            self.batch_tag_button.setEnabled(False)

    def on_selection_changed_batch(self):
        selected_count = len(self.favorite_list.selectedItems())
        if self.toggle_selection_button.isChecked() and selected_count >= 1:
            self.batch_tag_button.setEnabled(True)
            self.batch_tag_button.setText(f"🏷️ 選択した{selected_count}個のリストを一括タグ付け")
        else:
            self.batch_tag_button.setEnabled(False)
            self.batch_tag_button.setText("🏷️ 選択したリストを一括タグ付け")

    def batch_auto_tag_selected(self):
        selected_items = self.favorite_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "エラー", "フォルダが選択されていません。")
            return

        # folder エントリのみ対象
        selected_folders = []
        for item in selected_items:
            entry = item.data(Qt.UserRole)
            if entry and entry.get("type") == "folder":
                selected_folders.append(entry["path"])

        if not selected_folders:
            QMessageBox.warning(self, "エラー", "フォルダエントリが選択されていません。\nタグ検索リストは一括タグ付けの対象外です。")
            return

        valid_folders = [f for f in selected_folders if os.path.exists(f)]
        invalid_count = len(selected_folders) - len(valid_folders)

        if invalid_count > 0:
            QMessageBox.warning(
                self, "警告",
                f"{invalid_count}個のフォルダが存在しません。\n有効な{len(valid_folders)}個のフォルダのみを処理します。"
            )

        if not valid_folders:
            QMessageBox.warning(self, "エラー", "有効なフォルダがありません。")
            return

        folder_list_text = "\n".join([f"• {os.path.basename(folder)}" for folder in valid_folders])
        reply = QMessageBox.question(
            self, "確認",
            f"以下の{len(valid_folders)}個のお気に入りリストを自動タグ付けキューに追加しますか？\n\n{folder_list_text}\n\n"
            f"※各フォルダごとに解析→適用が自動的に順次実行されます。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            self.parent._process_batch_folders(valid_folders)
