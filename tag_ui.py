#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QListWidget, QListWidgetItem,
                             QSplitter, QTextEdit, QCompleter, QMessageBox,
                             QGridLayout, QScrollArea, QFrame, QDialog,
                             QDialogButtonBox, QCheckBox, QComboBox, QSpacerItem,
                             QSizePolicy, QProgressBar, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QProgressDialog, QApplication)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QStringListModel, QSettings
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import multiprocessing
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QImage, QBrush
from tag_manager import TagManager
from PIL import Image

class MultiTagCompleter(QCompleter):
    """複数タグ入力に対応したカスタムCompleter"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_tags = []
        self.existing_tags = set()
        self.current_tag = ""
        self.line_edit = None
        self.pending_completion = None  # Enterキーで確定する候補を保持
        self.is_completing = False  # 補完処理中かどうかのフラグ
        
        # 選択時のシグナルを接続
        self.activated[str].connect(self.on_activated_delayed)  # 遅延処理を使用
        self.highlighted[str].connect(self.on_highlighted)
        # print("[デバッグ] MultiTagCompleter初期化完了")
        
    def set_tags_data(self, all_tags, existing_tags, current_tag):
        """タグデータを設定"""
        self.all_tags = all_tags
        self.existing_tags = existing_tags
        self.current_tag = current_tag
        
        # フィルタリングされたタグリストを作成
        filtered_tags = self.filter_tags()
        
        # モデルを更新
        model = QStringListModel(filtered_tags)
        self.setModel(model)
    
    def setLineEdit(self, line_edit):
        """LineEditを設定"""
        self.line_edit = line_edit
    
    def filter_tags(self):
        """現在の入力に基づいてタグをフィルタリング"""
        if not self.current_tag:
            return []
        
        filtered_tags = []
        current_input_lower = self.current_tag.lower()
        
        # print(f"[デバッグ] filter_tags: current_tag='{self.current_tag}', existing_tags={self.existing_tags}")
        
        for tag in self.all_tags:
            try:
                tag_lower = tag.lower()
                # 現在の入力にマッチし、完全一致でない場合のみ候補に追加
                if (current_input_lower in tag_lower and 
                    tag_lower != current_input_lower):
                    # 既存タグとの完全一致のみを除外（部分一致は許可）
                    # 現在のタグが既存タグに含まれていても、より長いタグは候補として表示
                    if tag_lower not in self.existing_tags or len(tag) > len(self.current_tag):
                        filtered_tags.append(tag)
            except Exception as e:
                # print(f"[デバッグ] タグフィルタリングエラー: {e}, tag: {tag}")
                continue
        
        # print(f"[デバッグ] filter_tags結果: {len(filtered_tags)}個の候補")
        # if filtered_tags:
        #     print(f"[デバッグ] 最初の5個: {filtered_tags[:5]}")
        return filtered_tags
    
    def splitPath(self, path):
        """パスを分割して現在のタグ部分のみを返す"""
        if not path or not self.line_edit:
            return []
        
        cursor_position = self.line_edit.cursorPosition()
        before_cursor = path[:cursor_position]
        
        # 最後のカンマの位置を探す
        last_comma_pos = before_cursor.rfind(',')
        
        if last_comma_pos == -1:
            # カンマがない場合は最初のタグ
            current_tag = before_cursor.strip()
        else:
            # 最後のカンマ以降の部分を取得
            current_tag = before_cursor[last_comma_pos + 1:].strip()
        
        return [current_tag] if current_tag else []
    
    def pathFromIndex(self, index):
        """候補がハイライトされた時に返す文字列をカスタマイズ"""
        # モデルから選択された文字列を取得
        text = self.model().data(index, Qt.DisplayRole)
        # print(f"[デバッグ] pathFromIndex 呼び出し: text='{text}'")
        
        # 選択された候補を保持（Enterキーで確定する時に使用）
        self.pending_completion = text
        
        # splitPathで返された値と同じものを返す
        # （これによりQCompleterの自動補完が抑制される）
        return self.completionPrefix()
    
    def on_activated_delayed(self, text):
        """オートコンプリート選択時の遅延処理（QTimerを使用）"""
        # print(f"[デバッグ] on_activated_delayed 呼び出し: text='{text}'")
        
        # pending_completionがある場合はそちらを使用
        if self.pending_completion:
            text = self.pending_completion
            # print(f"[デバッグ] pending_completionを使用: '{text}'")
        
        # QTimerを使って少し遅延させてから処理
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.on_activated(text))
    
    def on_activated(self, text):
        """オートコンプリート選択時の処理"""
        # print(f"[デバッグ] on_activated 呼び出し: text='{text}'")
        
        # 既に処理中の場合は何もしない
        if self.is_completing:
            # print(f"[デバッグ] 既に処理中のため、スキップします")
            return
        
        # 処理中フラグを立てる
        self.is_completing = True
        
        if not self.line_edit:
            # print("[デバッグ] line_editがNoneです")
            self.is_completing = False
            return
        
        try:
            # 現在のテキストとカーソル位置を取得
            current_text = self.line_edit.text()
            cursor_position = self.line_edit.cursorPosition()
            
            # print(f"[デバッグ] 現在のテキスト: '{current_text}', カーソル位置: {cursor_position}")
            
            # カーソル位置に基づいて現在編集中のタグの範囲を特定
            start_pos, end_pos = self.get_current_tag_range(current_text, cursor_position)
            
            # print(f"[デバッグ] タグ範囲: {start_pos}-{end_pos}")
            
            # start_posの直前がカンマの場合、スペースをスキップして調整
            if start_pos > 0 and current_text[start_pos - 1] == ',':
                # カンマの後のスペースをスキップ
                while start_pos < len(current_text) and current_text[start_pos] == ' ':
                    start_pos += 1
            
            # 新しいテキストを構築
            new_text = (current_text[:start_pos] + 
                       text + 
                       current_text[end_pos:])
            
            # print(f"[デバッグ] 置換後のテキスト: '{new_text}'")
            
            # カンマを自動追加（最後のタグでない場合）
            if not new_text.endswith(',') and not new_text.endswith(' '):
                # カーソル位置を調整
                new_cursor_pos = start_pos + len(text)
                
                # カーソル位置より後にタグがあるかチェック
                after_cursor = new_text[new_cursor_pos:].strip()
                if after_cursor and not after_cursor.startswith(','):
                    # 次のタグがある場合はカンマを追加
                    new_text = new_text[:new_cursor_pos] + ', ' + new_text[new_cursor_pos:]
                    new_cursor_pos += 2
                elif not after_cursor:
                    # 最後のタグの場合はカンマを追加
                    new_text = new_text + ', '
                    new_cursor_pos = len(new_text)
                
                # print(f"[デバッグ] カンマ追加後: '{new_text}', カーソル位置: {new_cursor_pos}")
                
                # テキストとカーソル位置を更新
                self.line_edit.setText(new_text)
                self.line_edit.setCursorPosition(new_cursor_pos)
            else:
                # カンマが既にある場合は単純に置換
                # print(f"[デバッグ] カンマが既にあるため単純置換")
                self.line_edit.setText(new_text)
                self.line_edit.setCursorPosition(start_pos + len(text))
            
            # ポップアップを閉じる
            self.popup().hide()
            
            # pending_completionをクリア
            self.pending_completion = None
            
            # print(f"[デバッグ] on_activated処理完了: '{self.line_edit.text()}'")
                
        except Exception as e:
            print(f"[エラー] on_activated エラー: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 処理中フラグをクリア
            self.is_completing = False
    
    def on_highlighted(self, text):
        """オートコンプリート候補がハイライトされた時の処理"""
        # print(f"[デバッグ] on_highlighted 呼び出し: text='{text}'")
        # ハイライトされた候補を保持（Enterキーで確定する準備）
        # pending_completionはpathFromIndexで既に設定されているので、ここでは何もしない
        pass
    
    def get_current_tag_range(self, text, cursor_position):
        """現在編集中のタグの開始位置と終了位置を取得"""
        try:
            # カーソル位置より前の部分を取得
            before_cursor = text[:cursor_position]
            
            # 最後のカンマの位置を探す
            last_comma_pos = before_cursor.rfind(',')
            
            if last_comma_pos == -1:
                # カンマがない場合は最初のタグ
                start_pos = 0
            else:
                # 最後のカンマの次の位置
                start_pos = last_comma_pos + 1
            
            # カーソル位置より後の部分を取得
            after_cursor = text[cursor_position:]
            
            # 次のカンマの位置を探す
            next_comma_pos = after_cursor.find(',')
            
            if next_comma_pos == -1:
                # 次のカンマがない場合は最後まで
                end_pos = len(text)
            else:
                # 次のカンマの位置
                end_pos = cursor_position + next_comma_pos
            
            return start_pos, end_pos
            
        except Exception as e:
            print(f"[デバッグ] get_current_tag_range エラー: {e}")
            return cursor_position, cursor_position

class KeyboardNavigableListWidget(QListWidget):
    """キーボードナビゲーション対応のリストウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_tab = parent
        self.currentItemChanged.connect(self.on_current_item_changed)
    
    def on_current_item_changed(self, current, previous):
        """選択アイテムが変更された時の処理（キーボード操作を含む）"""
        if current and hasattr(self.parent_tab, 'show_image_preview'):
            self.parent_tab.show_image_preview(current)
    
    def keyPressEvent(self, event):
        """キーボードイベントの処理"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # エンターキーが押された時の処理
            current_item = self.currentItem()
            if current_item and hasattr(self.parent_tab, 'open_image'):
                self.parent_tab.open_image(current_item)
        else:
            # その他のキーは通常通り処理
            super().keyPressEvent(event)

class TagChip(QFrame):
    """タグを表示する小さなチップUI"""
    tag_removed = pyqtSignal(str)  # タグ削除シグナル
    
    def __init__(self, tag_name, removable=True):
        super().__init__()
        self.tag_name = tag_name
        self.removable = removable
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        # タグ名ラベル
        self.tag_label = QLabel(self.tag_name)
        self.tag_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.tag_label)
        
        # 削除ボタン（必要な場合）
        if self.removable:
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(16, 16)
            remove_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.2);
                    border: none;
                    border-radius: 8px;
                    color: white;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(255, 0, 0, 0.7);
                }
            """)
            remove_btn.clicked.connect(lambda: self.tag_removed.emit(self.tag_name))
            layout.addWidget(remove_btn)
        
        # チップのスタイル
        self.setStyleSheet("""
            QFrame {
                background-color: #4a90e2;
                border-radius: 12px;
                margin: 2px;
            }
        """)
        self.setMaximumHeight(24)

