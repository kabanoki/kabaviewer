# back
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QListWidget, QAbstractItemView

class HistoryTab(QWidget):
    def __init__(self, settings, viewer):
        super().__init__()
        self.settings = settings
        self.viewer = viewer
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.history_list = QListWidget(self)
        self.history_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_list.itemDoubleClicked.connect(self.load_selected_folder)
        self.layout.addWidget(self.history_list)
        self.setLayout(self.layout)

        self.load_history()

    def load_history(self):
        folder_history = self.settings.value("folder_history", [])
        self.history_list.addItems(folder_history)

    def update_folder_history(self, folder_path):
        if folder_path not in [self.history_list.item(i).text() for i in range(self.history_list.count())]:
            self.history_list.addItem(folder_path)

        folder_history = [self.history_list.item(i).text() for i in range(self.history_list.count())]
        self.settings.setValue("folder_history", folder_history)

    def load_selected_folder(self, item):
        folder_path = item.text()
        self.viewer.stop_slideshow()
        self.viewer.load_images(folder_path)
