import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QMessageBox, QSplitter, QLabel, QAbstractItemView
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
                self.parent_tab.open_selected_folder(current_item)
        else:
            super().keyPressEvent(event)

class FavoriteTab(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent = parent
        self.initUI()

    def initUI(self):
        # メインレイアウト
        main_layout = QVBoxLayout(self)
        
        # ツールバー（一括タグ付けボタン）
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
        
        # 左側: フォルダリストとボタン
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
        remove_button.clicked.connect(self.remove_selected_folder)
        left_layout.addWidget(remove_button)
        
        # 右側: プレビューエリア
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(300, 200)
        self.preview_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.preview_label.setText("フォルダを選択すると\nプレビューが表示されます")
        
        # スプリッターに追加
        splitter.addWidget(left_widget)
        splitter.addWidget(self.preview_label)
        splitter.setStretchFactor(0, 1)  # 左側
        splitter.setStretchFactor(1, 1)  # 右側
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # イベント接続
        self.favorite_list.itemDoubleClicked.connect(self.open_selected_folder)
        self.favorite_list.itemClicked.connect(self.show_preview)
        self.favorite_list.currentItemChanged.connect(self.on_selection_changed)
        self.favorite_list.itemSelectionChanged.connect(self.on_selection_changed_batch)

    def load_favorites(self):
        self.favorite_folders = self.settings.value("favorite_folders", [], type=list)
        self.favorite_list.clear()
        self.favorite_list.addItems(self.favorite_folders)

    def add_to_favorites(self, folder_path):
        if folder_path and folder_path not in self.favorite_folders:
            self.favorite_folders.append(folder_path)
            self.settings.setValue("favorite_folders", self.favorite_folders)
            self.favorite_list.addItem(folder_path)
        elif folder_path in self.favorite_folders:
            QMessageBox.information(self, "Information", "すでに登録済みです。")

    def remove_selected_folder(self):
        selected_items = self.favorite_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            folder_path = item.text()
            self.favorite_folders.remove(folder_path)
            self.favorite_list.takeItem(self.favorite_list.row(item))

        self.settings.setValue("favorite_folders", self.favorite_folders)

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

    def open_selected_folder(self, item):
        folder_path = item.text()
        if folder_path and os.path.exists(folder_path):
            try:
                self.parent.load_images(folder_path)
                # ビューアータブに自動切り替え
                self.parent.tabs.setCurrentIndex(0)
            except Exception as e:
                QMessageBox.warning(self, "エラー", f"フォルダの読み込みに失敗しました:\n{folder_path}\n{str(e)}")
        else:
            QMessageBox.warning(self, "Error", "選択されたフォルダが存在しません")
    
    def toggle_selection_mode(self):
        """複数選択モードの切り替え"""
        if self.toggle_selection_button.isChecked():
            self.favorite_list.setSelectionMode(QAbstractItemView.MultiSelection)
            self.toggle_selection_button.setText("単一選択モード")
        else:
            self.favorite_list.setSelectionMode(QAbstractItemView.SingleSelection)
            self.toggle_selection_button.setText("複数選択モード")
            self.batch_tag_button.setEnabled(False)
    
    def on_selection_changed_batch(self):
        """選択状態が変わったらボタンの有効/無効を切り替え"""
        selected_count = len(self.favorite_list.selectedItems())
        
        # 複数選択モードかつ1個以上選択されている場合のみ有効
        if self.toggle_selection_button.isChecked() and selected_count >= 1:
            self.batch_tag_button.setEnabled(True)
            self.batch_tag_button.setText(f"🏷️ 選択した{selected_count}個のリストを一括タグ付け")
        else:
            self.batch_tag_button.setEnabled(False)
            self.batch_tag_button.setText("🏷️ 選択したリストを一括タグ付け")
    
    def batch_auto_tag_selected(self):
        """選択されたフォルダを一括タグ付け"""
        selected_items = self.favorite_list.selectedItems()
        
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
            f"以下の{len(valid_folders)}個のお気に入りリストを自動タグ付けキューに追加しますか？\n\n{folder_list_text}\n\n"
            f"※各フォルダごとに解析→適用が自動的に順次実行されます。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # parentの_process_batch_foldersメソッドを呼び出す
            self.parent._process_batch_folders(valid_folders)