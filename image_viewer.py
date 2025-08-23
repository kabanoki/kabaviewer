# back
import os
import random
from PyQt5.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QComboBox, QTabWidget, QMenu, QFileDialog, QMessageBox, QAction, QInputDialog
from PyQt5.QtGui import QPixmap, QImage, QContextMenuEvent, QFont
from PyQt5.QtCore import Qt, QTimer, QSettings
from PIL import Image
from history import HistoryTab
from favorite import FavoriteTab

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.sort_order = ('random', True)
        self.current_image_index = 0
        self.initUI()

    def initUI(self):
        self.setWindowTitle("KabaViewer")
        self.setGeometry(100, 100, 800, 600)

        # 設定を保存するためのQSettingsオブジェクト
        self.settings = QSettings("MyCompany", "ImageViewerApp")

        # 保存されたスライドショーの速度を読み込む（デフォルトは3秒）
        last_speed = self.settings.value("slideshow_speed", 3, int)

        # タブウィジェットを作成
        self.tabs = QTabWidget(self)

        # 画像表示用のタブ
        self.image_tab = QWidget()
        self.image_layout = QVBoxLayout()
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumSize(800, 600)  # ラベルの最小サイズを固定
        self.image_layout.addWidget(self.label)
        self.image_tab.setLayout(self.image_layout)

        # メインレイアウトを作成
        self.main_layout = QVBoxLayout()
        # メッセージ表示用のラベルを作成
        self.message_label = QLabel(self)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("color: white; border-radius: 5px;")
        self.message_label.hide()  # 初期状態では非表示
        self.update_message_font_size()

        # メインウィジェットにレイアウトを設定
        central_widget = QWidget(self)
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

        # タイマー設定
        self.message_timer = QTimer(self)
        self.message_timer.setSingleShot(True)
        self.message_timer.timeout.connect(self.hide_message)


        # コントロール用のタブ
        self.control_tab = QWidget()
        self.control_layout = QVBoxLayout()

        self.start_button = QPushButton('Start Slideshow', self)
        self.start_button.clicked.connect(self.toggle_slideshow)

        self.combo_box = QComboBox(self)
        self.combo_box.addItems([f"{i} 秒" for i in range(1, 11)])
        self.combo_box.setCurrentIndex(last_speed - 1)
        self.combo_box.currentIndexChanged.connect(self.update_slideshow_speed)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addStretch()
        button_layout.addWidget(QLabel('Speed:'))
        button_layout.addWidget(self.combo_box)

        self.control_layout.addLayout(button_layout)
        self.control_layout.addStretch()  # 上に詰めるためのスペーサー

        self.control_tab.setLayout(self.control_layout)

        # お気に入りタブを作成
        self.favorite_tab = FavoriteTab(self.settings, self)

        # フォルダ履歴タブを作成
        self.history_tab = HistoryTab(self.settings, self)

        # タブに追加
        self.tabs.addTab(self.image_tab, "ビュアー")
        self.tabs.addTab(self.favorite_tab, "お気に入り")
        self.tabs.addTab(self.history_tab, "履歴")

        # メインレイアウトにタブを追加
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.images = []
        self.current_image_index = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_image)

        self.is_running = False

        # 最後に開いたフォルダを開くか、新しく選択する
        last_folder = self.settings.value("last_folder", "")
        if last_folder and os.path.exists(last_folder):  # ここで os.path.exists を使用
            try:
                self.load_images(last_folder)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load images from {last_folder}. Please select another folder.")
                self.select_folder()
        else:
            self.select_folder()

        # キーボードイベントの設定
        self.setFocusPolicy(Qt.StrongFocus)

        # メニューの設定
        self.init_menu()

    # クリックでスライドショーをトグルするメソッドを追加（ビューアータブ選択時のみ）
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.tabs.currentWidget() == self.image_tab:
            self.toggle_slideshow()

    def toggle_slideshow(self):
        if self.is_running:
            self.stop_slideshow()
        else:
            self.start_slideshow()

    def set_slideshow_speed(self, index):
        # 全てのチェックを外す
        for action in self.speed_actions:
            action.setChecked(False)
        # 選択した速度にチェックを入れる
        self.speed_actions[index].setChecked(True)
        # コンボボックスのインデックスを変更
        self.combo_box.setCurrentIndex(index)
        # スライドショーの速度を設定として保存
        self.settings.setValue("slideshow_speed", index + 1)
        # タイマーの速度を更新
        if self.timer.isActive():
            self.timer.start((index + 1) * 1000)

    def set_sort_order(self, sort_order):
        # 現在の並び順を設定
        self.sort_order = sort_order
        order_type, is_ascending = sort_order

        # 全てのアクションのチェックを外す
        for key, actions in self.sort_actions.items():
            ascending_action, descending_action = actions
            ascending_action.setChecked(False)
            descending_action.setChecked(False)

        # 現在選択されている順序のアクションにチェックを入れる
        if order_type != 'random':
            ascending_action, descending_action = self.sort_actions[order_type]
            if is_ascending:
                ascending_action.setChecked(True)
            else:
                descending_action.setChecked(True)

        # 画像を並び替える
        self.sort_images()

    def sort_images(self):
        order_type, is_ascending = self.sort_order

        if order_type == 'random':
            random.shuffle(self.images)
        else:
            reverse = not is_ascending
            if order_type == 'date_modified':
                self.images.sort(key=os.path.getmtime, reverse=reverse)
            elif order_type == 'date_added':
                self.images.sort(key=os.path.getctime, reverse=reverse)
            elif order_type == 'date_created':
                self.images.sort(key=os.path.getctime, reverse=reverse)
            elif order_type == 'name':
                self.images.sort(key=lambda x: os.path.basename(x).lower(), reverse=reverse)

        self.current_image_index = 0
        self.show_image()

    def set_sort_order_type(self, sort_type):
        self.sort_order = (sort_type.lower(), True)  # デフォルトは昇順
        # 他のチェックを外す
        for key in self.sort_actions:
            self.sort_actions[key].setChecked(key == sort_type)

        # ランダムの場合、昇順・降順を非表示
        if sort_type == 'ランダム':
            self.ascending_action.setVisible(False)
            self.descending_action.setVisible(False)
        else:
            self.ascending_action.setVisible(True)
            self.descending_action.setVisible(True)

        self.sort_images()

    def set_sort_order_ascending(self, is_ascending):
        order_type, _ = self.sort_order
        self.sort_order = (order_type, is_ascending)
        self.ascending_action.setChecked(is_ascending)
        self.descending_action.setChecked(not is_ascending)
        self.sort_images()

    def load_images(self, folder_path):
        try:
            # フォルダ内のファイルをリストアップ
            all_files = os.listdir(folder_path)
            # print(f"フォルダ内の全ファイル: {all_files}")  # デバッグ用出力

            self.images = [os.path.join(folder_path, f) for f in all_files
                           if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]

            # print(f"認識された画像ファイル: {self.images}")  # デバッグ用出力

            if not self.images:
                raise ValueError("No images found in the selected folder.")

            self.sort_images()
            self.show_image()
            self.settings.setValue("last_folder", folder_path)
            self.history_tab.update_folder_history(folder_path)
        except Exception as e:
            print(f"Error: {e}")  # エラーの内容を出力
            QMessageBox.warning(self, "Error",
                                f"Failed to load images from {folder_path}. Please select another folder.")
            self.select_folder()

    def show_image(self):
        if self.images:
            image_path = self.images[self.current_image_index]
            try:
                image = Image.open(image_path)

                # ラベルのサイズに画像をフィットさせる
                window_width, window_height = self.label.size().width(), self.label.size().height()
                image_ratio = image.width / image.height
                window_ratio = window_width / window_height

                if window_ratio > image_ratio:
                    new_height = window_height
                    new_width = int(window_height * image_ratio)
                else:
                    new_width = window_width
                    new_height = int(window_width / image_ratio)

                image = image.resize((new_width, new_height), Image.LANCZOS)
                image = image.convert("RGBA")
                pixmap = QPixmap.fromImage(QImage(image.tobytes("raw", "RGBA"), image.width, image.height, QImage.Format_RGBA8888))

                # ピクセル単位で正確に表示
                self.label.setPixmap(pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

                # ウィンドウタイトルにフォルダ名、画像の番号、並び順を表示
                folder_name = os.path.basename(os.path.dirname(image_path))
                order_type, is_ascending = self.sort_order
                order_type_str = {
                    'random': 'ランダム',
                    'date_modified': '変更日順',
                    'date_added': '追加日順',
                    'date_created': '作成日順',
                    'name': '名前順'
                }.get(order_type, '不明な順番')
                order_direction = '昇順' if is_ascending else '降順'

                self.setWindowTitle(f"KabaViewer - {folder_name} - {self.current_image_index + 1}/{len(self.images)} - {order_type_str} ({order_direction})")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to display image {image_path}.")
                print(f"Failed to load image {image_path}: {e}")

    def next_image(self):
        self.current_image_index = (self.current_image_index + 1) % len(self.images)
        self.show_image()

    def previous_image(self):
        self.current_image_index = (self.current_image_index - 1) % len(self.images)
        self.show_image()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.next_image()
        elif event.key() == Qt.Key_Left:
            self.previous_image()

    def start_slideshow(self):
        self.timer.start((self.combo_box.currentIndex() + 1) * 1000)  # コンボボックスの値を秒単位に変換
        self.is_running = True
        self.update_button_label()
        self.show_message("▶︎")

    def stop_slideshow(self):
        self.timer.stop()
        self.is_running = False
        self.update_button_label()
        self.show_message("■")

    def toggle_slideshow(self):
        if self.is_running:
            self.stop_slideshow()
        else:
            self.start_slideshow()

    def update_slideshow_speed(self):
        if self.timer.isActive():
            self.timer.start((self.combo_box.currentIndex() + 1) * 1000)
        # スライドショーの速度を設定として保存
        self.settings.setValue("スライド速度", self.combo_box.currentIndex() + 1)

    def update_button_label(self):
        if self.is_running:
            self.start_button.setText('ストップ')
            self.start_button.setStyleSheet("background-color: red; color: white;")
        else:
            self.start_button.setText('スタート')
            self.start_button.setStyleSheet("background-color: green; color: white;")

    def contextMenuEvent(self, event: QContextMenuEvent):
        # 画像タブが選択されている場合のみコンテキストメニューを表示
        if self.tabs.currentWidget() == self.image_tab:
            context_menu = QMenu(self)

            # 並び順のサブメニューを追加
            order_menu = context_menu.addMenu('並び順')

            # 並び順のタイプを選択するサブメニューとアクションを追加
            sort_types = {
                'ランダム': 'random',
                '変更日順': 'date_modified',
                '追加日順': 'date_added',
                '作成日順': 'date_created',
                '名前順': 'name'
            }

            self.sort_actions = {}
            for sort_type_name, sort_type_value in sort_types.items():
                sub_menu = order_menu.addMenu(sort_type_name)

                ascending_action = sub_menu.addAction('昇順')
                ascending_action.setCheckable(True)
                ascending_action.triggered.connect(
                    lambda checked, st=sort_type_value: self.set_sort_order((st, True))
                )

                descending_action = sub_menu.addAction('降順')
                descending_action.setCheckable(True)
                descending_action.triggered.connect(
                    lambda checked, st=sort_type_value: self.set_sort_order((st, False))
                )

                self.sort_actions[sort_type_value] = (ascending_action, descending_action)


            # スライドショーの制御
            slide_menu = context_menu.addMenu("スライド")
            start_action = slide_menu.addAction("スタート")
            stop_action = slide_menu.addAction("ストップ")

            # スライドショーの速度変更用のサブメニューを追加
            speed_menu = context_menu.addMenu("スライド速度")
            speed_actions = []
            for i in range(1, 11):
                action = speed_menu.addAction(f"{i} 秒")
                action.setCheckable(True)
                if i == self.combo_box.currentIndex() + 1:
                    action.setChecked(True)
                action.triggered.connect(lambda checked, index=i - 1: self.set_slideshow_speed(index))
                self.speed_actions.append(action)

            # 区切り線を追加
            context_menu.addSeparator()

            # 画像を削除メニューを追加
            delete_action = context_menu.addAction("画像を削除")
            delete_action.triggered.connect(self.delete_current_image)

            action = context_menu.exec_(self.mapToGlobal(event.pos()))

            if action == start_action:
                self.start_slideshow()
            elif action == stop_action:
                self.stop_slideshow()
            elif action in speed_actions:
                # 選択された速度に変更
                new_speed_index = speed_actions.index(action)
                self.combo_box.setCurrentIndex(new_speed_index)
                self.update_slideshow_speed()

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "フォルダを選択")
        if folder_path:
            self.load_images(folder_path)

    def init_menu(self):
        menubar = self.menuBar()
        # [ファイル]メニュー
        file_menu = menubar.addMenu('ファイル')
        select_folder_action = file_menu.addAction('フォルダを選択')
        select_folder_action.triggered.connect(self.select_folder)

        # [表示]メニュー
        show_menu = menubar.addMenu('表示')

        # 並び順のサブメニューを追加
        order_menu = show_menu.addMenu('並び順')

        # 並び順のタイプを選択するサブメニューとアクションを追加
        sort_types = {
            'ランダム': 'random',
            '変更日順': 'date_modified',
            '追加日順': 'date_added',
            '作成日順': 'date_created',
            '名前順': 'name'
        }

        self.sort_actions = {}
        for sort_type_name, sort_type_value in sort_types.items():
            sub_menu = order_menu.addMenu(sort_type_name)

            ascending_action = sub_menu.addAction('昇順')
            ascending_action.setCheckable(True)
            ascending_action.triggered.connect(
                lambda checked, st=sort_type_value: self.set_sort_order((st, True))
            )

            descending_action = sub_menu.addAction('降順')
            descending_action.setCheckable(True)
            descending_action.triggered.connect(
                lambda checked, st=sort_type_value: self.set_sort_order((st, False))
            )

            self.sort_actions[sort_type_value] = (ascending_action, descending_action)

        # 初期状態はランダムのみにチェックをつける
        self.set_sort_order(('random', True))


        # "スライド" サブメニューを作成
        slide_menu = show_menu.addMenu('スライド')
        start_action = slide_menu.addAction('スタート')
        stop_action = slide_menu.addAction('ストップ')

        # "スライド速度" サブメニューを作成
        speed_menu = show_menu.addMenu('スライド速度')

        # 現在の速度インデックスを取得
        current_speed_index = self.combo_box.currentIndex()

        # 各速度をサブメニューに追加
        self.speed_actions = []
        for i in range(1, 11):
            speed_action = speed_menu.addAction(f'{i} sec')
            speed_action.setCheckable(True)
            speed_action.triggered.connect(lambda checked, index=i - 1: self.set_slideshow_speed(index))
            self.speed_actions.append(speed_action)

        # 現在の速度にチェックを入れる
        self.speed_actions[current_speed_index].setChecked(True)

        start_action.triggered.connect(self.start_slideshow)
        stop_action.triggered.connect(self.stop_slideshow)

        # 移動メニュー
        move_menu = menubar.addMenu('移動')
        # 最初へ
        go_to_first_action = move_menu.addAction('最初へ')
        go_to_first_action.triggered.connect(self.go_to_first_slide)
        # 最後へ
        go_to_last_action = move_menu.addAction('最後へ')
        go_to_last_action.triggered.connect(self.go_to_last_slide)
        # スライド数指定
        go_to_slide_action = move_menu.addAction('スライド数指定')
        go_to_slide_action.triggered.connect(self.show_go_to_slide_dialog)

        # [お気に入り]メニュー
        favorite_menu = menubar.addMenu('お気に入り')
        add_favorite_action = QAction('お気に入りに追加', self)
        add_favorite_action.triggered.connect(self.add_current_folder_to_favorites)
        favorite_menu.addAction(add_favorite_action)



    def add_current_folder_to_favorites(self):
        current_folder = self.settings.value("last_folder", "")
        if current_folder and os.path.exists(current_folder):
            self.favorite_tab.add_to_favorites(current_folder)
        else:
            QMessageBox.warning(self, "Error", "No valid folder to add to favorites.")

    def delete_current_image(self):
        if not self.images:
            return
        current_image_path = self.images[self.current_image_index]
        # 確認メッセージの表示
        reply = QMessageBox.question(self, '画像を削除',
                                     f'本当に {os.path.basename(current_image_path)} を削除しますか？',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                os.remove(current_image_path)  # 画像ファイルを削除
                del self.images[self.current_image_index]  # リストから削除

                if self.images:
                    # 画像リストが残っている場合は次の画像を表示
                    self.current_image_index %= len(self.images)
                    self.show_image()
                else:
                    # 画像リストが空になった場合はラベルをクリア
                    self.label.clear()
                    QMessageBox.information(self, '情報', 'すべての画像が削除されました。')
            except Exception as e:
                QMessageBox.warning(self, 'エラー', f'画像を削除できませんでした: {e}')
##
# 移動メニュー関連
##
    def go_to_slide(self, index):
        if 0 <= index < len(self.images):
            self.current_image_index = index
            self.show_image()
        else:
            QMessageBox.warning(self, "Error", "Invalid slide number.")
    def show_go_to_slide_dialog(self):
        if not self.images:
            QMessageBox.warning(self, "Error", "No images loaded.")
            return

        # 現在の画像数を取得して、ユーザーに入力させる
        slide_number, ok = QInputDialog.getInt(self, "スライド数指定", "移動するスライド番号を入力してください:", min=1, max=len(self.images))

        if ok:
            self.go_to_slide(slide_number - 1)  # スライド番号を0始まりのインデックスに変換して移動
    def go_to_first_slide(self):
        self.go_to_slide(0)
    def go_to_last_slide(self):
        self.go_to_slide(len(self.images) - 1)

##
# メッセージ関連
##
    def update_message_font_size(self):
        """ウインドウのサイズに比例してメッセージラベルのフォントサイズを更新"""
        width = self.size().width()
        height = self.size().height()
        font_size = int(min(width, height) * 0.05)

        font = QFont()
        font.setPointSize(font_size)
        self.message_label.setFont(font)

        # paddingをフォントサイズに基づいて調整
        padding_vertical = int(font_size * 0.5)  # 文字サイズに対して50%の上下padding
        padding_horizontal = int(font_size * 0.75)  # 文字サイズに対して75%の左右padding
        self.message_label.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(128, 128, 128, 180);  /* 透明度を変更 */
                color: white;
                padding: {padding_vertical}px {padding_horizontal}px;
                border-radius: 10px;
            }}
        """)

    def resizeEvent(self, event):
        self.update_message_font_size()
        super().resizeEvent(event)

    def show_message(self, message, duration=500):
        self.message_label.setText(message)
        self.message_label.adjustSize()
        self.message_label.setGeometry(
            (self.width() - self.message_label.width()) // 2,
            (self.height() - self.message_label.height()) // 2,
            self.message_label.width(),
            self.message_label.height(),
        )
        self.message_label.raise_()  # ラベルを最前面に設定
        self.message_label.show()
        QTimer.singleShot(duration, self.message_label.hide)

    def hide_message(self):
        self.message_label.hide()