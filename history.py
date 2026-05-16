# back
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QListWidget, QAbstractItemView, QMessageBox, QSplitter, QLabel, QPushButton, QHBoxLayout
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
                self.parent_tab.load_selected_folder(current_item)
        else:
            super().keyPressEvent(event)

class HistoryTab(QWidget):
    def __init__(self, settings, viewer):
        super().__init__()
        self.settings = settings
        self.viewer = viewer
        self.init_ui()

    def init_ui(self):
        # メインレイアウト
        main_layout = QVBoxLayout(self)
        
        # ツールバー（一括タグ付けボタン）
        toolbar_layout = QHBoxLayout()
        
        self.batch_tag_button = QPushButton("🏷️ 選択したフォルダを一括タグ付け")
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
        
        # 左側: 履歴リスト
        self.history_list = CustomListWidget(self)
        self.history_list.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # 右側: プレビューエリア
        self.preview_label = QLabel()
        self.preview_label.setObjectName("PreviewLabel")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(300, 200)
        self.preview_label.setText("フォルダを選択すると\nプレビューが表示されます")
        
        # スプリッターに追加
        splitter.addWidget(self.history_list)
        splitter.addWidget(self.preview_label)
        splitter.setStretchFactor(0, 1)  # 左側
        splitter.setStretchFactor(1, 1)  # 右側
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # イベント接続
        self.history_list.itemDoubleClicked.connect(self.load_selected_folder)
        self.history_list.itemClicked.connect(self.show_preview)
        self.history_list.currentItemChanged.connect(self.on_selection_changed)
        self.history_list.itemSelectionChanged.connect(self.on_selection_changed_batch)

        self.load_history()
    
    def toggle_selection_mode(self):
        """複数選択モードの切り替え"""
        if self.toggle_selection_button.isChecked():
            self.history_list.setSelectionMode(QAbstractItemView.MultiSelection)
            self.toggle_selection_button.setText("単一選択モード")
        else:
            self.history_list.setSelectionMode(QAbstractItemView.SingleSelection)
            self.toggle_selection_button.setText("複数選択モード")
            self.batch_tag_button.setEnabled(False)
    
    def on_selection_changed_batch(self):
        """選択状態が変わったらボタンの有効/無効を切り替え"""
        selected_count = len(self.history_list.selectedItems())
        
        # 複数選択モードかつ2個以上選択されている場合のみ有効
        if self.toggle_selection_button.isChecked() and selected_count >= 1:
            self.batch_tag_button.setEnabled(True)
            self.batch_tag_button.setText(f"🏷️ 選択した{selected_count}個のフォルダを一括タグ付け")
        else:
            self.batch_tag_button.setEnabled(False)
            self.batch_tag_button.setText("🏷️ 選択したフォルダを一括タグ付け")
    
    def batch_auto_tag_selected(self):
        """選択されたフォルダを一括タグ付け"""
        selected_items = self.history_list.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "エラー", "フォルダが選択されていません。")
            return
        
        selected_folders = [item.text() for item in selected_items]
        
        # 存在チェック
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
        
        # 確認ダイアログ
        folder_list_text = "\n".join([f"• {os.path.basename(folder)}" for folder in valid_folders])
        reply = QMessageBox.question(
            self, "確認",
            f"以下の{len(valid_folders)}個のフォルダを自動タグ付けキューに追加しますか？\n\n{folder_list_text}\n\n"
            f"※各フォルダごとに解析→適用が自動的に順次実行されます。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # viewerの_process_batch_foldersメソッドを呼び出す
            self.viewer._process_batch_folders(valid_folders)

    def load_history(self):
        folder_history = self.settings.value("folder_history", []) or []
        # 存在するフォルダのみをフィルタリング
        valid_folders = self.cleanup_invalid_folders(folder_history)

        # 既存ユーザー向け一回限りの移行: 旧フォーマット（古い順）を
        # 新フォーマット（登録日順の降順 = 最新が先頭）に反転する
        if not self.settings.value("history_sort_migrated_desc", False, type=bool):
            valid_folders = list(reversed(valid_folders))
            self.settings.setValue("history_sort_migrated_desc", True)

        # 表示（最新が一番上）
        self.history_list.addItems(valid_folders)

        # 移行・無効除外を反映するため保存し直す
        self.settings.setValue("folder_history", valid_folders)

    def cleanup_invalid_folders(self, folder_list):
        """存在しないフォルダを履歴から除外する"""
        valid_folders = []
        removed_count = 0
        
        for folder_path in folder_list:
            if folder_path and os.path.exists(folder_path):
                valid_folders.append(folder_path)
            else:
                removed_count += 1
        
        # 削除されたフォルダがあった場合は通知
        if removed_count > 0:
            QMessageBox.information(
                self, 
                "履歴クリーンアップ", 
                f"存在しない {removed_count} 個のフォルダを履歴から削除しました。"
            )
        
        return valid_folders

    def update_folder_history(self, folder_path):
        """新規フォルダを登録日順の降順で追加する（最新が先頭）。"""
        existing = [self.history_list.item(i).text() for i in range(self.history_list.count())]
        if folder_path not in existing:
            # 先頭に挿入（最新を一番上に）
            self.history_list.insertItem(0, folder_path)

        folder_history = [self.history_list.item(i).text() for i in range(self.history_list.count())]
        self.settings.setValue("folder_history", folder_history)

    def show_preview(self, item):
        """選択されたフォルダの最初の画像をプレビュー表示"""
        folder_path = item.text()
        if not folder_path or not os.path.exists(folder_path):
            self.preview_label.setText("フォルダが存在しません")
            return
        
        try:
            # フォルダ内の画像ファイルを検索
            image_files = sorted([f for f in os.listdir(folder_path) 
                          if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))])
            
            if not image_files:
                self.preview_label.setText("画像ファイルがありません")
                return
            
            # 最初の画像を読み込み
            first_image = os.path.join(folder_path, image_files[0])
            with Image.open(first_image) as img:
                # プレビューサイズに合わせてリサイズ
                preview_size = (280, 180)  # プレビューエリアより少し小さく
                img.thumbnail(preview_size, Image.Resampling.LANCZOS)
                
                # QPixmapに変換して表示（バイト配列を変数に保持）
                image_rgba = img.convert("RGBA")
                w, h = image_rgba.size
                image_bytes = image_rgba.tobytes("raw", "RGBA")
                qimage = QImage(image_bytes, w, h, QImage.Format_RGBA8888).copy()
                pixmap = QPixmap.fromImage(qimage)
                
                self.preview_label.setPixmap(pixmap)
            
        except Exception as e:
            self.preview_label.setText(f"プレビュー読み込みエラー:\n{str(e)}")

    def on_selection_changed(self, current, previous):
        """選択項目変更時（キーボード操作含む）にプレビューを更新"""
        if current:
            self.show_preview(current)

    def load_selected_folder(self, item):
        folder_path = item.text()
        
        # フォルダの存在チェック
        if not os.path.exists(folder_path):
            QMessageBox.warning(
                self, 
                "エラー", 
                f"選択されたフォルダが存在しません：\n{folder_path}\n\n履歴を更新します。"
            )
            # 無効なフォルダを履歴から削除
            self.refresh_history()
            return
        
        self.viewer.stop_slideshow()
        try:
            self.viewer.load_images(folder_path)
            # ビューアータブに自動切り替え
            self.viewer.tabs.setCurrentIndex(0)
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"フォルダの読み込みに失敗しました:\n{folder_path}\n{str(e)}")

    def refresh_history(self):
        """履歴を再読み込みして無効なフォルダを除外"""
        self.history_list.clear()
        self.load_history()