class TagInputWidget(QWidget):
    """タグ入力・表示ウィジェット"""
    tags_changed = pyqtSignal(list)  # タグ変更シグナル
    
    def __init__(self, tag_manager):
        super().__init__()
        self.tag_manager = tag_manager
        self.current_tags = []
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # タグ入力部分
        input_layout = QHBoxLayout()
        
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("タグを入力してEnterキー (例: 風景, 夜景, ポートレート)")
        self.tag_input.returnPressed.connect(self.add_tag_from_input)
        
        # オートコンプリート機能
        all_tags = self.tag_manager.get_all_tags()
        completer = QCompleter(all_tags)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.tag_input.setCompleter(completer)
        
        input_layout.addWidget(self.tag_input)
        
        add_btn = QPushButton("追加")
        add_btn.clicked.connect(self.add_tag_from_input)
        input_layout.addWidget(add_btn)
        
        layout.addLayout(input_layout)
        
        # タグ表示エリア
        self.tags_scroll = QScrollArea()
        self.tags_widget = QWidget()
        self.tags_layout = QGridLayout(self.tags_widget)
        self.tags_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.tags_scroll.setWidget(self.tags_widget)
        self.tags_scroll.setWidgetResizable(True)
        self.tags_scroll.setMaximumHeight(120)
        self.tags_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #f8f8f8;
            }
        """)
        
        layout.addWidget(self.tags_scroll)
    
    def add_tag_from_input(self):
        """入力フィールドからタグを追加"""
        tag_text = self.tag_input.text().strip()
        if not tag_text:
            return
        
        # カンマ区切りで複数タグ対応
        new_tags = [tag.strip() for tag in tag_text.split(',') if tag.strip()]
        
        for tag in new_tags:
            if tag not in self.current_tags:
                self.current_tags.append(tag)
        
        self.tag_input.clear()
        self.update_tags_display()
        self.tags_changed.emit(self.current_tags)
    
    def set_tags(self, tags):
        """外部からタグを設定"""
        self.current_tags = tags[:]
        self.update_tags_display()
    
    def get_tags(self):
        """現在のタグリストを取得"""
        return self.current_tags[:]
    
    def remove_tag(self, tag):
        """タグを削除"""
        if tag in self.current_tags:
            self.current_tags.remove(tag)
            self.update_tags_display()
            self.tags_changed.emit(self.current_tags)
    
    def update_tags_display(self):
        """タグ表示を更新"""
        # 既存のタグチップを削除
        for i in reversed(range(self.tags_layout.count())):
            child = self.tags_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # 新しいタグチップを追加
        row = 0
        col = 0
        max_cols = 5
        
        for tag in self.current_tags:
            chip = TagChip(tag, removable=True)
            chip.tag_removed.connect(self.remove_tag)
            
            self.tags_layout.addWidget(chip, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

class TagEditDialog(QDialog):
    """画像のタグ編集ダイアログ"""
    
    def __init__(self, image_path, tag_manager, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.tag_manager = tag_manager
        self.original_tags = tag_manager.get_tags(image_path)
        
        self.setWindowTitle(f"タグ編集 - {os.path.basename(image_path)}")
        self.setModal(True)
        self.resize(500, 400)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 画像情報表示
        info_label = QLabel(f"📁 {os.path.basename(self.image_path)}")
        info_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background-color: #f0f0f0;
                border-radius: 4px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(info_label)
        
        # タグ入力ウィジェット
        self.tag_input_widget = TagInputWidget(self.tag_manager)
        self.tag_input_widget.set_tags(self.original_tags)
        layout.addWidget(self.tag_input_widget)
        
        # 人気タグ提案
        layout.addWidget(QLabel("💡 よく使われるタグ:"))
        self.popular_tags_widget = self.create_popular_tags_widget()
        layout.addWidget(self.popular_tags_widget)
        
        # ボタン
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.save_tags)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def create_popular_tags_widget(self):
        """人気タグの提案ウィジェット"""
        widget = QWidget()
        layout = QGridLayout(widget)
        
        # よく使われるタグを取得（実際の実装では使用頻度順）
        popular_tags = ["風景", "ポートレート", "夜景", "街角", "自然", "建物", "動物", "花", "食べ物", "旅行"]
        
        row = 0
        col = 0
        max_cols = 5
        
        for tag in popular_tags:
            btn = QPushButton(tag)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e8e8e8;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px 8px;
                    margin: 2px;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
            """)
            btn.clicked.connect(lambda checked, t=tag: self.add_popular_tag(t))
            
            layout.addWidget(btn, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        widget.setMaximumHeight(80)
        return widget
    
    def add_popular_tag(self, tag):
        """人気タグを追加"""
        current_tags = self.tag_input_widget.get_tags()
        if tag not in current_tags:
            current_tags.append(tag)
            self.tag_input_widget.set_tags(current_tags)
    
    def save_tags(self):
        """タグを保存"""
        new_tags = self.tag_input_widget.get_tags()
        
        try:
            # タグを完全に置き換える（既存のsave_tagsメソッドを使用）
            self.tag_manager.save_tags(self.image_path, new_tags)
            
            QMessageBox.information(self, "成功", "タグが保存されました。")
            self.accept()
            
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"タグの保存に失敗しました: {str(e)}")

class TagTab(QWidget):
    """タグ管理タブ"""
    
    def __init__(self, tag_manager, viewer):
        super().__init__()
        self.tag_manager = tag_manager
        self.viewer = viewer
        self.current_search_tags = set()  # 現在の検索タグ
        self.current_exclude_tags = set()  # 現在の除外タグ
        self.init_ui()
    
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # 左側: タグリストと検索
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 検索セクション
        search_layout = QVBoxLayout()
        search_layout.addWidget(QLabel("🔍 タグで検索"))
        
        # 検索タグ入力行
        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("検索したいタグを入力（カンマ区切りで複数指定可能）")
        self.search_input.textChanged.connect(self.update_search_results)
        search_input_layout.addWidget(self.search_input)
        
        # 検索タグクリアボタン
        self.search_clear_btn = QPushButton("×")
        self.search_clear_btn.setMaximumWidth(30)
        self.search_clear_btn.setToolTip("検索タグをクリア")
        self.search_clear_btn.clicked.connect(self.clear_search_tags)
        self.search_clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ff5252;
            }
            QPushButton:pressed {
                background-color: #e53935;
            }
        """)
        search_input_layout.addWidget(self.search_clear_btn)
        search_layout.addLayout(search_input_layout)
        
        # 除外タグ入力行
        exclude_label = QLabel("🚫 除外するタグ")
        search_layout.addWidget(exclude_label)
        
        exclude_input_layout = QHBoxLayout()
        self.exclude_input = QLineEdit()
        self.exclude_input.setPlaceholderText("除外したいタグを入力（カンマ区切りで複数指定可能）")
        self.exclude_input.textChanged.connect(self.update_search_results)
        exclude_input_layout.addWidget(self.exclude_input)
        
        # 除外タグクリアボタン
        self.exclude_clear_btn = QPushButton("×")
        self.exclude_clear_btn.setMaximumWidth(30)
        self.exclude_clear_btn.setToolTip("除外タグをクリア")
        self.exclude_clear_btn.clicked.connect(self.clear_exclude_tags)
        self.exclude_clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ff5252;
            }
            QPushButton:pressed {
                background-color: #e53935;
            }
        """)
        exclude_input_layout.addWidget(self.exclude_clear_btn)
        search_layout.addLayout(exclude_input_layout)
        
        search_options_layout = QHBoxLayout()
        self.match_all_checkbox = QCheckBox("すべてのタグにマッチ")
        self.match_all_checkbox.setChecked(True)
        self.match_all_checkbox.toggled.connect(self.update_search_results)
        search_options_layout.addWidget(self.match_all_checkbox)
        
        # お気に入りフィルターチェックボックスを追加
        self.favorites_only_checkbox = QCheckBox("♡ お気に入りのみ")
        self.favorites_only_checkbox.setChecked(False)
        self.favorites_only_checkbox.toggled.connect(self.update_search_results)
        search_options_layout.addWidget(self.favorites_only_checkbox)
        search_layout.addLayout(search_options_layout)
        
        left_layout.addLayout(search_layout)
        
        # タグ一覧
        left_layout.addWidget(QLabel("🏷️ すべてのタグ（クリック: 検索に追加, Ctrl+クリック: 除外に追加）"))
        self.all_tags_list = QListWidget()
        # スタイルシートを完全に削除してPythonコードのみで色を管理
        self.all_tags_list.setStyleSheet("")
        self.load_all_tags()
        self.all_tags_list.itemClicked.connect(self.tag_clicked)
        left_layout.addWidget(self.all_tags_list)
        
        # 右側: 検索結果と画像プレビュー
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 上下分割用のスプリッター
        vertical_splitter = QSplitter(Qt.Vertical)
        
        # 上側: 検索結果
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        # 検索結果ヘッダーとボタン
        results_header_layout = QHBoxLayout()
        results_header_layout.addWidget(QLabel("📸 検索結果"))
        results_header_layout.addStretch()  # 空白で押し離す
        
        # 「ビューアーで表示」ボタンを追加
        self.view_in_viewer_btn = QPushButton("🖼️ ビューアーで表示")
        self.view_in_viewer_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.view_in_viewer_btn.clicked.connect(self.show_results_in_viewer)
        self.view_in_viewer_btn.setEnabled(False)  # 初期状態では無効
        results_header_layout.addWidget(self.view_in_viewer_btn)
        
        results_layout.addLayout(results_header_layout)
        
        self.results_list = KeyboardNavigableListWidget(self)
        self.results_list.itemDoubleClicked.connect(self.open_image)
        self.results_list.itemClicked.connect(self.show_image_preview)  # 単一クリックでプレビュー
        results_layout.addWidget(self.results_list)
        
        vertical_splitter.addWidget(results_widget)
        
        # 下側: 画像プレビューエリア
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_layout.addWidget(QLabel("🖼️ 画像プレビュー"))
        
        # 画像表示ラベル
        self.preview_label = QLabel()
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px dashed #cccccc;
                border-radius: 8px;
                color: #666666;
                font-size: 14px;
            }
        """)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("画像を選択してください")
        self.preview_label.setScaledContents(False)  # アスペクト比を保持
        preview_layout.addWidget(self.preview_label)
        
        # 画像情報ラベル
        self.image_info_label = QLabel()
        self.image_info_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                padding: 5px;
            }
        """)
        self.image_info_label.setWordWrap(True)
        preview_layout.addWidget(self.image_info_label)
        
        vertical_splitter.addWidget(preview_widget)
        
        # スプリッターの比率を設定（上:下 = 1:1）
        vertical_splitter.setStretchFactor(0, 1)
        vertical_splitter.setStretchFactor(1, 1)
        
        right_layout.addWidget(vertical_splitter)
        
        # スプリッター
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
    
    def load_all_tags(self):
        """すべてのタグを読み込み"""
        all_tags = self.tag_manager.get_all_tags()
        self.all_tags_list.clear()
        self.all_tags_list.addItems(all_tags)
        self.update_tag_visual_states()
    
    def update_tag_visual_states(self):
        """タグリストの視覚状態を更新"""
        for i in range(self.all_tags_list.count()):
            item = self.all_tags_list.item(i)
            tag_name = item.text()
            
            # まず全ての色をリセット
            item.setBackground(QBrush())
            item.setForeground(QBrush())
            
            if tag_name in self.current_exclude_tags:
                # 除外タグ: 濃い赤色
                red_brush = QBrush(QColor(255, 205, 210))  # #ffcdd2
                item.setBackground(red_brush)
                item.setForeground(QBrush(QColor(0, 0, 0)))  # 黒
            elif tag_name in self.current_search_tags:
                # 検索タグ: 濃い青色
                blue_brush = QBrush(QColor(144, 202, 249))  # #90caf9
                item.setBackground(blue_brush)
                item.setForeground(QBrush(QColor(0, 0, 0)))  # 黒
            else:
                # 通常状態: デフォルト色
                item.setBackground(QBrush(QColor(255, 255, 255)))  # 白
                item.setForeground(QBrush(QColor(0, 0, 0)))        # 黒
        
        # 強制的に再描画
        self.all_tags_list.update()
    
    def tag_clicked(self, item):
        """タグがクリックされた時の処理"""
        tag_name = item.text()
        current_search = self.search_input.text()
        
        # Ctrlキーが押されている場合は除外タグに追加/削除
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            current_exclude = self.exclude_input.text()
            if current_exclude:
                exclude_tags = [tag.strip() for tag in current_exclude.split(',') if tag.strip()]
                if tag_name in exclude_tags:
                    # 選択済みのタグを削除
                    exclude_tags.remove(tag_name)
                    self.exclude_input.setText(', '.join(exclude_tags))
                else:
                    # 新しいタグを追加
                    self.exclude_input.setText(f"{current_exclude}, {tag_name}")
            else:
                self.exclude_input.setText(tag_name)
        else:
            # 通常の検索タグに追加/削除
            if current_search:
                search_tags = [tag.strip() for tag in current_search.split(',') if tag.strip()]
                if tag_name in search_tags:
                    # 選択済みのタグを削除
                    search_tags.remove(tag_name)
                    self.search_input.setText(', '.join(search_tags))
                else:
                    # 新しいタグを追加
                    self.search_input.setText(f"{current_search}, {tag_name}")
            else:
                self.search_input.setText(tag_name)
    
    def clear_search_tags(self):
        """検索タグをクリア"""
        self.search_input.clear()
        # textChangedシグナルで自動的にupdate_search_resultsが呼ばれる
    
    def clear_exclude_tags(self):
        """除外タグをクリア"""
        self.exclude_input.clear()
        # textChangedシグナルで自動的にupdate_search_resultsが呼ばれる
    
    def update_search_results(self):
        """検索結果を更新"""
        search_text = self.search_input.text().strip()
        exclude_text = self.exclude_input.text().strip()
        
        # 内部のタグ状態を更新
        self.current_search_tags = set()
        self.current_exclude_tags = set()
        
        if search_text:
            self.current_search_tags = set(tag.strip() for tag in search_text.split(',') if tag.strip())
        
        if exclude_text:
            self.current_exclude_tags = set(tag.strip() for tag in exclude_text.split(',') if tag.strip())
        
        # タグリストの視覚状態を更新
        self.update_tag_visual_states()
        
        # 検索タグと除外タグの両方が空で、お気に入りフィルターもオフの場合は結果をクリア
        if not search_text and not exclude_text and not self.favorites_only_checkbox.isChecked():
            self.results_list.clear()
            return
        
        # 検索タグを解析
        tags = list(self.current_search_tags)
        
        # 除外タグを解析
        exclude_tags = list(self.current_exclude_tags)
        
        match_all = self.match_all_checkbox.isChecked()
        only_favorites = self.favorites_only_checkbox.isChecked()
        
        try:
            results = self.tag_manager.search_by_tags(tags, match_all=match_all, exclude_tags=exclude_tags, only_favorites=only_favorites)
            
            self.results_list.clear()
            for file_path in results:
                item = QListWidgetItem(os.path.basename(file_path))
                item.setData(Qt.UserRole, file_path)
                self.results_list.addItem(item)
            
            # 検索結果がある場合は最初のアイテムを選択してプレビューを表示
            if self.results_list.count() > 0:
                self.results_list.setCurrentRow(0)
                first_item = self.results_list.item(0)
                if first_item:
                    self.show_image_preview(first_item)
                
            # ビューアーボタンの有効/無効を設定
            self.view_in_viewer_btn.setEnabled(self.results_list.count() > 0)
                
        except Exception as e:
            print(f"Search error: {e}")
            self.view_in_viewer_btn.setEnabled(False)
    
    def show_image_preview(self, item):
        """選択された画像のプレビューを表示"""
        file_path = item.data(Qt.UserRole)
        if not file_path or not os.path.exists(file_path):
            self.preview_label.setText("画像ファイルが見つかりません")
            self.image_info_label.setText("")
            return
        
        try:
            # 画像を読み込み
            with Image.open(file_path) as pil_image:
                # QPixmapに変換（バイト配列を変数に保持）
                image_rgba = pil_image.convert("RGBA")
                w, h = image_rgba.size
                image_bytes = image_rgba.tobytes("raw", "RGBA")
                qimage = QImage(image_bytes, w, h, QImage.Format_RGBA8888).copy()
                original_pixmap = QPixmap.fromImage(qimage)
                
                # プレビューラベルのサイズを取得
                label_width = self.preview_label.width() - 20  # マージンを考慮
                label_height = self.preview_label.height() - 20
                
                if label_width <= 50 or label_height <= 50:
                    label_width, label_height = 400, 300  # デフォルトサイズ
                
                # アスペクト比を保ったままスケール
                scaled_pixmap = original_pixmap.scaled(
                    label_width, label_height,
                    Qt.KeepAspectRatio,  # アスペクト比を保持
                    Qt.SmoothTransformation  # 高品質なスケーリング
                )
                
                # プレビューラベルの背景をリセットしてから画像を表示
                self.preview_label.setStyleSheet("""
                    QLabel {
                        background-color: #f8f8f8;
                        border: 1px solid #cccccc;
                        border-radius: 8px;
                    }
                """)
                self.preview_label.setPixmap(scaled_pixmap)
                
                # 画像情報を表示
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                
                # 元の画像サイズを取得
                with Image.open(file_path) as orig_image:
                    orig_width, orig_height = orig_image.size
                
                # タグ情報を取得
                tags = self.tag_manager.get_tags(file_path)
                tags_text = f"タグ: {', '.join(tags)}" if tags else "タグ: なし"
                
                info_text = f"""📁 {file_name}
📏 {orig_width} × {orig_height}
💾 {file_size_mb:.1f} MB
🏷️ {tags_text}"""
                
                self.image_info_label.setText(info_text)
                
        except Exception as e:
            self.preview_label.setText(f"画像の読み込みに失敗しました\n{str(e)}")
            self.image_info_label.setText("")
            print(f"Preview error: {e}")
    
    def show_results_in_viewer(self):
        """検索結果をビューアーで表示"""
        if self.results_list.count() == 0:
            QMessageBox.information(self, "情報", "表示する検索結果がありません。")
            return
            
        # 検索結果の画像パスリストを取得
        image_paths = []
        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                image_paths.append(file_path)
        
        if not image_paths:
            QMessageBox.warning(self, "エラー", "有効な画像ファイルが見つかりませんでした。")
            return
        
        try:
            # 検索タグ情報を取得
            search_text = self.search_input.text().strip()
            description = f"タグ検索: {search_text}"
            
            # ビューアーでフィルタリングされたリストを表示
            self.viewer.load_filtered_images(image_paths, description)
            
            QMessageBox.information(self, "成功", f"{len(image_paths)}枚の画像をビューアーで表示しました。")
            
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"ビューアー表示に失敗しました: {str(e)}")
    
    def open_image(self, item):
        """検索結果の画像を開く（ダブルクリック時）"""
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.exists(file_path):
            # フォルダを切り替えて画像を表示
            folder_path = os.path.dirname(file_path)
            try:
                self.viewer.load_images(folder_path)
                
                # 該当画像を選択
                if file_path in self.viewer.images:
                    self.viewer.current_image_index = self.viewer.images.index(file_path)
                    self.viewer.show_image()
                    
                # ビューアータブに切り替え
                self.viewer.tabs.setCurrentWidget(self.viewer.image_tab)
            except Exception as e:
                QMessageBox.warning(self, "エラー", f"フォルダの読み込みに失敗しました:\n{folder_path}\n{str(e)}")


