# back
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QListWidget, QAbstractItemView, QMessageBox, QSplitter, QLabel
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
        
        # 左右分割用のスプリッター
        splitter = QSplitter(Qt.Horizontal)
        
        # 左側: 履歴リスト
        self.history_list = CustomListWidget(self)
        self.history_list.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # 右側: プレビューエリア
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(300, 200)
        self.preview_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
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

        self.load_history()

    def load_history(self):
        folder_history = self.settings.value("folder_history", [])
        # 存在するフォルダのみをフィルタリング
        valid_folders = self.cleanup_invalid_folders(folder_history)
        self.history_list.addItems(valid_folders)
        
        # 無効なフォルダが除外された場合は設定を更新
        if len(valid_folders) != len(folder_history):
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
        if folder_path not in [self.history_list.item(i).text() for i in range(self.history_list.count())]:
            self.history_list.addItem(folder_path)

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
            image_files = [f for f in os.listdir(folder_path) 
                          if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
            
            if not image_files:
                self.preview_label.setText("画像ファイルがありません")
                return
            
            # 最初の画像を読み込み
            first_image = os.path.join(folder_path, image_files[0])
            image = Image.open(first_image)
            
            # プレビューサイズに合わせてリサイズ
            preview_size = (280, 180)  # プレビューエリアより少し小さく
            image.thumbnail(preview_size, Image.Resampling.LANCZOS)
            
            # QPixmapに変換して表示
            image_rgba = image.convert("RGBA")
            w, h = image.size
            qimage = QImage(image_rgba.tobytes("raw", "RGBA"), w, h, QImage.Format_RGBA8888)
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
        self.viewer.load_images(folder_path)
        # ビューアータブに自動切り替え
        self.viewer.tabs.setCurrentIndex(0)

    def refresh_history(self):
        """履歴を再読み込みして無効なフォルダを除外"""
        self.history_list.clear()
        self.load_history()
