import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QMessageBox

class FavoriteTab(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent = parent
        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.favorite_list = QListWidget(self)
        self.load_favorites()

        self.layout.addWidget(self.favorite_list)

        add_button = QPushButton("選択中リストを保存する", self)
        add_button.clicked.connect(self.parent.add_current_folder_to_favorites)
        self.layout.addWidget(add_button)

        remove_button = QPushButton("選択を削除する", self)
        remove_button.setStyleSheet("background-color: red; color: white;")
        remove_button.clicked.connect(self.remove_selected_folder)
        self.layout.addWidget(remove_button)

        self.setLayout(self.layout)

        self.favorite_list.itemDoubleClicked.connect(self.open_selected_folder)

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

    def open_selected_folder(self, item):
        folder_path = item.text()
        if folder_path and os.path.exists(folder_path):
            self.parent.load_images(folder_path)
        else:
            QMessageBox.warning(self, "Error", "選択されたフォルダが存在しません")