class FavoritesTab(QWidget):
    """お気に入り画像管理タブ"""
    
    def __init__(self, tag_manager, viewer):
        super().__init__()
        self.tag_manager = tag_manager
        self.viewer = viewer
        self.init_ui()
    
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # 左側: フィルター・管理機能
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # お気に入り管理セクション
        manage_layout = QVBoxLayout()
        manage_layout.addWidget(QLabel("♡ お気に入り管理"))
        
        # 更新ボタン
        refresh_button = QPushButton("🔄 リストを更新")
        refresh_button.clicked.connect(self.refresh_favorites)
        manage_layout.addWidget(refresh_button)
        
        # 統計情報
        self.stats_label = QLabel("読み込み中...")
        self.stats_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                padding: 10px;
                background-color: #f5f5f5;
                border-radius: 4px;
                margin: 5px 0px;
            }
        """)
        manage_layout.addWidget(self.stats_label)
        
        left_layout.addLayout(manage_layout)
        
        # フィルターセクション
        filter_layout = QVBoxLayout()
        filter_layout.addWidget(QLabel("🔍 フィルター"))
        
        # 現在のフォルダのみ表示チェックボックス
        self.current_folder_only = QCheckBox("現在のフォルダ内のみ表示")
        self.current_folder_only.setChecked(True)
        self.current_folder_only.toggled.connect(self.update_favorites_list)
        filter_layout.addWidget(self.current_folder_only)
        
        left_layout.addLayout(filter_layout)
        left_layout.addStretch()
        
        # 右側: お気に入り一覧と画像プレビュー
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 上下分割用のスプリッター
        vertical_splitter = QSplitter(Qt.Vertical)
        
        # 上側: お気に入り一覧
        favorites_widget = QWidget()
        favorites_layout = QVBoxLayout(favorites_widget)
        favorites_layout.setContentsMargins(0, 0, 0, 0)
        
        # お気に入りヘッダーとボタン
        favorites_header_layout = QHBoxLayout()
        self.favorites_count_label = QLabel("♡ お気に入り画像")
        favorites_header_layout.addWidget(self.favorites_count_label)
        favorites_header_layout.addStretch()  # 空白で押し離す
        
        # 「ビューアーで表示」ボタンを追加
        self.view_favorites_in_viewer_btn = QPushButton("🖼️ ビューアーで表示")
        self.view_favorites_in_viewer_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff8c00;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff7700;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.view_favorites_in_viewer_btn.clicked.connect(self.show_favorites_in_viewer)
        self.view_favorites_in_viewer_btn.setEnabled(False)  # 初期状態では無効
        favorites_header_layout.addWidget(self.view_favorites_in_viewer_btn)
        
        favorites_layout.addLayout(favorites_header_layout)
        
        self.favorites_list = KeyboardNavigableListWidget(self)
        self.favorites_list.itemDoubleClicked.connect(self.open_image)
        self.favorites_list.itemClicked.connect(self.show_image_preview)
        favorites_layout.addWidget(self.favorites_list)
        
        vertical_splitter.addWidget(favorites_widget)
        
        # 下側: 画像プレビューエリア（タグタブと同様）
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_layout.addWidget(QLabel("🖼️ 画像プレビュー"))
        
        # 画像表示ラベル
        self.preview_label = QLabel()
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px dashed #cccccc;
                border-radius: 8px;
                color: #666666;
                font-size: 14px;
            }
        """)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("お気に入り画像を選択してください")
        self.preview_label.setScaledContents(False)
        preview_layout.addWidget(self.preview_label)
        
        # 画像情報ラベル
        self.image_info_label = QLabel()
        self.image_info_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                padding: 5px;
            }
        """)
        self.image_info_label.setWordWrap(True)
        preview_layout.addWidget(self.image_info_label)
        
        vertical_splitter.addWidget(preview_widget)
        
        # スプリッターの比率を設定（上:下 = 1:1）
        vertical_splitter.setStretchFactor(0, 1)
        vertical_splitter.setStretchFactor(1, 1)
        
        right_layout.addWidget(vertical_splitter)
        
        # メインスプリッター
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(main_splitter)
        
        # 初期データ読み込み
        self.refresh_favorites()
    
    def refresh_favorites(self):
        """お気に入り一覧を更新"""
        try:
            all_favorites = self.tag_manager.get_favorite_images()
            
            # 統計情報を更新
            total_count = len(all_favorites)
            existing_count = sum(1 for img_path, _, _ in all_favorites if os.path.exists(img_path))
            missing_count = total_count - existing_count
            
            stats_text = f"""📊 統計情報
🎯 総数: {total_count}枚
✅ 存在: {existing_count}枚
❌ 欠損: {missing_count}枚"""
            self.stats_label.setText(stats_text)
            
            self.update_favorites_list()
            
        except Exception as e:
            self.stats_label.setText(f"エラー: {str(e)}")
            print(f"Refresh favorites error: {e}")
    
    def update_favorites_list(self):
        """フィルター設定に応じてお気に入り一覧を更新"""
        try:
            all_favorites = self.tag_manager.get_favorite_images()
            
            # フィルター処理
            if self.current_folder_only.isChecked() and hasattr(self.viewer, 'images') and self.viewer.images:
                # 現在のフォルダ内の画像のみ
                current_paths = set(self.viewer.images)
                filtered_favorites = [
                    (img_path, file_name, updated_at) 
                    for img_path, file_name, updated_at in all_favorites
                    if img_path in current_paths and os.path.exists(img_path)
                ]
            else:
                # すべてのお気に入り（存在するもののみ）
                filtered_favorites = [
                    (img_path, file_name, updated_at) 
                    for img_path, file_name, updated_at in all_favorites
                    if os.path.exists(img_path)
                ]
            
            # リストを更新
            self.favorites_list.clear()
            for img_path, file_name, updated_at in filtered_favorites:
                item_text = f"♡ {file_name}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, img_path)
                self.favorites_list.addItem(item)
            
            # カウント表示を更新
            count_text = f"♡ お気に入り画像 ({len(filtered_favorites)}枚)"
            if self.current_folder_only.isChecked():
                count_text += " - 現在のフォルダ内"
            self.favorites_count_label.setText(count_text)
            
            # 最初のアイテムを選択
            if self.favorites_list.count() > 0:
                self.favorites_list.setCurrentRow(0)
                first_item = self.favorites_list.item(0)
                if first_item:
                    self.show_image_preview(first_item)
            else:
                self.preview_label.setText("お気に入り画像がありません")
                self.image_info_label.setText("")
            
            # ビューアーボタンの有効/無効を設定
            self.view_favorites_in_viewer_btn.setEnabled(self.favorites_list.count() > 0)
                
        except Exception as e:
            print(f"Update favorites list error: {e}")
            self.view_favorites_in_viewer_btn.setEnabled(False)
    
    def show_image_preview(self, item):
        """選択された画像のプレビューを表示（タグタブと同様）"""
        file_path = item.data(Qt.UserRole)
        if not file_path or not os.path.exists(file_path):
            self.preview_label.setText("画像ファイルが見つかりません")
            self.image_info_label.setText("")
            return
        
        try:
            # 画像を読み込み
            with Image.open(file_path) as pil_image:
                # QPixmapに変換（バイト配列を変数に保持）
                image_rgba = pil_image.convert("RGBA")
                w, h = image_rgba.size
                image_bytes = image_rgba.tobytes("raw", "RGBA")
                qimage = QImage(image_bytes, w, h, QImage.Format_RGBA8888).copy()
                original_pixmap = QPixmap.fromImage(qimage)
                
                # プレビューラベルのサイズを取得
                label_width = self.preview_label.width() - 20
                label_height = self.preview_label.height() - 20
                
                if label_width <= 50 or label_height <= 50:
                    label_width, label_height = 400, 300
                
                # アスペクト比を保ったままスケール
                scaled_pixmap = original_pixmap.scaled(
                    label_width, label_height,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                
                self.preview_label.setStyleSheet("""
                    QLabel {
                        background-color: #f8f8f8;
                        border: 1px solid #cccccc;
                        border-radius: 8px;
                    }
                """)
                self.preview_label.setPixmap(scaled_pixmap)
                
                # 画像情報を表示
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                
                # 元の画像サイズを取得
                with Image.open(file_path) as orig_image:
                    orig_width, orig_height = orig_image.size
                
                # タグ情報を取得
                tags = self.tag_manager.get_tags(file_path)
                tags_text = f"タグ: {', '.join(tags)}" if tags else "タグ: なし"
                
                info_text = f"""♡ {file_name}
📏 {orig_width} × {orig_height}
💾 {file_size_mb:.1f} MB
🏷️ {tags_text}"""
                
                self.image_info_label.setText(info_text)
                
        except Exception as e:
            self.preview_label.setText(f"画像の読み込みに失敗しました\n{str(e)}")
            self.image_info_label.setText("")
            print(f"Preview error: {e}")
    
    def show_favorites_in_viewer(self):
        """お気に入り画像をビューアーで表示"""
        if self.favorites_list.count() == 0:
            QMessageBox.information(self, "情報", "表示するお気に入り画像がありません。")
            return
            
        # お気に入り画像パスリストを取得
        image_paths = []
        for i in range(self.favorites_list.count()):
            item = self.favorites_list.item(i)
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                image_paths.append(file_path)
        
        if not image_paths:
            QMessageBox.warning(self, "エラー", "有効なお気に入り画像が見つかりませんでした。")
            return
        
        try:
            # フィルター状態に応じた説明文を生成
            if self.current_folder_only.isChecked():
                description = "お気に入り画像 (現在のフォルダ内)"
            else:
                description = "お気に入り画像 (全体)"
            
            # ビューアーでフィルタリングされたリストを表示
            self.viewer.load_filtered_images(image_paths, description)
            
            QMessageBox.information(self, "成功", f"{len(image_paths)}枚のお気に入り画像をビューアーで表示しました。")
            
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"ビューアー表示に失敗しました: {str(e)}")
    
    def open_image(self, item):
        """お気に入り画像を開く（ダブルクリック時）"""
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.exists(file_path):
            # フォルダを切り替えて画像を表示
            folder_path = os.path.dirname(file_path)
            try:
                self.viewer.load_images(folder_path)
                
                # 該当画像を選択
                if file_path in self.viewer.images:
                    self.viewer.current_image_index = self.viewer.images.index(file_path)
                    self.viewer.show_image()
                    
                # ビューアータブに切り替え
                self.viewer.tabs.setCurrentWidget(self.viewer.image_tab)
            except Exception as e:
                QMessageBox.warning(self, "エラー", f"フォルダの読み込みに失敗しました:\n{folder_path}\n{str(e)}")

# KabaViewerのメイン統合用関数
def integrate_tag_system_to_kabaviewer(viewer):
    """既存のKabaViewerにタグシステムを統合"""
    
    # TagManagerインスタンスを作成
    viewer.tag_manager = TagManager()
    
    # タグタブを追加
    viewer.tag_tab = TagTab(viewer.tag_manager, viewer)
    viewer.tabs.addTab(viewer.tag_tab, "🏷️ タグ")
    
    # 現在画像にタグ編集機能を追加（コンテキストメニュー）
    def show_tag_edit_dialog():
        if viewer.images and viewer.current_image_index < len(viewer.images):
            current_image = viewer.images[viewer.current_image_index]
            dialog = TagEditDialog(current_image, viewer.tag_manager, viewer)
            dialog.exec_()
    
    # Eキーでもタグ編集ダイアログを表示（既存のEキー機能と併用）
    original_key_press = viewer.keyPressEvent
    
    def enhanced_key_press(event):
        if event.key() == Qt.Key_T:  # Tキーでタグ編集
            if viewer.tabs.currentWidget() == viewer.image_tab:
                show_tag_edit_dialog()
        else:
            original_key_press(event)
    
    viewer.keyPressEvent = enhanced_key_press
    
    # コンテキストメニューにタグ編集を追加
    original_context_menu = viewer.contextMenuEvent
    
    def enhanced_context_menu(event):
        # 既存のコンテキストメニュー処理を実行
        original_context_menu(event)
        
        # 必要に応じてタグ編集メニューを追加
        # （既存の実装に合わせて調整）
    
    return viewer

# 使用例（既存のKabaViewerに統合）
"""
# main.pyまたはimage_viewer.pyで以下のように使用:

from tag_ui import integrate_tag_system_to_kabaviewer

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... 既存の初期化処理 ...
        
        # タグシステムを統合
        integrate_tag_system_to_kabaviewer(self)
"""


# === 自動タグ付け機能 ===

class AutoTagWorker(QThread):
    """自動タグ解析のワーカースレッド（並列処理対応）"""
    progress_updated = pyqtSignal(int, str)  # 進捗, メッセージ
    analysis_completed = pyqtSignal(dict)    # 結果
    error_occurred = pyqtSignal(str)         # エラー
    
    def __init__(self, image_paths, metadata_getter_func, analyzer):
        super().__init__()
        self.image_paths = image_paths
        self.metadata_getter_func = metadata_getter_func
        self.analyzer = analyzer
        self.is_cancelled = False
        
        # 並列処理用の同期オブジェクト
        self.progress_lock = threading.Lock()
        self.completed_count = 0
        self.total_count = len(image_paths)
        
        # アダプティブ並列処理：データ量とCPU性能に基づいて最適化
        cpu_cores = multiprocessing.cpu_count()
        
        # 少量データは単一スレッド（オーバーヘッド回避）
        if self.total_count < 10:
            self.max_workers = 1
            print(f"[最適化] 少量データ({self.total_count}枚)のため単一スレッド処理を使用")
        # 中量データは控えめな並列処理
        elif self.total_count < 50:
            self.max_workers = min(3, max(2, cpu_cores // 2))
            print(f"[最適化] 中量データ({self.total_count}枚)のため{self.max_workers}スレッド使用")
        # 大量データは積極的な並列処理
        else:
            self.max_workers = min(8, max(2, cpu_cores - 1))
            print(f"[最適化] 大量データ({self.total_count}枚)のため{self.max_workers}スレッド使用")
    
    def cancel(self):
        """処理をキャンセル"""
        self.is_cancelled = True
    
    def analyze_single_image(self, image_path):
        """単一画像の解析処理"""
        try:
            # メタデータ取得
            metadata = self.metadata_getter_func(image_path)
            
            # プロンプトデータを解析
            prompt_data = self.analyzer._parse_ai_metadata(metadata)
            
            # 自動タグを生成
            suggested_tags = self.analyzer.analyze_prompt_data(prompt_data)
            
            # 進捗更新（スレッドセーフ）
            with self.progress_lock:
                if not self.is_cancelled:
                    self.completed_count += 1
                    filename = os.path.basename(image_path)
                    self.progress_updated.emit(
                        self.completed_count, 
                        f"解析完了: {filename} ({self.completed_count}/{self.total_count})"
                    )
            
            return image_path, sorted(list(suggested_tags))
            
        except Exception as e:
            print(f"解析エラー ({image_path}): {e}")
            
            # エラーでも進捗は更新
            with self.progress_lock:
                if not self.is_cancelled:
                    self.completed_count += 1
                    filename = os.path.basename(image_path)
                    self.progress_updated.emit(
                        self.completed_count, 
                        f"エラー: {filename} ({self.completed_count}/{self.total_count})"
                    )
            
            return image_path, []
    
    def run(self):
        """メインの並列解析処理"""
        try:
            results = {}
            
            # ThreadPoolExecutorで並列処理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # すべてのタスクを投入
                future_to_path = {
                    executor.submit(self.analyze_single_image, path): path 
                    for path in self.image_paths
                }
                
                # 完了したタスクから順次結果を収集
                for future in as_completed(future_to_path):
                    if self.is_cancelled:
                        # キャンセル時は残りのタスクもキャンセル
                        for remaining_future in future_to_path:
                            remaining_future.cancel()
                        break
                    
                    try:
                        image_path, tags = future.result()
                        results[image_path] = tags
                    except Exception as e:
                        image_path = future_to_path[future]
                        print(f"タスク実行エラー ({image_path}): {e}")
                        results[image_path] = []
            
            if not self.is_cancelled:
                if self.max_workers == 1:
                    self.progress_updated.emit(self.total_count, "✅ 解析完了!")
                else:
                    self.progress_updated.emit(self.total_count, f"🚀 並列解析完了! ({self.max_workers}スレッド使用)")
                self.analysis_completed.emit(results)
                
        except Exception as e:
            self.error_occurred.emit(str(e))


class TagApplyWorker(QThread):
    """タグ適用のワーカースレッド"""
    progress_updated = pyqtSignal(int, str)  # 進捗, メッセージ
    completion_finished = pyqtSignal(int, int, float, int) # 成功数, タグ総数, 経過時間, 失敗数
    error_occurred = pyqtSignal(str, int, int)  # エラーメッセージ, 成功数, 失敗数

    def __init__(self, items, tag_manager, is_replace_mode, analysis_results):
        super().__init__()
        self.items = items
        self.tag_manager = tag_manager
        self.is_replace_mode = is_replace_mode
        self.analysis_results = analysis_results
        self.is_cancelled = False
        self.applied_count = 0
        self.failed_count = 0
        self.total_tags = 0
        self.progress_lock = threading.Lock()
        self.failed_items = []

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        start_time = time.time()
        
        # アイテム数に基づいて並列度を調整
        if len(self.items) < 5:
            max_workers = 1
        elif len(self.items) < 20:
            max_workers = 2
        else:
            max_workers = 4

        def apply_single(item):
            image_path, filename = item
            try:
                if image_path in self.analysis_results:
                    tags = self.analysis_results[image_path]
                    if tags:
                        if self.is_replace_mode:
                            success = self.tag_manager.save_tags(image_path, tags)
                        else:
                            existing_tags = self.tag_manager.get_tags(image_path)
                            new_tags = list(set(existing_tags + tags))
                            success = self.tag_manager.save_tags(image_path, new_tags)
                        
                        if success:
                            with self.progress_lock:
                                self.applied_count += 1
                                self.total_tags += len(tags)
                            return True
                        else:
                            with self.progress_lock:
                                self.failed_count += 1
                                self.failed_items.append(filename)
                            return False
                return True
            except Exception as e:
                print(f"Apply error ({filename}): {e}")
                with self.progress_lock:
                    self.failed_count += 1
                    self.failed_items.append(filename)
                return False

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(apply_single, item): item for item in self.items}
                
                completed = 0
                for future in as_completed(futures):
                    if self.is_cancelled:
                        for f in futures: f.cancel()
                        break
                    
                    completed += 1
                    _, filename = futures[future]
                    self.progress_updated.emit(completed, f"適用中... ({completed}/{len(self.items)}) {filename}")
                    
            elapsed_time = time.time() - start_time
            if not self.is_cancelled:
                self.completion_finished.emit(self.applied_count, self.total_tags, elapsed_time, self.failed_count)
        except Exception as e:
            # 重大なエラー発生時も部分的な成功情報を報告
            self.error_occurred.emit(str(e), self.applied_count, self.failed_count)


class AutoTagDialog(QDialog):
    """自動タグ付けダイアログ"""
    
    def __init__(self, image_paths, metadata_getter_func, tag_manager, parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.metadata_getter_func = metadata_getter_func
        self.tag_manager = tag_manager
        self.analysis_results = {}
        self.worker_thread = None
        
        # 自動タグアナライザーをインポート
        try:
            from auto_tag_analyzer import AutoTagAnalyzer
            self.analyzer = AutoTagAnalyzer()
        except ImportError as e:
            QMessageBox.critical(self, "エラー", f"自動タグ分析システムの読み込みに失敗しました: {e}")
            return
        
        self.init_ui()
        self.setModal(True)
        self.setWindowTitle("プロンプト解析による自動タグ付け")
        self.resize(900, 600)
    
    def init_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout(self)
        
        # タイトル
        title_label = QLabel("🤖 AI画像プロンプト解析による自動タグ付け")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 説明
        desc_label = QLabel(f"選択された {len(self.image_paths)} 枚の画像のプロンプトを解析してタグを自動生成します")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #666666; margin: 10px;")
        layout.addWidget(desc_label)
        
        # 注意事項
        warning_label = QLabel("自動タグ適用時に「追加モード」または「置換モード」を選択できます")
        warning_label.setAlignment(Qt.AlignCenter)
        warning_label.setStyleSheet("color: #0066cc; margin: 5px; font-weight: bold; background-color: #e3f2fd; padding: 8px; border-radius: 4px;")
        layout.addWidget(warning_label)
        
        # 進捗セクション
        progress_group = QGroupBox("解析進捗")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(len(self.image_paths))
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("解析準備中...")
        progress_layout.addWidget(self.progress_label)
        
        layout.addWidget(progress_group)
        
        # 結果セクション
        results_group = QGroupBox("解析結果とタグプレビュー")
        results_layout = QVBoxLayout(results_group)
        
        # 結果テーブル
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["画像ファイル", "提案タグ", "適用"])
        
        # テーブルの設定
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # ファイル名
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # タグ
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # チェックボックス
        
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        results_layout.addWidget(self.results_table)
        
        layout.addWidget(results_group)
        
        # ボタンセクション
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("🔍 解析開始")
        self.start_button.clicked.connect(self.start_analysis)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.cancel_button = QPushButton("❌ キャンセル")
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.cancel_button.setEnabled(False)
        
        self.apply_button = QPushButton("✅ 選択したタグを適用")
        self.apply_button.clicked.connect(self.apply_tags)
        self.apply_button.setEnabled(False)
        self.apply_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                border: none;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.close_button = QPushButton("閉じる")
        self.close_button.clicked.connect(self.close)
        
        self.settings_button = QPushButton("⚙️ 除外設定")
        self.settings_button.clicked.connect(self.show_exclude_settings)
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                border: none;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        
        self.rules_button = QPushButton("🔧 ルール設定")
        self.rules_button.clicked.connect(self.show_mapping_rules)
        self.rules_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                border: none;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.settings_button)
        button_layout.addWidget(self.rules_button)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def start_analysis(self):
        """解析を開始"""
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.apply_button.setEnabled(False)
        
        # 結果テーブルをクリア
        self.results_table.setRowCount(0)
        self.analysis_results = {}
        
        # ワーカースレッドを作成して開始
        self.worker_thread = AutoTagWorker(
            self.image_paths,
            self.metadata_getter_func,
            self.analyzer
        )
        
        self.worker_thread.progress_updated.connect(self.update_progress)
        self.worker_thread.analysis_completed.connect(self.analysis_finished)
        self.worker_thread.error_occurred.connect(self.analysis_error)
        
        self.worker_thread.start()
    
    def cancel_analysis(self):
        """解析をキャンセル"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.cancel()
            self.worker_thread.wait()
        
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("解析がキャンセルされました")
    
    def update_progress(self, current, message):
        """進捗を更新"""
        self.progress_bar.setValue(current)
        self.progress_label.setText(message)
    
    def analysis_finished(self, results):
        """解析完了"""
        self.analysis_results = results
        self.populate_results_table()
        
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.apply_button.setEnabled(True)
        
        # 結果サマリーを表示
        total_images = len(results)
        images_with_tags = len([r for r in results.values() if r])
        total_tags = sum(len(tags) for tags in results.values())
        
        summary = f"解析完了: {total_images}枚中{images_with_tags}枚に{total_tags}個のタグを提案"
        self.progress_label.setText(summary)
        
        QMessageBox.information(self, "解析完了", summary)
    
    def analysis_error(self, error_message):
        """解析エラー"""
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("解析エラーが発生しました")
        
        QMessageBox.critical(self, "エラー", f"自動タグ解析でエラーが発生しました:\n{error_message}")
    
    def populate_results_table(self):
        """結果テーブルに解析結果を表示"""
        self.results_table.setRowCount(len(self.analysis_results))
        
        # ファイル名順にソート
        sorted_results = sorted(self.analysis_results.items(), 
                               key=lambda x: os.path.basename(x[0]).lower())
        
        for row, (image_path, tags) in enumerate(sorted_results):
            # ファイル名
            filename = os.path.basename(image_path)
            self.results_table.setItem(row, 0, QTableWidgetItem(filename))
            
            # タグリスト（チップ風に表示）
            if tags:
                tags_text = " | ".join(tags[:10])  # 最大10個まで表示
                if len(tags) > 10:
                    tags_text += f" ... (+{len(tags)-10})"
            else:
                tags_text = "タグなし"
            
            self.results_table.setItem(row, 1, QTableWidgetItem(tags_text))
            
            # チェックボックス
            checkbox = QCheckBox()
            checkbox.setChecked(len(tags) > 0)  # タグがある場合はデフォルトでチェック
            self.results_table.setCellWidget(row, 2, checkbox)
        
        self.results_table.resizeRowsToContents()
    
    def apply_tags(self):
        """選択されたタグを実際に適用"""
        if not self.analysis_results:
            return
        
        # 選択された行を収集
        selected_items = []
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 2)
            if checkbox and checkbox.isChecked():
                filename = self.results_table.item(row, 0).text()
                # 対応する画像パスを取得
                image_path = None
                for path in self.analysis_results.keys():
                    if os.path.basename(path) == filename:
                        image_path = path
                        break
                if image_path:
                    selected_items.append((image_path, filename))
        
        if not selected_items:
            QMessageBox.warning(self, "適用なし", "適用するタグが選択されていません。")
            return
        
        # カスタム確認ダイアログを表示
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QButtonGroup, QRadioButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("タグ適用モード選択")
        dialog.setModal(True)
        dialog.resize(400, 250)
        
        layout = QVBoxLayout(dialog)
        
        # 説明
        desc_label = QLabel(f"選択された{len(selected_items)}枚の画像に自動タグを適用します。\n"
                           f"適用モードを選択してください：")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # ラジオボタングループ
        radio_group = QButtonGroup(dialog)
        
        # 追加モード
        add_radio = QRadioButton("🔗 追加モード")
        add_radio.setToolTip("既存のタグを保持し、新しい自動タグを追加します")
        radio_group.addButton(add_radio, 1)
        layout.addWidget(add_radio)
        
        add_desc = QLabel("   → 既存のタグ + 新しい自動タグ（重複は自動除去）")
        add_desc.setStyleSheet("color: #666666; margin-left: 20px; font-size: 11px;")
        layout.addWidget(add_desc)
        
        layout.addSpacing(10)
        
        # 置換モード
        replace_radio = QRadioButton("🔄 置換モード")
        replace_radio.setToolTip("既存のタグをすべて削除し、新しい自動タグに置き換えます")
        replace_radio.setChecked(True)  # デフォルトは置換モード
        radio_group.addButton(replace_radio, 2)
        layout.addWidget(replace_radio)
        
        replace_desc = QLabel("   → 新しい自動タグのみ（既存タグは削除）")
        replace_desc.setStyleSheet("color: #666666; margin-left: 20px; font-size: 11px;")
        layout.addWidget(replace_desc)
        
        layout.addSpacing(20)
        
        # ボタン
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("適用")
        ok_button.setDefault(True)
        cancel_button = QPushButton("キャンセル")
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)
        
        # イベント接続
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        # ダイアログ表示
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # 選択されたモードを取得
        selected_mode = radio_group.checkedId()
        is_replace_mode = (selected_mode == 2)
        
        # ファイル名順にソート（確実にするため）
        selected_items.sort(key=lambda x: x[1].lower())
        
        # メインウィンドウ（ImageViewer）を取得
        parent = self.parent()
        if parent and hasattr(parent, 'start_background_tag_application'):
            # バックグラウンド適用を開始
            parent.start_background_tag_application(selected_items, is_replace_mode, self.analysis_results)
            self.accept()  # ダイアログを閉じる
            return

        # 以下のフォールバック処理（QProgressDialogを使用する古い方法）は、
        # 万が一親ウィンドウが見つからない場合のために残しておきますが、
        # ImageViewer経由であれば上記で終了します。

        # プログレスバーを作成・表示
        progress_dialog = QProgressDialog("タグを適用中...", "キャンセル", 0, len(selected_items), self)
        progress_dialog.setWindowTitle("⚡ 並列タグ適用")
        progress_dialog.setModal(True)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.show()
        
        # UIを無効化
        self.apply_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.results_table.setEnabled(False)
        
        applied_count = 0
        total_tags = 0
        was_cancelled = False
        
        # 並列処理用の同期オブジェクト
        progress_lock = threading.Lock()
        completed_count = 0
        
        def apply_single_tag(item_data):
            """単一画像にタグを適用する処理"""
            nonlocal applied_count, total_tags, completed_count
            
            idx, image_path, filename = item_data
            
            try:
                # タグを適用
                if image_path in self.analysis_results:
                    tags = self.analysis_results[image_path]
                    if tags:
                        if is_replace_mode:
                            # 置換モード: 既存タグを完全に置き換える
                            success = self.tag_manager.save_tags(image_path, tags)
                            if success:
                                with progress_lock:
                                    applied_count += 1
                                    total_tags += len(tags)
                        else:
                            # 追加モード: 既存タグに新しいタグを追加
                            existing_tags = self.tag_manager.get_tags(image_path)
                            new_tags = list(set(existing_tags + tags))  # 重複除去
                            success = self.tag_manager.save_tags(image_path, new_tags)
                            if success:
                                with progress_lock:
                                    applied_count += 1
                                    total_tags += len(tags)  # 新しく追加されたタグ数
                
                return True
                
            except Exception as e:
                print(f"タグ適用エラー ({filename}): {e}")
                return False
        
        try:
            from PyQt5.QtWidgets import QApplication
            import time
            
            # 処理開始時刻を記録
            start_time = time.time()
            
            # アダプティブタグ適用：データ量に基づいて最適化
            if len(selected_items) < 5:
                max_tag_workers = 1
                print(f"[最適化] 少量適用({len(selected_items)}枚)のため単一スレッド処理を使用")
            elif len(selected_items) < 20:
                max_tag_workers = 2
                print(f"[最適化] 中量適用({len(selected_items)}枚)のため2スレッド使用")
            else:
                max_tag_workers = min(4, len(selected_items))
                print(f"[最適化] 大量適用({len(selected_items)}枚)のため{max_tag_workers}スレッド使用")
            
            # アイテムにインデックスを追加
            indexed_items = [(idx, path, filename) for idx, (path, filename) in enumerate(selected_items)]
            
            with ThreadPoolExecutor(max_workers=max_tag_workers) as executor:
                # すべてのタスクを投入
                future_to_item = {
                    executor.submit(apply_single_tag, item): item 
                    for item in indexed_items
                }
                
                # 完了したタスクから順次結果を収集
                for future in as_completed(future_to_item):
                    # キャンセルチェック
                    if progress_dialog.wasCanceled():
                        was_cancelled = True
                        # 残りのタスクをキャンセル
                        for remaining_future in future_to_item:
                            remaining_future.cancel()
                        break
                    
                    # 進捗更新
                    with progress_lock:
                        completed_count += 1
                    
                    # UI更新
                    item_data = future_to_item[future]
                    idx, _, filename = item_data
                    progress_dialog.setValue(completed_count)
                    progress_dialog.setLabelText(f"⚡ 並列適用中... ({completed_count}/{len(selected_items)})\n{filename}")
                    QApplication.processEvents()
                    
                    # タスクの結果をチェック
                    try:
                        success = future.result()
                        if not success:
                            print(f"タグ適用失敗: {filename}")
                    except Exception as e:
                        print(f"並列タスクエラー ({filename}): {e}")
            
            # プログレスバーを完了状態に（キャンセルされていない場合のみ）
            if not was_cancelled:
                progress_dialog.setValue(len(selected_items))
                progress_dialog.setLabelText("完了しました！")
                QApplication.processEvents()
                
                # 少し待機して完了メッセージを表示
                import time
                time.sleep(0.5)
            
            progress_dialog.close()
            
            # UIを再有効化
            self.apply_button.setEnabled(True)
            self.close_button.setEnabled(True)
            self.results_table.setEnabled(True)
            
            # 処理時間を計算
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # 結果を報告
            if was_cancelled:
                QMessageBox.information(self, "キャンセル", "タグの適用がキャンセルされました。")
            elif applied_count > 0:
                # 処理方式の表示を調整
                if max_tag_workers == 1:
                    processing_info = f"処理時間: {elapsed_time:.2f}秒"
                else:
                    processing_info = f"最大{max_tag_workers}スレッドで並列処理、処理時間: {elapsed_time:.2f}秒"
                
                if is_replace_mode:
                    if max_tag_workers == 1:
                        message = f"✅ {applied_count}枚の画像のタグを{total_tags}個の新しい自動タグに置き換えました。\n（{processing_info}）"
                    else:
                        message = f"⚡ {applied_count}枚の画像のタグを{total_tags}個の新しい自動タグに置き換えました。\n（{processing_info}）"
                else:
                    if max_tag_workers == 1:
                        message = f"✅ {applied_count}枚の画像に{total_tags}個の新しい自動タグを追加しました。\n（{processing_info}）"
                    else:
                        message = f"⚡ {applied_count}枚の画像に{total_tags}個の新しい自動タグを追加しました。\n（{processing_info}）"
                
                QMessageBox.information(
                    self,
                    "タグ適用完了" if max_tag_workers == 1 else "⚡ 並列タグ適用完了",
                    message
                )
                # 親ウィンドウのサイドバーを更新（タグが変更されたため）
                if hasattr(self.parent(), 'update_sidebar_metadata'):
                    self.parent().update_sidebar_metadata()
                
                self.accept()  # ダイアログを閉じる
            else:
                QMessageBox.warning(self, "適用エラー", "タグの適用に失敗しました。")
        
        except Exception as e:
            progress_dialog.close()
            # UIを再有効化
            self.apply_button.setEnabled(True)
            self.close_button.setEnabled(True)
            self.results_table.setEnabled(True)
            
            QMessageBox.critical(self, "エラー", f"タグの適用中にエラーが発生しました:\n{e}")
    
    def show_exclude_settings(self):
        """除外設定ダイアログを表示"""
        try:
            settings_dialog = ExcludeSettingsDialog(self.analyzer, self)
            settings_dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"除外設定ダイアログの表示に失敗しました:\n{e}")
    
    def show_mapping_rules(self):
        """マッピングルール設定ダイアログを表示"""
        try:
            rules_dialog = MappingRulesDialog(self.analyzer, self, self.tag_manager)
            rules_dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ルール設定ダイアログの表示に失敗しました:\n{e}")
    
    def closeEvent(self, event):
        """ダイアログが閉じられる時の処理"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.cancel()
            self.worker_thread.wait()
        event.accept()


class ExcludeSettingsDialog(QDialog):
    """自動タグ付け用の除外設定ダイアログ"""
    
    def __init__(self, analyzer, parent=None):
        super().__init__(parent)
        self.analyzer = analyzer
        self.init_ui()
        self.load_settings()
        self.setModal(True)
        self.setWindowTitle("自動タグ付け除外設定")
        self.resize(600, 500)
    
    def init_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout(self)
        
        # タイトル
        title_label = QLabel("🚫 自動タグ付け除外設定")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 説明
        desc_label = QLabel("自動タグ付け時に除外したいキーワードを設定できます")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #666666; margin: 10px;")
        layout.addWidget(desc_label)
        
        # デフォルト除外キーワード表示
        default_group = QGroupBox("デフォルト除外キーワード（変更不可）")
        default_layout = QVBoxLayout(default_group)
        
        self.default_keywords_text = QTextEdit()
        self.default_keywords_text.setReadOnly(True)
        self.default_keywords_text.setMaximumHeight(100)
        self.default_keywords_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 5px;
                color: #666666;
                padding: 5px;
            }
        """)
        default_layout.addWidget(self.default_keywords_text)
        
        layout.addWidget(default_group)
        
        # カスタム除外キーワード設定
        custom_group = QGroupBox("カスタム除外キーワード")
        custom_layout = QVBoxLayout(custom_group)
        
        # 新しいキーワード追加
        add_layout = QHBoxLayout()
        self.new_keyword_input = QLineEdit()
        self.new_keyword_input.setPlaceholderText("除外したいキーワードを入力")
        self.new_keyword_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        self.new_keyword_input.returnPressed.connect(self.add_keyword)
        
        self.add_button = QPushButton("追加")
        self.add_button.clicked.connect(self.add_keyword)
        self.add_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 5px 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        add_layout.addWidget(self.new_keyword_input)
        add_layout.addWidget(self.add_button)
        custom_layout.addLayout(add_layout)
        
        # カスタム除外キーワード一覧
        self.custom_keywords_list = QListWidget()
        self.custom_keywords_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eeeeee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        custom_layout.addWidget(self.custom_keywords_list)
        
        # 削除ボタン
        remove_button = QPushButton("選択したキーワードを削除")
        remove_button.clicked.connect(self.remove_selected_keyword)
        remove_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border: none;
                color: white;
                padding: 8px 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        custom_layout.addWidget(remove_button)
        
        layout.addWidget(custom_group)
        
        # ボタンエリア
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("リセット")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        
        self.close_button = QPushButton("閉じる")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                border: none;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def load_settings(self):
        """設定を読み込んでUIに表示"""
        # デフォルト除外キーワードを表示
        default_keywords = sorted(self.analyzer.exclude_keywords)
        self.default_keywords_text.setText(", ".join(default_keywords))
        
        # カスタム除外キーワードを表示
        self.refresh_custom_keywords_list()
    
    def refresh_custom_keywords_list(self):
        """カスタム除外キーワード一覧を更新"""
        self.custom_keywords_list.clear()
        custom_keywords = self.analyzer.load_custom_exclude_keywords()
        for keyword in sorted(custom_keywords):
            self.custom_keywords_list.addItem(keyword)
    
    def add_keyword(self):
        """新しい除外キーワードを追加"""
        keyword = self.new_keyword_input.text().strip()
        if not keyword:
            return
        
        # 既に存在チェック
        custom_keywords = self.analyzer.load_custom_exclude_keywords()
        if keyword in custom_keywords:
            QMessageBox.warning(self, "重複", f"'{keyword}' は既に除外リストに存在します。")
            return
        
        # デフォルトキーワードとの重複チェック
        if keyword in self.analyzer.exclude_keywords:
            QMessageBox.warning(self, "重複", f"'{keyword}' はデフォルトの除外キーワードです。")
            return
        
        # 追加
        self.analyzer.add_custom_exclude_keyword(keyword)
        self.refresh_custom_keywords_list()
        self.new_keyword_input.clear()
        
        QMessageBox.information(self, "追加完了", f"'{keyword}' を除外リストに追加しました。")
    
    def remove_selected_keyword(self):
        """選択されたキーワードを削除"""
        current_item = self.custom_keywords_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "選択なし", "削除するキーワードを選択してください。")
            return
        
        keyword = current_item.text()
        reply = QMessageBox.question(
            self, "削除確認", 
            f"'{keyword}' を除外リストから削除しますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.analyzer.remove_custom_exclude_keyword(keyword)
            self.refresh_custom_keywords_list()
            QMessageBox.information(self, "削除完了", f"'{keyword}' を除外リストから削除しました。")
    
    def reset_to_defaults(self):
        """カスタム除外キーワードをすべてクリア"""
        reply = QMessageBox.question(
            self, "リセット確認",
            "すべてのカスタム除外キーワードを削除しますか？\n（デフォルトの除外キーワードは残ります）",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.analyzer.save_custom_exclude_keywords([])
            self.refresh_custom_keywords_list()
            QMessageBox.information(self, "リセット完了", "カスタム除外キーワードをすべて削除しました。")


def show_auto_tag_dialog(image_paths, metadata_getter_func, tag_manager, parent=None):
    """自動タグ付けダイアログを表示するユーティリティ関数"""
    if not image_paths:
        QMessageBox.warning(parent, "エラー", "画像が選択されていません。")
        return
    
    dialog = AutoTagDialog(image_paths, metadata_getter_func, tag_manager, parent)
    dialog.exec_()


class MappingRulesDialog(QDialog):
    """キーワード→タグのマッピングルール管理ダイアログ"""
    
    def __init__(self, analyzer, parent=None, tag_manager=None):
        super().__init__(parent)
        self.analyzer = analyzer
        self.tag_manager = tag_manager

        # 生成タグ欄のオートコンプリート用デバウンスタイマー
        # QSettings の "tag_completion_debounce_ms" で可変（既定 300ms、0 なら即時）
        try:
            self._completion_debounce_ms = int(
                QSettings("MyCompany", "ImageViewerApp").value(
                    "tag_completion_debounce_ms", 300, type=int
                )
            )
        except Exception:
            self._completion_debounce_ms = 300
        self._completion_timer = QTimer(self)
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._fire_tags_completion)

        self.init_ui()
        self.load_rules()
        self.setModal(True)
        self.setWindowTitle("自動タグ付けルール設定")
        self.resize(800, 600)
    
    def eventFilter(self, obj, event):
        """イベントフィルター：Enterキーでオートコンプリート確定"""
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QKeyEvent
        from PyQt5.QtCore import Qt as QtCore_Qt
        
        # tags_inputまたはpopupのイベントをチェック
        if hasattr(self, 'tags_completer'):
            is_tags_input = hasattr(self, 'tags_input') and obj == self.tags_input
            popup = self.tags_completer.popup()
            is_popup = obj == popup
            is_popup_viewport = hasattr(popup, 'viewport') and obj == popup.viewport()
            
            if (is_tags_input or is_popup or is_popup_viewport) and event.type() == QEvent.KeyPress:
                key_event = event
                if key_event.key() in (QtCore_Qt.Key_Return, QtCore_Qt.Key_Enter):
                    # print(f"[デバッグ] Enterキーが押されました (obj: {obj})")
                    # オートコンプリートが表示されている場合
                    if self.tags_completer.popup().isVisible():
                        # print(f"[デバッグ] オートコンプリートポップアップが表示されています")
                        # ハイライトされている候補を取得
                        if self.tags_completer.pending_completion:
                            # print(f"[デバッグ] pending_completion: {self.tags_completer.pending_completion}")
                            # on_activatedを直接呼び出す（activatedシグナルを使わない）
                            self.tags_completer.on_activated(self.tags_completer.pending_completion)
                            return True  # イベントを処理済みとしてマーク（QCompleterの処理をスキップ）
                        # else:
                            # print(f"[デバッグ] pending_completionがNoneです")
                    # else:
                        # print(f"[デバッグ] オートコンプリートポップアップが表示されていません")
        
        return super().eventFilter(obj, event)
    
    def init_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout(self)
        
        # タイトル
        title_label = QLabel("🔧 自動タグ付けルール設定")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 説明
        desc_label = QLabel("「キーワード → タグ」のルールを設定します。プロンプトにキーワードが含まれていると、対応するタグが自動生成されます。")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #666666; margin: 10px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # 新しいルール追加セクション
        add_group = QGroupBox("新しいルールを追加")
        add_layout = QVBoxLayout(add_group)
        
        # キーワード入力
        keyword_layout = QHBoxLayout()
        keyword_layout.addWidget(QLabel("キーワード:"))
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("例: luka megurine")
        
        # キーワード入力にもオートコンプリート機能を追加
        self.setup_keyword_autocomplete()
        
        keyword_layout.addWidget(self.keyword_input)
        add_layout.addLayout(keyword_layout)
        
        # タグ入力
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("生成タグ:"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("例: 巡音ルカ, VOCALOID, キャラクター （カンマ区切り）")
        
        # オートコンプリート機能を追加
        self.setup_tags_autocomplete()
        
        tags_layout.addWidget(self.tags_input)
        add_layout.addLayout(tags_layout)
        
        # 追加ボタン
        add_button = QPushButton("➕ ルールを追加")
        add_button.clicked.connect(self.add_rule)
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 15px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        add_layout.addWidget(add_button)
        
        layout.addWidget(add_group)
        
        # 既存ルール表示・管理
        rules_group = QGroupBox("設定済みルール")
        rules_layout = QVBoxLayout(rules_group)
        
        # ルール表示テーブル
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(3)
        self.rules_table.setHorizontalHeaderLabels(["キーワード", "生成タグ", "削除"])
        
        # テーブル設定
        header = self.rules_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        
        self.rules_table.setAlternatingRowColors(True)
        self.rules_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        rules_layout.addWidget(self.rules_table)
        
        layout.addWidget(rules_group)
        
        # ボタンエリア
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("🔄 デフォルトに戻す")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        
        self.close_button = QPushButton("閉じる")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                border: none;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _schedule_tags_completion(self):
        """生成タグ欄のオートコンプリート更新をデバウンスしてスケジュール"""
        if self._completion_debounce_ms <= 0:
            self._fire_tags_completion()
            return
        self._completion_timer.start(self._completion_debounce_ms)

    def _fire_tags_completion(self):
        """デバウンスタイマー満了時に呼び出される実処理"""
        try:
            self.update_tags_completion()
        except Exception as e:
            print(f"[エラー] _fire_tags_completion エラー: {e}")

    def closeEvent(self, event):
        """ダイアログを閉じる際に遅延コールバックが走らないようタイマー停止"""
        try:
            if hasattr(self, '_completion_timer') and self._completion_timer is not None:
                self._completion_timer.stop()
        except Exception:
            pass
        super().closeEvent(event)

    def done(self, result):
        """accept/reject 経由で閉じる場合にもタイマーを停止"""
        try:
            if hasattr(self, '_completion_timer') and self._completion_timer is not None:
                self._completion_timer.stop()
        except Exception:
            pass
        super().done(result)

    def setup_tags_autocomplete(self):
        """生成タグ入力フィールドにオートコンプリート機能を設定"""
        try:
            # 既存のタグデータベースから候補を取得
            all_tags = self.get_all_available_tags()
            
            if not all_tags:
                print("[デバッグ] タグ候補が空です")
                return
            
            # カスタムMultiTagCompleterを作成
            self.tags_completer = MultiTagCompleter()
            self.tags_completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.tags_completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
            self.tags_completer.setMaxVisibleItems(10)  # 最大10個の候補を表示
            # インライン補完を無効化
            self.tags_completer.setCompletionPrefix("")
            
            # 入力フィールドにCompleterを設定
            self.tags_input.setCompleter(self.tags_completer)
            
            # カスタムCompleterにLineEditを設定
            self.tags_completer.setLineEdit(self.tags_input)
            
            # Enterキーイベントをインストール
            self.tags_input.installEventFilter(self)
            
            # QCompleterのポップアップにもイベントフィルターをインストール
            popup = self.tags_completer.popup()
            popup.installEventFilter(self)
            # ポップアップのビューポートにもイベントフィルターをインストール
            if hasattr(popup, 'viewport'):
                popup.viewport().installEventFilter(self)
            
            # print(f"[デバッグ] イベントフィルターをインストールしました: popup={popup}, viewport={popup.viewport() if hasattr(popup, 'viewport') else None}")
            
            # QCompleterのデフォルトのactivatedシグナル処理を無効化
            # （カスタムのon_activatedで処理する）
            self.tags_completer.setWidget(self.tags_input)
            
            # 入力内容が変更された時に候補を更新（デバウンス経由）
            self.tags_input.textChanged.connect(lambda _=None: self._schedule_tags_completion())

            # カーソル位置が変更された時にも候補を更新（デバウンス経由）
            self.tags_input.cursorPositionChanged.connect(lambda *_: self._schedule_tags_completion())
            
        except Exception as e:
            print(f"[エラー] setup_tags_autocomplete エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def setup_keyword_autocomplete(self):
        """キーワード入力フィールドにオートコンプリート機能を設定"""
        try:
            # 既存のキーワードから候補を取得
            all_keywords = self.get_all_available_keywords()
            
            if not all_keywords:
                print("[デバッグ] キーワード候補が空です")
                return
            
            # カスタムCompleterを作成
            self.keyword_completer = QCompleter(all_keywords)
            self.keyword_completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.keyword_completer.setCompletionMode(QCompleter.PopupCompletion)
            self.keyword_completer.setMaxVisibleItems(10)  # 最大10個の候補を表示
            
            # 入力フィールドにCompleterを設定
            self.keyword_input.setCompleter(self.keyword_completer)
            
        except Exception as e:
            print(f"[デバッグ] setup_keyword_autocomplete エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def get_all_available_keywords(self):
        """利用可能なすべてのキーワードを取得"""
        try:
            all_keywords = set()
            
            # 1. デフォルトマッピングルールからキーワードを取得
            try:
                default_rules = self.analyzer.get_default_mapping_rules()
                for keyword in default_rules.keys():
                    if isinstance(keyword, str) and keyword.strip():
                        all_keywords.add(keyword.strip())
            except Exception as e:
                print(f"[デバッグ] デフォルトキーワード取得エラー: {e}")
            
            # 2. カスタムマッピングルールからキーワードを取得
            try:
                custom_rules = self.analyzer.settings.value("auto_tag_mapping_rules", {}, type=dict)
                for keyword in custom_rules.keys():
                    if isinstance(keyword, str) and keyword.strip():
                        all_keywords.add(keyword.strip())
            except Exception as e:
                print(f"[デバッグ] カスタムキーワード取得エラー: {e}")
            
            # 3. よく使われるキーワードを追加
            common_keywords = [
                "1girl", "1boy", "2girls", "2boys", "girl", "boy", "woman", "man",
                "solo", "multiple", "twins", "sisters", "brothers", "smile", "smiling",
                "happy", "sad", "angry", "surprised", "crying", "laughing", "serious",
                "wink", "blush", "embarrassed", "dress", "shirt", "skirt", "pants",
                "jacket", "coat", "uniform", "kimono", "swimsuit", "bikini", "lingerie",
                "armor", "cosplay", "school_uniform", "sailor_uniform", "blazer", "tie",
                "ribbon", "blonde_hair", "brown_hair", "black_hair", "white_hair",
                "silver_hair", "red_hair", "blue_hair", "green_hair", "pink_hair",
                "purple_hair", "long_hair", "short_hair", "twintails", "ponytail",
                "braids", "curly_hair", "straight_hair", "wavy_hair", "outdoor",
                "outside", "park", "street", "road", "beach", "forest", "mountain",
                "sky", "clouds", "sunset", "sunrise", "nature", "indoor", "inside",
                "room", "bedroom", "kitchen", "bathroom", "living_room", "office",
                "classroom", "library", "school", "gymnasium", "cafeteria", "hallway",
                "stairs", "rooftop", "anime", "manga", "cartoon", "2d", "cel_shading",
                "flat_colors", "realistic", "photorealistic", "3d", "cgi", "photography",
                "portrait", "stable_diffusion", "midjourney", "dall-e", "ai_generated",
                "diffusion", "generated", "spring", "summer", "autumn", "winter",
                "cherry_blossoms", "snow", "rain", "sunny", "morning", "noon", "evening",
                "night", "midnight", "dawn", "dusk", "standing", "sitting", "lying",
                "walking", "running", "jumping", "dancing", "sleeping", "waving",
                "pointing", "nsfw", "hetero", "sex", "nude", "naked", "orgasm",
                "moaning", "cowgirl position", "straddling", "sit astride", "doggy style",
                "breasts", "large breasts", "small breasts", "chest", "nipples"
            ]
            all_keywords.update(common_keywords)
            
            return sorted(list(all_keywords))
            
        except Exception as e:
            print(f"[デバッグ] get_all_available_keywords エラー: {e}")
            import traceback
            traceback.print_exc()
            # エラー時は基本的なキーワードのみ返す
            return ["1girl", "1boy", "girl", "boy", "smile", "happy", "dress", "shirt", "anime", "realistic"]
    
    def get_all_available_tags(self):
        """利用可能なすべてのタグを取得"""
        try:
            all_tags = set()
            
            # 1. 既存のタグデータベースから取得
            try:
                if self.tag_manager:
                    db_tags = self.tag_manager.get_all_tags()
                    if db_tags:
                        all_tags.update(db_tags)
            except Exception as e:
                print(f"[デバッグ] タグデータベース取得エラー: {e}")
            
            # 2. デフォルトマッピングルールから生成タグを取得
            try:
                default_rules = self.analyzer.get_default_mapping_rules()
                for tags_list in default_rules.values():
                    if isinstance(tags_list, list):
                        all_tags.update(tags_list)
            except Exception as e:
                print(f"[デバッグ] デフォルトルール取得エラー: {e}")
            
            # 3. カスタムマッピングルールから生成タグを取得
            try:
                custom_rules = self.analyzer.settings.value("auto_tag_mapping_rules", {}, type=dict)
                for tags_list in custom_rules.values():
                    if isinstance(tags_list, list):
                        all_tags.update(tags_list)
            except Exception as e:
                print(f"[デバッグ] カスタムルール取得エラー: {e}")
            
            # 4. よく使われるタグを追加
            common_tags = [
                "人物", "キャラクター", "表情", "衣装", "ファッション", "制服", "学校",
                "髪色", "髪型", "屋外", "自然", "屋内", "建物", "アニメ", "二次元",
                "リアル", "写実的", "AI生成", "人工知能", "季節", "時間帯", "ポーズ", "動作",
                "成人向け", "R-18", "身体", "体型", "風景", "ポートレート", "夜景", "街角",
                "動物", "花", "食べ物", "旅行", "水着", "ビキニ", "ドレス", "制服"
            ]
            all_tags.update(common_tags)
            
            # 5. テスト用のタグを追加（BB関連）
            test_tags = [
                "BB_Pony", "BB_Chan", "BB_Character", "BB_Anime", "BB_Game",
                "BB_Type", "BB_Series", "BB_Universe", "BB_World", "BB_Story"
            ]
            all_tags.update(test_tags)
            
            # 文字列以外の要素を除外
            filtered_tags = []
            for tag in all_tags:
                try:
                    if isinstance(tag, str) and tag.strip():
                        filtered_tags.append(tag.strip())
                except Exception as e:
                    print(f"[デバッグ] タグフィルタリングエラー: {e}, tag: {tag}")
                    continue
            
            return sorted(list(set(filtered_tags)))
            
        except Exception as e:
            print(f"[デバッグ] get_all_available_tags エラー: {e}")
            import traceback
            traceback.print_exc()
            # エラー時は基本的なタグのみ返す
            return ["人物", "キャラクター", "表情", "衣装", "ファッション", "制服", "学校"]
    
    def update_tags_completion(self, text=None):
        """入力内容に基づいて候補を動的に更新"""
        try:
            if not hasattr(self, 'tags_input') or not self.tags_input:
                return
            
            # Completerが処理中の場合はスキップ
            if hasattr(self, 'tags_completer') and self.tags_completer.is_completing:
                # print("[デバッグ] Completer処理中のため、update_tags_completionをスキップ")
                return
            
            # テキストが渡されていない場合は入力フィールドから取得
            if text is None:
                text = self.tags_input.text()
            
            if not text:
                return
            
            # カーソル位置を取得
            cursor_position = self.tags_input.cursorPosition()
            
            # カーソル位置に基づいて現在編集中のタグを特定
            current_tag = self.get_current_editing_tag(text, cursor_position)
            
            # print(f"[デバッグ] update_tags_completion: text='{text}', cursor={cursor_position}, current_tag='{current_tag}'")
            
            if not current_tag:
                # print("[デバッグ] current_tagが空のため、候補をクリア")
                if hasattr(self, 'tags_completer') and self.tags_completer:
                    model = QStringListModel([])
                    self.tags_completer.setModel(model)
                return
            
            # 既存のタグを除外して候補を絞り込み
            all_tags = self.get_all_available_tags()
            existing_tags = self.get_existing_tags(text, cursor_position)
            
            # print(f"[デバッグ] all_tags数: {len(all_tags)}, existing_tags: {existing_tags}")
            
            # カスタムCompleterにデータを設定
            if hasattr(self, 'tags_completer') and self.tags_completer:
                self.tags_completer.set_tags_data(all_tags, existing_tags, current_tag)
                # print(f"[デバッグ] Completerモデル更新後: {self.tags_completer.model().stringList()[:5]}")
                
                # ポップアップを表示
                if self.tags_completer.model().rowCount() > 0:
                    # Completerを再度アクティブにする
                    self.tags_completer.complete()
                    # print(f"[デバッグ] Completerのポップアップを表示")
            
        except Exception as e:
            print(f"[デバッグ] update_tags_completion エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def get_current_editing_tag(self, text, cursor_position):
        """カーソル位置に基づいて現在編集中のタグを取得"""
        try:
            # テキストが文字列でない場合は空文字を返す
            if not isinstance(text, str):
                return ""
            
            # カーソル位置が範囲外の場合は調整
            if cursor_position < 0:
                cursor_position = 0
            elif cursor_position > len(text):
                cursor_position = len(text)
            
            # カーソル位置より前の部分を取得
            before_cursor = text[:cursor_position]
            
            # 最後のカンマの位置を探す
            last_comma_pos = before_cursor.rfind(',')
            
            if last_comma_pos == -1:
                # カンマがない場合は最初のタグ
                current_tag = before_cursor.strip()
            else:
                # 最後のカンマ以降の部分を取得
                current_tag = before_cursor[last_comma_pos + 1:].strip()
            
            # カーソル位置がカンマの直後の場合は空文字を返す（新しいタグの開始）
            if cursor_position < len(text) and text[cursor_position] == ',':
                return ""
            
            # デバッグ情報を出力（必要に応じてコメントアウト）
            # print(f"[デバッグ] get_current_editing_tag: text='{text}', cursor={cursor_position}, current_tag='{current_tag}'")
            
            return current_tag
        except Exception as e:
            print(f"[デバッグ] get_current_editing_tag エラー: {e}, text: {text}, cursor_position: {cursor_position}")
            return ""
    
    def get_existing_tags(self, text, cursor_position):
        """カーソル位置に基づいて既存のタグセットを取得（現在編集中のタグは除外）"""
        try:
            # テキストが文字列でない場合は空セットを返す
            if not isinstance(text, str):
                return set()
            
            # カーソル位置が範囲外の場合は調整
            if cursor_position < 0:
                cursor_position = 0
            elif cursor_position > len(text):
                cursor_position = len(text)
            
            # 現在編集中のタグの範囲を取得
            # カーソル位置より前の部分を取得
            before_cursor = text[:cursor_position]
            
            # 最後のカンマの位置を探す
            last_comma_pos = before_cursor.rfind(',')
            
            if last_comma_pos == -1:
                # カンマがない場合は最初のタグ
                start_pos = 0
            else:
                # 最後のカンマの次の位置
                start_pos = last_comma_pos + 1
            
            # カーソル位置より後の部分を取得
            after_cursor = text[cursor_position:]
            
            # 次のカンマの位置を探す
            next_comma_pos = after_cursor.find(',')
            
            if next_comma_pos == -1:
                # 次のカンマがない場合は最後まで
                end_pos = len(text)
            else:
                # 次のカンマの位置
                end_pos = cursor_position + next_comma_pos
            
            # 現在編集中のタグを除外したテキストを作成
            text_without_current = text[:start_pos] + text[end_pos:]
            
            # すべてのタグを取得
            all_tags = []
            if text_without_current.strip():
                all_tags = [tag.strip().lower() for tag in text_without_current.split(',') if tag.strip()]
            
            # 既存のタグセットを作成
            existing_tags = set(all_tags)
            
            # print(f"[デバッグ] get_existing_tags: text='{text}', cursor={cursor_position}, existing_tags={existing_tags}")
            
            return existing_tags
        except Exception as e:
            print(f"[デバッグ] get_existing_tags エラー: {e}, text: {text}, cursor_position: {cursor_position}")
            return set()
    
    def load_rules(self):
        """ルールを読み込んでテーブルに表示"""
        # デフォルトルールとカスタムルールを個別に取得
        default_rules = self.analyzer.get_default_mapping_rules()
        custom_rules = self.analyzer.settings.value("auto_tag_mapping_rules", {}, type=dict)
        
        total_rules = len(default_rules) + len(custom_rules)
        self.rules_table.setRowCount(total_rules)
        
        row = 0
        
        # デフォルトルールを表示（削除不可）
        for keyword, tags in default_rules.items():
            # キーワード（デフォルトマーク付き）
            keyword_item = QTableWidgetItem(f"📌 {keyword}")
            keyword_item.setBackground(QColor(245, 245, 245))  # グレー背景
            self.rules_table.setItem(row, 0, keyword_item)
            
            # タグ（カンマ区切りで表示）
            tags_text = ", ".join(tags)
            tags_item = QTableWidgetItem(tags_text)
            tags_item.setBackground(QColor(245, 245, 245))  # グレー背景
            self.rules_table.setItem(row, 1, tags_item)
            
            # 削除不可ラベル
            disabled_label = QLabel("🔒 デフォルト")
            disabled_label.setAlignment(Qt.AlignCenter)
            disabled_label.setStyleSheet("""
                QLabel {
                    background-color: #e0e0e0;
                    color: #757575;
                    padding: 4px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                }
            """)
            self.rules_table.setCellWidget(row, 2, disabled_label)
            row += 1
        
        # カスタムルールを表示（削除可能）
        for keyword, tags in custom_rules.items():
            # キーワード
            self.rules_table.setItem(row, 0, QTableWidgetItem(keyword))
            
            # タグ（カンマ区切りで表示）
            tags_text = ", ".join(tags)
            self.rules_table.setItem(row, 1, QTableWidgetItem(tags_text))
            
            # 削除ボタン
            delete_button = QPushButton("🗑️ 削除")
            delete_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    border: none;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
            """)
            delete_button.clicked.connect(lambda checked, k=keyword: self.remove_rule(k))
            self.rules_table.setCellWidget(row, 2, delete_button)
            row += 1
        
        self.rules_table.resizeRowsToContents()
    
    def add_rule(self):
        """新しいルールを追加"""
        keyword = self.keyword_input.text().strip()
        tags_text = self.tags_input.text().strip()
        
        if not keyword or not tags_text:
            QMessageBox.warning(self, "入力エラー", "キーワードとタグの両方を入力してください。")
            return
        
        # タグをカンマ区切りで分割
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        
        if not tags:
            QMessageBox.warning(self, "入力エラー", "少なくとも1つのタグを入力してください。")
            return
        
        # ルールを追加
        self.analyzer.add_mapping_rule(keyword, tags)
        
        # 入力をクリア
        self.keyword_input.clear()
        self.tags_input.clear()
        
        # テーブルを更新
        self.load_rules()
        
        QMessageBox.information(self, "追加完了", f"ルール '{keyword}' → {tags} を追加しました。")
    
    def remove_rule(self, keyword):
        """ルールを削除"""
        reply = QMessageBox.question(
            self, "削除確認", 
            f"ルール '{keyword}' を削除しますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.analyzer.remove_mapping_rule(keyword)
            self.load_rules()
            QMessageBox.information(self, "削除完了", f"ルール '{keyword}' を削除しました。")
    
    def reset_to_defaults(self):
        """カスタムルールをすべてクリアしてデフォルトに戻す"""
        reply = QMessageBox.question(
            self, "リセット確認",
            "すべてのカスタムルールを削除してデフォルトルールのみにしますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.analyzer.save_mapping_rules({})  # カスタムルールをクリア
            self.load_rules()
            QMessageBox.information(self, "リセット完了", "デフォルトルールに戻しました。")


def show_exclude_settings_dialog(analyzer, parent=None):
    """除外設定ダイアログを表示するユーティリティ関数"""
    dialog = ExcludeSettingsDialog(analyzer, parent)
    dialog.exec_()


def show_mapping_rules_dialog(analyzer, parent=None, tag_manager=None):
    """マッピングルール設定ダイアログを表示するユーティリティ関数"""
    dialog = MappingRulesDialog(analyzer, parent, tag_manager)
    dialog.exec_()


class FavoriteImagesDialog(QDialog):
    """お気に入り画像一覧ダイアログ"""
    
    def __init__(self, favorite_images, tag_manager, parent=None):
        super().__init__(parent)
        self.favorite_images = favorite_images
        self.tag_manager = tag_manager
        self.selected_image_path = None
        self.init_ui()
    
    def init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("♡ お気に入り画像")
        self.setModal(True)
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # ヘッダー（動的にカウント）
        existing_count = sum(1 for image_path, _, _ in self.favorite_images if os.path.exists(image_path))
        header_label = QLabel(f"♡ お気に入り画像一覧 ({existing_count}枚)")
        header_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333333;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header_label)
        
        # 画像リスト
        self.image_list = QListWidget()
        self.image_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eeeeee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.image_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # 画像リストを埋める
        missing_files = []
        for image_path, file_name, updated_at in self.favorite_images:
            if os.path.exists(image_path):
                # ファイルが存在する場合のみ追加
                item_text = f"♡ {file_name}"
                if updated_at:
                    item_text += f"\n📅 {updated_at}"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, image_path)
                self.image_list.addItem(item)
            else:
                missing_files.append(file_name)
        
        # 存在しないファイルがある場合は情報を表示
        if missing_files and len(missing_files) < 5:  # 少数の場合のみ詳細表示
            missing_info = QLabel(f"⚠️ 見つからないファイル: {', '.join(missing_files)}")
            missing_info.setStyleSheet("""
                QLabel {
                    color: #ff6b35;
                    font-size: 12px;
                    padding: 5px;
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    margin-bottom: 5px;
                }
            """)
            missing_info.setWordWrap(True)
            layout.insertWidget(1, missing_info)  # ヘッダーの下に挿入
        elif missing_files:  # 多数の場合は件数のみ表示
            missing_info = QLabel(f"⚠️ {len(missing_files)}個のファイルが見つかりません")
            missing_info.setStyleSheet("""
                QLabel {
                    color: #ff6b35;
                    font-size: 12px;
                    padding: 5px;
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    margin-bottom: 5px;
                }
            """)
            layout.insertWidget(1, missing_info)  # ヘッダーの下に挿入
        
        layout.addWidget(self.image_list)
        
        # ボタンエリア
        button_layout = QHBoxLayout()
        
        # お気に入りから削除ボタン
        remove_button = QPushButton("♡ お気に入りから削除")
        remove_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        remove_button.clicked.connect(self.remove_from_favorites)
        button_layout.addWidget(remove_button)
        
        button_layout.addStretch()
        
        # 表示ボタン
        view_button = QPushButton("🖼️ 表示")
        view_button.setDefault(True)
        view_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        view_button.clicked.connect(self.view_selected_image)
        button_layout.addWidget(view_button)
        
        # キャンセルボタン
        cancel_button = QPushButton("キャンセル")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # 最初のアイテムを選択
        if self.image_list.count() > 0:
            self.image_list.setCurrentRow(0)
    
    def on_item_double_clicked(self, item):
        """アイテムダブルクリック時の処理"""
        self.view_selected_image()
    
    def view_selected_image(self):
        """選択された画像を表示"""
        current_item = self.image_list.currentItem()
        if current_item:
            self.selected_image_path = current_item.data(Qt.UserRole)
            self.accept()
    
    def remove_from_favorites(self):
        """選択された画像をお気に入りから削除"""
        current_item = self.image_list.currentItem()
        if not current_item:
            return
        
        image_path = current_item.data(Qt.UserRole)
        file_name = os.path.basename(image_path)
        
        reply = QMessageBox.question(
            self, "お気に入りから削除",
            f"「{file_name}」をお気に入りから削除しますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.tag_manager.set_favorite_status(image_path, False)
                # リストからアイテムを削除
                row = self.image_list.row(current_item)
                self.image_list.takeItem(row)
                
                # リストが空になった場合は閉じる
                if self.image_list.count() == 0:
                    QMessageBox.information(self, "お気に入り", "お気に入り画像がなくなりました。")
                    self.reject()
                    
            except Exception as e:
                QMessageBox.warning(self, "エラー", f"お気に入り削除エラー: {str(e)}")
    
    def get_selected_image_path(self):
        """選択された画像のパスを取得"""
        return self.selected_image_path
