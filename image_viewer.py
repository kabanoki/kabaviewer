# back
import os
import random
import zipfile
import shutil
import datetime
from PyQt5.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QComboBox, QTabWidget, QMenu, QFileDialog, QMessageBox, QAction, QInputDialog, QGridLayout, QDialog, QTextEdit, QScrollArea, QFrame, QApplication, QProgressDialog, QProgressBar
from PyQt5.QtGui import QPixmap, QImage, QContextMenuEvent, QFont, QIcon, QPainter, QColor, QPen, QBrush, QPainterPath
from PyQt5.QtCore import Qt, QTimer, QSettings, QPointF
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from history import HistoryTab
from favorite import FavoriteTab

# タグシステムのインポート
try:
    from tag_manager import TagManager
    from tag_ui import (
        TagTab, TagEditDialog, show_auto_tag_dialog, 
        show_exclude_settings_dialog, show_mapping_rules_dialog, 
        FavoriteImagesDialog, FavoritesTab, AutoTagDialog
    )
    TAG_SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"タグシステムのインポートに失敗しました: {e}")
    TAG_SYSTEM_AVAILABLE = False

class ExifInfoDialog(QDialog):
    """画像メタデータを美しく表示するダイアログ"""
    def __init__(self, exif_data, image_path, parent=None, parse_only=False):
        super().__init__(parent)
        self.exif_data = exif_data
        self.image_path = image_path
        self.parsed_prompt_data = self.parse_prompt_data()
        if not parse_only:
            self.init_ui()
    
    @staticmethod
    def parse_metadata_statically(exif_data):
        """AI生成画像のプロンプトデータを解析して構造化（静的メソッド版）"""
        parsed_data = {
            'prompt': '',
            'negative_prompt': '',
            'hire_prompt': '',
            'parameters': {},
            'tags': [],
            'has_ai_data': False
        }
        
        # AI生成画像のプロンプト情報を探す
        ai_prompt_text = ''
        for key, value in exif_data.items():
            if str(key).startswith('AI_') and isinstance(value, str):
                ai_prompt_text = value
                parsed_data['has_ai_data'] = True
                break
        
        if not ai_prompt_text:
            return parsed_data
            
        # プロンプトテキストを解析
        lines = ai_prompt_text.split('\n')
        current_section = 'prompt'
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # ネガティブプロンプト検出
            if line.lower().startswith('negative prompt:'):
                current_section = 'negative'
                negative_content = line[len('negative prompt:'):].strip()
                if negative_content:
                    parsed_data['negative_prompt'] = negative_content
                continue
            
            # Hiresプロンプト検出
            if line.lower().startswith('hires prompt:'):
                current_section = 'hire'
                continue
            
            # パラメータ行検出
            is_weight_element = (line.strip().startswith('(') and 
                               (':' in line and 
                                (line.strip().endswith(')') or line.strip().endswith('),'))))
            
            is_simple_weight = False
            if ':' in line and not is_weight_element:
                parts = line.strip().split(':')
                if len(parts) == 2:
                    key_part = parts[0].strip().strip('(').strip()
                    value_part = parts[1].strip().strip(')').strip(',').strip()
                    if (len(key_part.split()) <= 3 and 
                        (value_part.replace('.', '').isdigit() or 
                         value_part in ['1', '2', '3', '4', '5', '0.5', '0.7', '0.8', '0.9', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7', '1.8', '1.9', '2.0'])):
                        is_simple_weight = True
            
            is_actual_param_line = (':' in line and 
                                  not is_weight_element and 
                                  not is_simple_weight and
                                  any(param in line.lower() for param in [
                                      'steps:', 'sampler:', 'cfg scale:', 'seed:', 'size:', 
                                      'model:', 'denoising strength:', 'clip skip:', 
                                      'hires upscale:', 'hires steps:', 'vae:', 'lora hashes:',
                                      'schedule type:', 'vae hash:', 'emphasis:', 'version:'
                                  ]))
            
            if is_actual_param_line:
                current_section = 'parameters'
                line_for_params = line
                if 'hires prompt:' in line.lower():
                    hires_start = line.lower().find('hires prompt:')
                    if hires_start != -1:
                        after_hires = line[hires_start:]
                        if '"' in after_hires:
                            quote_start = after_hires.find('"')
                            remaining = after_hires[quote_start + 1:]
                            if '",' in remaining:
                                quote_end = remaining.find('",')
                                before_hires = line[:hires_start]
                                after_quote = remaining[quote_end + 2:]
                                line_for_params = before_hires + "Hires prompt: [EXCLUDED]" + after_quote
                
                params = line_for_params.split(',')
                for param in params:
                    param = param.strip()
                    if (':' in param and 
                        not param.lower().startswith('hires prompt') and
                        not param.startswith('\\n') and 
                        not '\\n' in param and 
                        not param.startswith('(') and 
                        'EXCLUDED' not in param):
                        try:
                            key, value = param.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            valid_keys = ['steps', 'sampler', 'schedule type', 'cfg scale', 'seed', 'size', 
                                        'model hash', 'model', 'vae hash', 'vae', 'denoising strength', 
                                        'clip skip', 'hires upscale', 'hires steps', 'hires upscaler', 
                                        'lora hashes', 'emphasis', 'version']
                            if key.lower() in valid_keys:
                                parsed_data['parameters'][key] = value
                        except ValueError:
                            pass
                continue
            
            if current_section == 'prompt':
                if parsed_data['prompt']:
                    parsed_data['prompt'] += ' ' + line
                else:
                    parsed_data['prompt'] = line
            elif current_section == 'negative':
                if parsed_data['negative_prompt']:
                    parsed_data['negative_prompt'] += ' ' + line
                else:
                    parsed_data['negative_prompt'] = line
        
        if 'txt2img' in ai_prompt_text.lower():
            parsed_data['tags'].append('TXT2IMG')
        if 'hires prompt:' in ai_prompt_text.lower() or 'hi-res' in ai_prompt_text.lower():
            parsed_data['tags'].append('HI-RES')
        if any(model in ai_prompt_text.lower() for model in ['automatic1111', 'webui']):
            parsed_data['tags'].append('AUTOMATIC1111')
        if 'comfyui' in ai_prompt_text.lower():
            parsed_data['tags'].append('COMFYUI')
        
        return parsed_data

    def parse_prompt_data(self):
        """AI生成画像のプロンプトデータを解析して構造化"""
        return self.parse_metadata_statically(self.exif_data)
    
    def init_ui(self):
        self.setWindowTitle(f"画像メタデータ情報 - {os.path.basename(self.image_path)}")
        self.setGeometry(200, 200, 700, 600)  # サイズを拡大
        
        # メインレイアウト
        layout = QVBoxLayout()
        
        # スクロール可能エリアの作成
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 現在のタグセクション（一番最初に表示、タグシステムが利用可能な場合）
        self.create_current_tags_section(scroll_layout)
        
        # AI生成画像データがある場合の美しい表示
        if self.parsed_prompt_data['has_ai_data']:
            self.create_ai_sections(scroll_layout)
        
        # EXIF情報セクション
        self.create_exif_section(scroll_layout)
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # ボタン部分
        button_layout = QHBoxLayout()
        
        # 全体コピーボタン
        copy_all_button = QPushButton("📋 全体コピー")
        copy_all_button.clicked.connect(self.copy_all_metadata)
        copy_all_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        button_layout.addWidget(copy_all_button)
        
        button_layout.addStretch()
        
        # 閉じるボタン
        close_button = QPushButton("閉じる")
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # ダイアログの全体的なスタイル
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QFrame {
                background-color: #3c3c3c;
                border-radius: 8px;
                margin: 5px;
                padding: 10px;
            }
        """)
    
    def copy_all_metadata(self):
        """全てのメタデータをクリップボードにコピー"""
        all_text_lines = []
        
        # ファイル情報
        all_text_lines.append(f"ファイル: {os.path.basename(self.image_path)}")
        all_text_lines.append(f"パス: {self.image_path}")
        all_text_lines.append("")
        
        # AI生成画像情報
        if self.parsed_prompt_data['has_ai_data']:
            if self.parsed_prompt_data['prompt']:
                all_text_lines.append("=== Prompt ===")
                all_text_lines.append(self.parsed_prompt_data['prompt'])
                all_text_lines.append("")
            
            if self.parsed_prompt_data['negative_prompt']:
                all_text_lines.append("=== Negative prompt ===")
                all_text_lines.append(self.parsed_prompt_data['negative_prompt'])
                all_text_lines.append("")
            
            if self.parsed_prompt_data['hire_prompt']:
                all_text_lines.append("=== Hires prompt ===")
                all_text_lines.append(self.parsed_prompt_data['hire_prompt'])
                all_text_lines.append("")
            
            if self.parsed_prompt_data['parameters']:
                all_text_lines.append("=== Parameters ===")
                for key, value in self.parsed_prompt_data['parameters'].items():
                    all_text_lines.append(f"{key}: {value}")
                all_text_lines.append("")
        
        # EXIF情報
        exif_info = {}
        for key, value in self.exif_data.items():
            if not str(key).startswith('AI_') and not str(key).startswith('Meta_'):
                exif_info[key] = value
        
        if exif_info:
            all_text_lines.append("=== EXIF Information ===")
            for tag_id, value in exif_info.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if isinstance(value, bytes):
                    value_str = f"<バイナリデータ ({len(value)} bytes)>"
                else:
                    value_str = str(value)[:100]
                all_text_lines.append(f"{tag_name}: {value_str}")
        
        # クリップボードにコピー
        full_text = "\n".join(all_text_lines)
        clipboard = QApplication.clipboard()
        clipboard.setText(full_text)
        
        # ボタンの一時的な変更でコピー完了を示す
        copy_button = self.sender()
        original_text = copy_button.text()
        copy_button.setText("✓ コピー完了")
        QTimer.singleShot(1500, lambda: copy_button.setText(original_text))
    
    def create_ai_sections(self, layout):
        """AI生成画像情報の美しいセクションを作成"""
        # プロンプトセクション
        if self.parsed_prompt_data['prompt']:
            prompt_frame = self.create_collapsible_section(
                "Prompt", 
                self.parsed_prompt_data['prompt'],
                self.parsed_prompt_data['tags']
            )
            layout.addWidget(prompt_frame)
        
        # ネガティブプロンプトセクション
        if self.parsed_prompt_data['negative_prompt']:
            negative_frame = self.create_collapsible_section(
                "Negative prompt",
                self.parsed_prompt_data['negative_prompt'],
                []
            )
            layout.addWidget(negative_frame)
        
        # Hiresプロンプトセクション
        if self.parsed_prompt_data['hire_prompt']:
            hire_frame = self.create_collapsible_section(
                "Hires prompt",
                self.parsed_prompt_data['hire_prompt'],
                []
            )
            layout.addWidget(hire_frame)
        
        # パラメータセクション
        if self.parsed_prompt_data['parameters']:
            param_frame = self.create_parameters_section()
            layout.addWidget(param_frame)
    
    def create_collapsible_section(self, title, content, tags):
        """折りたたみ可能なセクションを作成"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 8px;
                margin: 5px 0px;
                padding: 0px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        
        # ヘッダー部分
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        # タイトル
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
            }
        """)
        header_layout.addWidget(title_label)
        
        # タグ表示
        for tag in tags:
            tag_label = QLabel(tag)
            tag_label.setStyleSheet("""
                QLabel {
                    background-color: #4a90e2;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    margin-left: 10px;
                }
            """)
            header_layout.addWidget(tag_label)
        
        header_layout.addStretch()
        
        # コピーボタン
        copy_button = QPushButton("📋")
        copy_button.setToolTip("テキストをコピー")
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                color: white;
                padding: 6px 8px;
                border-radius: 4px;
                font-size: 14px;
                margin-left: 5px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        
        # Show more/less ボタン
        self.toggle_button = QPushButton("Show more")
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: #4a90e2;
                font-size: 12px;
                text-decoration: underline;
                margin-left: 10px;
            }
            QPushButton:hover {
                color: #357ae8;
            }
        """)
        
        # コンテンツ部分
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 0, 15, 15)
        
        # プロンプト内容（QTextEditを使用してテキスト選択可能にする）
        content_text_edit = QTextEdit()
        content_text_edit.setReadOnly(True)
        content_text_edit.setStyleSheet("""
            QTextEdit {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
                border: none;
                padding: 5px 0px;
            }
        """)
        content_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # コピー機能の実装
        def copy_content():
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
            # 一時的にボタンテキストを変更してコピー完了を示す
            original_text = copy_button.text()
            copy_button.setText("✓")
            QTimer.singleShot(1000, lambda: copy_button.setText(original_text))
        
        copy_button.clicked.connect(copy_content)
        header_layout.addWidget(copy_button)
        
        # プロンプト系のコンテンツは全文表示、その他は長い場合のみ省略
        is_prompt_content = "prompt" in title.lower() or "プロンプト" in title
        
        if not is_prompt_content and len(content) > 800:
            # プロンプト以外で非常に長い場合のみ省略機能を提供
            short_content = content[:800] + "..."
            content_text_edit.setPlainText(short_content)
            content_text_edit.full_text = content
            content_text_edit.short_text = short_content
            content_text_edit.is_expanded = False
            
            def toggle_content():
                if content_text_edit.is_expanded:
                    content_text_edit.setPlainText(content_text_edit.short_text)
                    self.toggle_button.setText("Show more")
                    content_text_edit.is_expanded = False
                    # 高さを調整
                    content_text_edit.setMaximumHeight(200)
                else:
                    content_text_edit.setPlainText(content_text_edit.full_text)
                    self.toggle_button.setText("Show less")
                    content_text_edit.is_expanded = True
                    # 高さを調整
                    content_text_edit.setMaximumHeight(16777215)  # 制限を解除
            
            self.toggle_button.clicked.connect(toggle_content)
            header_layout.addWidget(self.toggle_button)
            
            # 初期状態では高さを制限
            content_text_edit.setMaximumHeight(200)
        else:
            # プロンプト系または短いコンテンツは全文表示
            content_text_edit.setPlainText(content)
            # 適切な高さに自動調整（プロンプトの場合はより多くの行を許可）
            doc_height = content_text_edit.document().size().height()
            max_height = 400 if is_prompt_content else int(doc_height) + 40
            content_text_edit.setMaximumHeight(max_height)
        
        content_layout.addWidget(content_text_edit)
        
        layout.addWidget(header_widget)
        layout.addWidget(content_widget)
        
        return frame
    
    def create_parameters_section(self):
        """パラメータセクションを作成"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 8px;
                margin: 5px 0px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        
        # ヘッダー部分（タイトルとコピーボタン）
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        # タイトル
        title_label = QLabel("Other metadata")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # パラメータをテキストに変換してコピー用に準備
        param_text_lines = []
        for key, value in self.parsed_prompt_data['parameters'].items():
            param_text_lines.append(f"{key}: {value}")
        param_text = "\n".join(param_text_lines)
        
        # コピーボタン
        copy_param_button = QPushButton("📋")
        copy_param_button.setToolTip("パラメータをコピー")
        copy_param_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                color: white;
                padding: 6px 8px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        
        def copy_parameters():
            clipboard = QApplication.clipboard()
            clipboard.setText(param_text)
            original_text = copy_param_button.text()
            copy_param_button.setText("✓")
            QTimer.singleShot(1000, lambda: copy_param_button.setText(original_text))
        
        copy_param_button.clicked.connect(copy_parameters)
        header_layout.addWidget(copy_param_button)
        
        layout.addWidget(header_widget)
        
        # パラメータをグリッド形式で表示
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(10)
        
        row = 0
        col = 0
        for key, value in self.parsed_prompt_data['parameters'].items():
            param_widget = self.create_parameter_box(key.upper(), value)
            grid_layout.addWidget(param_widget, row, col)
            
            col += 1
            if col >= 3:  # 3列で改行
                col = 0
                row += 1
        
        layout.addWidget(grid_widget)
        return frame
    
    def create_parameter_box(self, key, value):
        """個別のパラメータボックスを作成（コピー・選択機能付き）"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #4a4a4a;
                border-radius: 6px;
                padding: 8px;
                margin: 2px;
            }
            QWidget:hover {
                background-color: #505050;
                border: 1px solid #666666;
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(2)
        
        # ヘッダー部分（キーラベル + コピーボタン）
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        # キーラベル
        key_label = QLabel(key)
        key_label.setStyleSheet("""
            QLabel {
                color: #4a90e2;
                font-size: 11px;
                font-weight: bold;
                margin: 0px;
            }
        """)
        header_layout.addWidget(key_label)
        header_layout.addStretch()
        
        # コピーボタン
        copy_button = QPushButton("📋")
        copy_button.setFixedSize(18, 18)
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                border: none;
                border-radius: 9px;
                color: white;
                font-size: 10px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #888888;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        
        def copy_param():
            param_text = f"{key}: {value}"
            QApplication.clipboard().setText(param_text)
            original_text = copy_button.text()
            copy_button.setText("✓")
            QTimer.singleShot(800, lambda: copy_button.setText(original_text))
        
        copy_button.clicked.connect(copy_param)
        header_layout.addWidget(copy_button)
        
        layout.addLayout(header_layout)
        
        # 値表示部分（選択可能なテキスト）
        value_text = QTextEdit()
        value_text.setPlainText(str(value))
        value_text.setReadOnly(True)
        value_text.setMaximumHeight(35)
        value_text.setMinimumHeight(25)
        value_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        value_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        value_text.setStyleSheet("""
            QTextEdit {
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                margin: 0px;
                padding: 2px 4px;
                border: none;
                background: transparent;
            }
        """)
        layout.addWidget(value_text)
        
        return widget
    
    def create_exif_section(self, layout):
        """EXIF情報セクションを作成"""
        # EXIF情報がない場合は何もしない
        exif_info = {}
        for key, value in self.exif_data.items():
            if not str(key).startswith('AI_') and not str(key).startswith('Meta_'):
                exif_info[key] = value
        
        if not exif_info:
            return
        
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 8px;
                margin: 5px 0px;
                padding: 15px;
            }
        """)
        
        frame_layout = QVBoxLayout(frame)
        
        # タイトル
        title_label = QLabel("📷 EXIF Information")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 10px;
            }
        """)
        frame_layout.addWidget(title_label)
        
        # EXIF情報をテキスト表示
        exif_text = ""
        for tag_id, value in exif_info.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if isinstance(value, bytes):
                value_str = f"<バイナリデータ ({len(value)} bytes)>"
            else:
                value_str = str(value)[:100]
            exif_text += f"{tag_name}: {value_str}\n"
        
        exif_label = QLabel(exif_text)
        exif_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 12px;
                font-family: monospace;
            }
        """)
        exif_label.setWordWrap(True)
        frame_layout.addWidget(exif_label)
        
        layout.addWidget(frame)
    
    def create_current_tags_section(self, layout):
        """現在のタグセクションを作成"""
        # タグシステムが利用可能でない場合は何もしない
        if not TAG_SYSTEM_AVAILABLE:
            return
        
        # タグマネージャーを取得（ImageViewerから）
        try:
            # parent widget（ImageViewer）からタグマネージャーを取得
            parent_widget = self.parent()
            if hasattr(parent_widget, 'tag_manager') and parent_widget.tag_manager:
                tag_manager = parent_widget.tag_manager
                current_tags = tag_manager.get_tags(self.image_path)
                
                if not current_tags:
                    return  # タグがない場合は表示しない
            else:
                return  # タグマネージャーがない場合は何もしない
        except Exception as e:
            return  # エラーの場合は何もしない
        
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 8px;
                margin: 5px 0px;
                padding: 15px;
            }
        """)
        
        frame_layout = QVBoxLayout(frame)
        
        # タイトル行
        title_layout = QHBoxLayout()
        
        # タイトル
        title_label = QLabel(f"🏷️ 現在のタグ ({len(current_tags)}個)")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #4CAF50;
                margin-bottom: 10px;
            }
        """)
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 全コピーボタン
        copy_all_button = QPushButton("📋 全コピー")
        copy_all_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 15px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        copy_all_button.clicked.connect(lambda: QApplication.clipboard().setText(", ".join(current_tags)))
        copy_all_button.setToolTip("全タグをコピー")
        title_layout.addWidget(copy_all_button)
        
        frame_layout.addLayout(title_layout)
        
        # タグ表示エリア
        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)
        tags_layout.setContentsMargins(0, 10, 0, 0)
        tags_layout.setSpacing(8)
        
        # タグを動的フローレイアウトで配置（ダイアログ版）
        self.arrange_dialog_tags_in_flow_layout(current_tags, tags_layout)
        
        frame_layout.addWidget(tags_widget)
        layout.addWidget(frame)
    
    def arrange_dialog_tags_in_flow_layout(self, tags, layout):
        """ダイアログ用のタグ動的フローレイアウト"""
        if not tags:
            return
        
        # ダイアログの利用可能幅（より広い）
        available_width = 600  # ダイアログは幅が広い
        tag_spacing = 8
        tag_min_width = 60
        
        current_row = None
        current_row_layout = None
        current_row_width = 0
        
        for tag in tags:
            # タグの推定幅を計算（10pxフォント + より大きなpadding）
            estimated_width = max(len(tag) * 7 + 40, tag_min_width)  # 10pxフォント×7 + padding + ボタン
            
            # 新しい行が必要かチェック
            need_new_row = (current_row is None or 
                          current_row_width + estimated_width + tag_spacing > available_width)
            
            if need_new_row:
                # 前の行にストレッチを追加
                if current_row_layout:
                    current_row_layout.addStretch()
                
                # 新しい行を作成
                current_row = QWidget()
                current_row_layout = QHBoxLayout(current_row)
                current_row_layout.setContentsMargins(0, 0, 0, 0)
                current_row_layout.setSpacing(tag_spacing)
                layout.addWidget(current_row)
                current_row_width = 0
            
            # タグのボックスを作成
            tag_box = QFrame()
            tag_box.setStyleSheet("""
                QFrame {
                    background-color: #4CAF50;
                    border: 1px solid #45a049;
                    border-radius: 15px;
                    padding: 8px 12px;
                }
                QFrame:hover {
                    background-color: #45a049;
                }
            """)
            
            tag_box_layout = QHBoxLayout(tag_box)
            tag_box_layout.setContentsMargins(8, 4, 8, 4)
            tag_box_layout.setSpacing(6)
            
            # タグテキスト
            tag_label = QLabel(tag)
            tag_label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
            tag_box_layout.addWidget(tag_label)
            
            # コピーボタン
            copy_button = QPushButton("📋")
            copy_button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: white;
                    font-size: 10px;
                    padding: 2px;
                }
                QPushButton:hover {
                    color: #cccccc;
                }
            """)
            copy_button.setFixedSize(20, 20)
            copy_button.clicked.connect(lambda checked, t=tag: QApplication.clipboard().setText(t))
            copy_button.setToolTip(f"「{tag}」をコピー")
            tag_box_layout.addWidget(copy_button)
            
            current_row_layout.addWidget(tag_box)
            current_row_width += estimated_width + tag_spacing
        
        # 最後の行にストレッチを追加
        if current_row_layout:
            current_row_layout.addStretch()


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.sort_order = ('random', True)
        self.current_image_index = 0
        self.display_mode = 'single'  # 'single' または 'grid'
        
        # 4分割グリッド用の独立したインデックス配列とポジション
        self.grid_indices = [[], [], [], []]  # 各グリッドの独立した画像順序
        self.grid_positions = [0, 0, 0, 0]    # 各グリッドの現在位置
        self.selected_grid = -1  # 現在選択されているグリッド（0-3、-1は選択なし）
        
        # タグシステムの初期化
        if TAG_SYSTEM_AVAILABLE:
            try:
                self.tag_manager = TagManager()
            except Exception as e:
                print(f"タグシステムの初期化に失敗しました: {e}")
                self.tag_manager = None
        else:
            self.tag_manager = None
        
        self.initUI()

    def initUI(self):
        self.setWindowTitle("KabaViewer")
        
        # 設定を保存するためのQSettingsオブジェクト
        self.settings = QSettings("MyCompany", "ImageViewerApp")
        
        # 保存されたウィンドウサイズと位置を復元（デフォルト: 800x600, 位置100,100）
        saved_geometry = self.settings.value("window_geometry")
        if saved_geometry:
            self.restoreGeometry(saved_geometry)
        else:
            self.setGeometry(100, 100, 800, 600)

        # 保存されたスライドショーの速度を読み込む（デフォルトは3秒）
        last_speed = self.settings.value("slideshow_speed", 3, int)

        # タブウィジェットを作成
        self.tabs = QTabWidget(self)

        # 画像表示用のタブ
        self.image_tab = QWidget()
        self.image_layout = QHBoxLayout()  # 水平レイアウトに変更
        
        # メイン表示エリア（画像表示部分）
        self.main_display_widget = QWidget()
        self.main_display_layout = QVBoxLayout(self.main_display_widget)
        
        # シングル表示用ラベル（従来のもの）
        self.single_label = QLabel(self)
        self.single_label.setAlignment(Qt.AlignCenter)
        self.single_label.setMinimumSize(800, 600)  # より大きな初期サイズに変更
        
        # 4分割表示用のグリッドレイアウトと4つのラベル
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_labels = []
        
        for i in range(4):
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumSize(200, 150)
            label.setStyleSheet("border: 1px solid gray;")
            # クリックイベント用のカスタムプロパティ
            label.grid_index = i
            label.mousePressEvent = lambda event, idx=i: self.grid_label_clicked(idx)
            self.grid_labels.append(label)
        
        # 2x2で配置
        self.grid_layout.addWidget(self.grid_labels[0], 0, 0)  # 左上
        self.grid_layout.addWidget(self.grid_labels[1], 0, 1)  # 右上
        self.grid_layout.addWidget(self.grid_labels[2], 1, 0)  # 左下
        self.grid_layout.addWidget(self.grid_labels[3], 1, 1)  # 右下
        
        # 初期状態はシングル表示
        self.main_display_layout.addWidget(self.single_label)
        self.main_display_layout.addWidget(self.grid_widget)
        
        # grid_widgetは最初は非表示
        self.grid_widget.setVisible(False)
        
        # サイドバーの作成
        self.create_metadata_sidebar()
        
        # メイン表示エリアをレイアウトに追加（サイドバーをもっと広く）
        self.image_layout.addWidget(self.main_display_widget, 3)  # 3/5の幅を占める
        self.image_layout.addWidget(self.sidebar_widget, 2)  # 2/5の幅を占める（以前より広い）
        
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

        # タグタブを作成
        if TAG_SYSTEM_AVAILABLE and self.tag_manager:
            self.tag_tab = TagTab(self.tag_manager, self)
            self.favorites_tab = FavoritesTab(self.tag_manager, self)
        else:
            self.tag_tab = None
            self.favorites_tab = None

        # タブに追加
        self.tabs.addTab(self.image_tab, "ビュアー")
        self.tabs.addTab(self.favorite_tab, "登録リスト")
        self.tabs.addTab(self.history_tab, "履歴")
        if self.tag_tab:
            self.tabs.addTab(self.tag_tab, "🏷️ タグ")
        if self.favorites_tab:
            self.tabs.addTab(self.favorites_tab, "♡ お気に入り")

        # メインレイアウトにタブを追加
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)

        # バックグラウンド進捗表示エリア（追加）
        self.background_progress_widget = QWidget()
        self.background_progress_widget.setStyleSheet("""
            QWidget {
                background-color: #333333;
                border-top: 1px solid #555555;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
        """)
        self.background_progress_layout = QHBoxLayout(self.background_progress_widget)
        self.background_progress_layout.setContentsMargins(15, 5, 15, 5)
        
        self.background_progress_label = QLabel("準備中...")
        self.background_progress_bar = QProgressBar()
        self.background_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 5px;
                text-align: center;
                background-color: #2b2b2b;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
                margin: 0.5px;
            }
        """)
        self.background_progress_bar.setFixedHeight(15)
        self.background_progress_bar.setMaximumWidth(300)
        
        self.background_progress_layout.addWidget(self.background_progress_label)
        self.background_progress_layout.addStretch()
        self.background_progress_layout.addWidget(self.background_progress_bar)
        
        # キャンセルボタン
        self.bg_cancel_button = QPushButton("キャンセル")
        self.bg_cancel_button.setFixedSize(80, 22)
        self.bg_cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.background_progress_layout.addWidget(self.bg_cancel_button)
        
        self.background_progress_widget.hide() # 初期状態は非表示
        main_layout.addWidget(self.background_progress_widget)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.images = []
        self.current_image_index = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_image)

        self.is_running = False
        self.tag_apply_worker = None  # バックグラウンド適用用

        # 最後に開いたフォルダを開くか、新しく選択する
        last_folder = self.settings.value("last_folder", "")
        if last_folder and os.path.exists(last_folder):  # ここで os.path.exists を使用
            try:
                self.load_images(last_folder)
            except Exception as e:
                print(f"フォルダ読み込みエラー: {e}")
                self.select_folder()
        else:
            self.select_folder()

        # キーボードイベントの設定
        self.setFocusPolicy(Qt.StrongFocus)

        # メニューの設定
        self.init_menu()
    
    def create_metadata_sidebar(self):
        """メタデータ表示用のサイドバーを作成"""
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-left: 1px solid #555555;
            }
        """)
        self.sidebar_layout = QVBoxLayout(self.sidebar_widget)
        self.sidebar_layout.setContentsMargins(10, 10, 10, 10)
        
        # サイドバータイトル
        sidebar_title = QLabel("画像メタデータ")
        sidebar_title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                padding: 10px 0px;
                border-bottom: 1px solid #555555;
            }
        """)
        self.sidebar_layout.addWidget(sidebar_title)
        
        # 切り替えボタン群
        button_layout = QHBoxLayout()
        
        self.sidebar_toggle_button = QPushButton("非表示")
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        button_layout.addWidget(self.sidebar_toggle_button)
        
        self.copy_all_sidebar_button = QPushButton("📋")
        self.copy_all_sidebar_button.setToolTip("全体コピー")
        self.copy_all_sidebar_button.clicked.connect(self.copy_all_metadata_sidebar)
        self.copy_all_sidebar_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        button_layout.addWidget(self.copy_all_sidebar_button)
        
        # お気に入りハートボタン（タグシステムが利用可能な場合）
        if TAG_SYSTEM_AVAILABLE and self.tag_manager:
            self.favorite_heart_button = QPushButton("♡")
            self.favorite_heart_button.setToolTip("お気に入りを切り替え (Fキー)")
            self.favorite_heart_button.clicked.connect(lambda: self.toggle_favorite_status())
            self.favorite_heart_button.setStyleSheet("""
                QPushButton {
                    background-color: #555555;
                    color: #888888;
                    border: none;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
            """)
            button_layout.addWidget(self.favorite_heart_button)
        else:
            self.favorite_heart_button = None
        
        button_layout.addStretch()
        self.sidebar_layout.addLayout(button_layout)
        
        # スクロールエリア
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #3c3c3c;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                border-radius: 6px;
                min-height: 20px;
            }
        """)
        
        # サイドバー用のメタデータコンテナ
        self.sidebar_content_widget = QWidget()
        self.sidebar_content_layout = QVBoxLayout(self.sidebar_content_widget)
        self.sidebar_content_layout.setContentsMargins(0, 10, 0, 0)
        
        # 初期メッセージ
        self.no_data_label = QLabel("画像が選択されていません")
        self.no_data_label.setStyleSheet("""
            QLabel {
                color: #999999;
                font-style: italic;
                text-align: center;
                padding: 20px;
            }
        """)
        self.no_data_label.setAlignment(Qt.AlignCenter)
        self.sidebar_content_layout.addWidget(self.no_data_label)
        
        self.sidebar_scroll.setWidget(self.sidebar_content_widget)
        self.sidebar_layout.addWidget(self.sidebar_scroll)
        
        # サイドバーの表示状態を設定から読み込み
        # 初回起動時のみ非表示、その後は前回の状態を維持
        self.sidebar_visible = self.settings.value("sidebar_visible", False, type=bool)
        
        # 保存された状態に基づいてサイドバーを設定
        if not self.sidebar_visible:
            self.sidebar_widget.setVisible(False)
            self.sidebar_toggle_button.setText("表示")
        
        # サイドバーの最小幅を設定（より広く使いやすく）
        self.sidebar_widget.setMinimumWidth(300)
        self.sidebar_widget.setMaximumWidth(600)
        
        # リストモードの初期化
        self.list_mode = "folder"  # "folder" または "filter"
        self.current_folder = None
        self.filter_description = ""
    
    def toggle_sidebar(self):
        """サイドバーの表示/非表示を切り替え"""
        if self.sidebar_visible:
            self.sidebar_widget.setVisible(False)
            self.sidebar_toggle_button.setText("表示")
            self.sidebar_visible = False
        else:
            self.sidebar_widget.setVisible(True)
            self.sidebar_toggle_button.setText("非表示")
            self.sidebar_visible = True
            # 表示された時に最新のメタデータに更新
            self.update_sidebar_metadata()
        
        # 設定を保存
        self.settings.setValue("sidebar_visible", self.sidebar_visible)
        
        # メッセージを表示
        status_text = "表示" if self.sidebar_visible else "非表示"
        self.show_message(f"サイドバー{status_text}")
    
    def update_sidebar_metadata(self):
        """現在の画像のメタデータでサイドバーを更新"""
        if not self.images:
            self.show_sidebar_no_data()
            return
        
        current_image_path = self.images[self.current_image_index]
        metadata = self.get_exif_data(current_image_path)
        
        # UIを作らずに解析ロジックのみを使用
        parsed_data = ExifInfoDialog.parse_metadata_statically(metadata)
        
        self.populate_sidebar_content(parsed_data, metadata, current_image_path)
    
    def show_sidebar_no_data(self):
        """サイドバーにデータなしメッセージを表示"""
        # 既存のコンテンツをクリア
        self.clear_sidebar_content()
        
        self.no_data_label.setText("画像が選択されていません")
        self.no_data_label.setVisible(True)
    
    def clear_sidebar_content(self):
        """サイドバーの既存コンテンツをクリア"""
        # 既存のウィジェットを全て削除
        while self.sidebar_content_layout.count() > 0:
            item = self.sidebar_content_layout.takeAt(0)  # レイアウトからアイテムを取り除く
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()  # ウィジェットを完全に削除
    
    def copy_all_metadata_sidebar(self):
        """サイドバー版の全体コピー機能"""
        if not self.images:
            return
            
        current_image_path = self.images[self.current_image_index]
        metadata = self.get_exif_data(current_image_path)
        
        # UIを作らずに解析ロジックのみを使用
        parsed_data = ExifInfoDialog.parse_metadata_statically(metadata)
        
        all_text_lines = []
        
        # ファイル情報
        all_text_lines.append(f"ファイル: {os.path.basename(current_image_path)}")
        all_text_lines.append(f"パス: {current_image_path}")
        all_text_lines.append("")
        
        # AI生成画像情報
        if parsed_data['has_ai_data']:
            if parsed_data['prompt']:
                all_text_lines.append("=== Prompt ===")
                all_text_lines.append(parsed_data['prompt'])
                all_text_lines.append("")
            
            if parsed_data['negative_prompt']:
                all_text_lines.append("=== Negative prompt ===")
                all_text_lines.append(parsed_data['negative_prompt'])
                all_text_lines.append("")
            
            if parsed_data['hire_prompt']:
                all_text_lines.append("=== Hires prompt ===")
                all_text_lines.append(parsed_data['hire_prompt'])
                all_text_lines.append("")
            
            if parsed_data['parameters']:
                all_text_lines.append("=== Parameters ===")
                for key, value in parsed_data['parameters'].items():
                    all_text_lines.append(f"{key}: {value}")
                all_text_lines.append("")
        
        # EXIF情報
        exif_info = {}
        for key, value in metadata.items():
            if not str(key).startswith('AI_') and not str(key).startswith('Meta_'):
                exif_info[key] = value
        
        if exif_info:
            all_text_lines.append("=== EXIF Information ===")
            for tag_id, value in exif_info.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if isinstance(value, bytes):
                    value_str = f"<バイナリデータ ({len(value)} bytes)>"
                else:
                    value_str = str(value)[:100]
                all_text_lines.append(f"{tag_name}: {value_str}")
        
        # クリップボードにコピー
        full_text = "\n".join(all_text_lines)
        clipboard = QApplication.clipboard()
        clipboard.setText(full_text)
        
        # ボタンの一時的な変更でコピー完了を示す
        original_text = self.copy_all_sidebar_button.text()
        self.copy_all_sidebar_button.setText("✓")
        QTimer.singleShot(1000, lambda: self.copy_all_sidebar_button.setText(original_text))
    
    def populate_sidebar_content(self, parsed_data, metadata, image_path):
        """サイドバーにメタデータコンテンツを表示"""
        # 既存のコンテンツをクリア
        self.clear_sidebar_content()
        
        # ファイル名表示
        filename_label = QLabel(f"📁 {os.path.basename(image_path)}")
        filename_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 0px;
                border-bottom: 1px solid #444444;
            }
        """)
        filename_label.setWordWrap(True)
        self.sidebar_content_layout.addWidget(filename_label)
        
        # お気に入りハートボタンの状態を更新（タグシステムが利用可能な場合）
        if TAG_SYSTEM_AVAILABLE and self.tag_manager and hasattr(self, 'favorite_heart_button') and self.favorite_heart_button:
            try:
                is_favorite = self.tag_manager.get_favorite_status(image_path)
                self.update_favorite_heart_button(is_favorite)
            except Exception:
                # お気に入り取得エラーは無視
                pass
        
        # 現在のタグセクション（タグシステムが利用可能な場合）
        if TAG_SYSTEM_AVAILABLE and self.tag_manager:
            try:
                current_tags = self.tag_manager.get_tags(image_path)
                if current_tags:
                    tags_section = self.create_sidebar_tags_section(current_tags)
                    self.sidebar_content_layout.addWidget(tags_section)
            except Exception:
                # タグ取得エラーは無視
                pass
        
        # AI生成画像データがある場合
        if parsed_data['has_ai_data']:
            # プロンプトセクション
            if parsed_data['prompt']:
                prompt_section = self.create_sidebar_section(
                    "Prompt", 
                    parsed_data['prompt'], 
                    parsed_data['tags']
                )
                self.sidebar_content_layout.addWidget(prompt_section)
            
            # ネガティブプロンプトセクション
            if parsed_data['negative_prompt']:
                negative_section = self.create_sidebar_section(
                    "Negative prompt",
                    parsed_data['negative_prompt'],
                    []
                )
                self.sidebar_content_layout.addWidget(negative_section)
            
            # Hiresプロンプトセクション
            if parsed_data['hire_prompt']:
                hire_section = self.create_sidebar_section(
                    "Hires prompt",
                    parsed_data['hire_prompt'],
                    []
                )
                self.sidebar_content_layout.addWidget(hire_section)
            
            # パラメータセクション
            if parsed_data['parameters']:
                param_section = self.create_sidebar_parameters_section(parsed_data['parameters'])
                self.sidebar_content_layout.addWidget(param_section)
        
        # EXIF情報セクション
        exif_info = {}
        for key, value in metadata.items():
            if not str(key).startswith('AI_') and not str(key).startswith('Meta_'):
                exif_info[key] = value
        
        if exif_info:
            exif_section = self.create_sidebar_exif_section(exif_info)
            self.sidebar_content_layout.addWidget(exif_section)
        
        # データがない場合
        if not parsed_data['has_ai_data'] and not exif_info:
            no_metadata_label = QLabel("メタデータが見つかりません")
            no_metadata_label.setStyleSheet("""
                QLabel {
                    color: #999999;
                    font-style: italic;
                    text-align: center;
                    padding: 20px;
                }
            """)
            no_metadata_label.setAlignment(Qt.AlignCenter)
            self.sidebar_content_layout.addWidget(no_metadata_label)
        
        # スペーサーを追加
        self.sidebar_content_layout.addStretch()
    
    def update_favorite_heart_button(self, is_favorite):
        """ハートボタンの表示状態を更新"""
        if not hasattr(self, 'favorite_heart_button') or not self.favorite_heart_button:
            return
        
        # ボタンのテキストと色を更新
        if is_favorite:
            # お気に入り済み：赤いハート
            self.favorite_heart_button.setText("♡")
            self.favorite_heart_button.setStyleSheet("""
                QPushButton {
                    background-color: #555555;
                    color: #FF3250;
                    border: none;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
            """)
        else:
            # 未お気に入り：グレーのハート
            self.favorite_heart_button.setText("♡")
            self.favorite_heart_button.setStyleSheet("""
                QPushButton {
                    background-color: #555555;
                    color: #888888;
                    border: none;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
            """)
        
        # ツールチップも更新
        tooltip = "お気に入りから削除 (Fキー)" if is_favorite else "お気に入りに追加 (Fキー)"
        self.favorite_heart_button.setToolTip(tooltip)
    
    def create_sidebar_tags_section(self, tags):
        """サイドバー用のタグセクションを作成"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 6px;
                margin: 5px 0px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        
        # タイトル行
        title_layout = QHBoxLayout()
        
        # タイトルラベル
        title_label = QLabel("🏷️ 現在のタグ")
        title_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        title_layout.addWidget(title_label)
        
        # タグ数表示
        count_label = QLabel(f"({len(tags)}個)")
        count_label.setStyleSheet("""
            QLabel {
                color: #999999;
                font-size: 10px;
            }
        """)
        title_layout.addWidget(count_label)
        
        title_layout.addStretch()
        
        # 全コピーボタン
        copy_all_button = QPushButton("📋")
        copy_all_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        copy_all_button.setFixedSize(25, 20)
        copy_all_button.clicked.connect(lambda: QApplication.clipboard().setText(", ".join(tags)))
        copy_all_button.setToolTip("全タグをコピー")
        title_layout.addWidget(copy_all_button)
        
        layout.addLayout(title_layout)
        
        # タグチップ表示エリア
        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)
        tags_layout.setContentsMargins(0, 8, 0, 0)
        tags_layout.setSpacing(8)
        
        # タグを動的フローレイアウトで配置
        self.arrange_tags_in_flow_layout(tags, tags_layout)
        
        layout.addWidget(tags_widget)
        
        return frame
    
    def create_tag_chip(self, tag):
        """個別タグのチップを作成"""
        chip_frame = QFrame()
        chip_frame.setStyleSheet("""
            QFrame {
                background-color: #4CAF50;
                border: 1px solid #45a049;
                border-radius: 12px;
            }
            QFrame:hover {
                background-color: #45a049;
            }
        """)
        chip_frame.setFixedHeight(36)
        
        # 文字幅に合わせて横幅を調整
        from PyQt5.QtWidgets import QSizePolicy
        chip_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        chip_layout = QHBoxLayout(chip_frame)
        chip_layout.setContentsMargins(8, 0, 8, 0)
        chip_layout.setSpacing(4)
        
        # タグテキスト
        tag_label = QLabel(tag)
        tag_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        chip_layout.addWidget(tag_label)
        
        # コピーボタン
        copy_button = QPushButton("📋")
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 11px;
                padding: 0px;
            }
            QPushButton:hover {
                color: #cccccc;
            }
        """)
        copy_button.setFixedSize(16, 16)
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(tag))
        copy_button.setToolTip(f"「{tag}」をコピー")
        chip_layout.addWidget(copy_button)
        
        return chip_frame
    
    def arrange_tags_in_flow_layout(self, tags, layout):
        """タグを動的フローレイアウトで配置"""
        if not tags:
            return
        
        # サイドバーの利用可能幅を推定（大体300-400px程度）
        available_width = 280  # padding等を考慮した実際の幅
        tag_spacing = 8
        tag_min_width = 50  # 最小タグ幅
        
        current_row = None
        current_row_layout = None
        current_row_width = 0
        
        for tag in tags:
            # タグの推定幅を計算（文字数 × 10px + padding + ボタン）
            estimated_width = max(len(tag) * 7 + 32, tag_min_width)  # 10pxフォント×7 + padding + コピーボタン
            
            # 新しい行が必要かチェック
            need_new_row = (current_row is None or 
                          current_row_width + estimated_width + tag_spacing > available_width)
            
            if need_new_row:
                # 前の行にストレッチを追加
                if current_row_layout:
                    current_row_layout.addStretch()
                
                # 新しい行を作成
                current_row = QWidget()
                current_row_layout = QHBoxLayout(current_row)
                current_row_layout.setContentsMargins(0, 0, 0, 0)
                current_row_layout.setSpacing(tag_spacing)
                current_row_layout.setAlignment(Qt.AlignLeft)
                layout.addWidget(current_row)
                current_row_width = 0
            
            # タグチップを作成して追加
            tag_chip = self.create_tag_chip(tag)
            current_row_layout.addWidget(tag_chip)
            current_row_width += estimated_width + tag_spacing
        
        # 最後の行にストレッチを追加
        if current_row_layout:
            current_row_layout.addStretch()
    
    def create_sidebar_section(self, title, content, tags):
        """サイドバー用のセクションを作成"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 6px;
                margin: 5px 0px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # ヘッダー部分
        header_layout = QHBoxLayout()
        
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 5px;
            }
        """)
        header_layout.addWidget(title_label)
        
        # タグ表示
        for tag in tags:
            tag_label = QLabel(tag)
            tag_label.setStyleSheet("""
                QLabel {
                    background-color: #4a90e2;
                    color: white;
                    padding: 2px 6px;
                    border-radius: 8px;
                    font-size: 9px;
                    margin-left: 5px;
                }
            """)
            header_layout.addWidget(tag_label)
        
        header_layout.addStretch()
        
        # コピーボタン
        copy_btn = QPushButton("📋")
        copy_btn.setToolTip("コピー")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                color: white;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        
        def copy_section_content():
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
            original_text = copy_btn.text()
            copy_btn.setText("✓")
            QTimer.singleShot(800, lambda: copy_btn.setText(original_text))
        
        copy_btn.clicked.connect(copy_section_content)
        header_layout.addWidget(copy_btn)
        
        layout.addLayout(header_layout)
        
        # コンテンツ部分（サイドバー用は常に短縮表示）
        content_text = QTextEdit()
        content_text.setReadOnly(True)
        content_text.setStyleSheet("""
            QTextEdit {
                color: #cccccc;
                font-size: 11px;
                background-color: transparent;
                border: none;
                padding: 2px;
            }
        """)
        content_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        content_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # プロンプト系のコンテンツは全文表示
        is_prompt_content = "prompt" in title.lower() or "プロンプト" in title
        
        if is_prompt_content:
            # プロンプト系は全文表示
            display_content = content
        else:
            # その他のコンテンツは800文字まで表示
            display_content = content[:800] + "..." if len(content) > 800 else content
            
        content_text.setPlainText(display_content)
        
        # プロンプト系の場合は高さ制限を大幅に緩和、その他は制限を維持
        max_height = 400 if is_prompt_content else 200
        content_text.setMaximumHeight(max_height)
        
        layout.addWidget(content_text)
        
        return frame
    
    def create_sidebar_parameter_item(self, key, value):
        """サイドバー用の個別パラメータアイテムを作成（コピー・選択機能付き）"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #464646;
                border-radius: 4px;
                padding: 4px;
                margin: 1px;
            }
            QWidget:hover {
                background-color: #525252;
                border: 1px solid #666666;
            }
        """)
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)
        
        # キーラベル
        key_label = QLabel(f"{key}:")
        key_label.setStyleSheet("""
            QLabel {
                color: #4a90e2;
                font-size: 10px;
                font-weight: bold;
                min-width: 50px;
            }
        """)
        layout.addWidget(key_label)
        
        # 値テキスト（選択可能）
        value_text = QTextEdit()
        value_text.setPlainText(str(value))
        value_text.setReadOnly(True)
        value_text.setMaximumHeight(20)
        value_text.setMinimumHeight(20)
        value_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        value_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        value_text.setStyleSheet("""
            QTextEdit {
                color: #ffffff;
                font-size: 10px;
                border: none;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
        """)
        layout.addWidget(value_text)
        layout.addStretch()
        
        # コピーボタン
        copy_button = QPushButton("📋")
        copy_button.setFixedSize(14, 14)
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                border: none;
                border-radius: 7px;
                color: white;
                font-size: 8px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #888888;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        
        def copy_param():
            param_text = f"{key}: {value}"
            QApplication.clipboard().setText(param_text)
            original_text = copy_button.text()
            copy_button.setText("✓")
            QTimer.singleShot(600, lambda: copy_button.setText(original_text))
        
        copy_button.clicked.connect(copy_param)
        layout.addWidget(copy_button)
        
        return widget
    
    def create_sidebar_parameters_section(self, parameters):
        """サイドバー用のパラメータセクションを作成"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 6px;
                margin: 5px 0px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # ヘッダー
        header_layout = QHBoxLayout()
        title_label = QLabel("Parameters")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 5px;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # コピーボタン
        copy_btn = QPushButton("📋")
        copy_btn.setToolTip("パラメータをコピー")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                color: white;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        
        param_text_lines = [f"{key}: {value}" for key, value in parameters.items()]
        param_text = "\n".join(param_text_lines)
        
        def copy_params():
            clipboard = QApplication.clipboard()
            clipboard.setText(param_text)
            original_text = copy_btn.text()
            copy_btn.setText("✓")
            QTimer.singleShot(800, lambda: copy_btn.setText(original_text))
        
        copy_btn.clicked.connect(copy_params)
        header_layout.addWidget(copy_btn)
        layout.addLayout(header_layout)
        
        # パラメータを縦並びで表示（個別コピー・選択機能付き）
        for key, value in parameters.items():
            param_item = self.create_sidebar_parameter_item(key.upper(), value)
            layout.addWidget(param_item)
        
        return frame
    
    def create_sidebar_exif_section(self, exif_info):
        """サイドバー用のEXIF情報セクションを作成"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 6px;
                margin: 5px 0px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        
        title_label = QLabel("📷 EXIF Info")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(title_label)
        
        # EXIF情報をテキストで表示
        exif_text_lines = []
        for tag_id, value in exif_info.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if isinstance(value, bytes):
                value_str = f"<バイナリ ({len(value)}B)>"
            else:
                value_str = str(value)[:50]  # サイドバー用に短縮
            exif_text_lines.append(f"{tag_name}: {value_str}")
        
        exif_text_edit = QTextEdit()
        exif_text_edit.setReadOnly(True)
        exif_text_edit.setPlainText("\n".join(exif_text_lines))
        exif_text_edit.setStyleSheet("""
            QTextEdit {
                color: #cccccc;
                font-size: 9px;
                font-family: monospace;
                background-color: transparent;
                border: none;
            }
        """)
        exif_text_edit.setMaximumHeight(150)  # サイドバーが広くなったので高さを増やす
        exif_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        layout.addWidget(exif_text_edit)
        
        return frame

    # クリックでスライドショーをトグルするメソッドを追加（ビューアータブ選択時のみ）
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.tabs.currentWidget() == self.image_tab:
            # サイドバー内でのクリックかどうかを確認
            if self.sidebar_widget.isVisible():
                sidebar_geometry = self.sidebar_widget.geometry()
                click_pos = event.pos()
                
                # クリック位置がサイドバー内の場合はスライドショーを開始しない
                if sidebar_geometry.contains(click_pos):
                    return
            
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
            self.initialize_grid_system()  # 独立したグリッドシステムを初期化
            self.show_image()
            self.settings.setValue("last_folder", folder_path)
            self.history_tab.update_folder_history(folder_path)
            
            # フォルダモードに設定
            self.list_mode = "folder"
            self.current_folder = folder_path
            self.update_window_title()
            
            # お気に入りタブも更新
            if TAG_SYSTEM_AVAILABLE and self.favorites_tab:
                self.favorites_tab.update_favorites_list()
            
            # ZIP圧縮メニューの状態を更新
            self.update_zip_menu_state()
        except Exception as e:
            print(f"load_images Error: {e}")  # エラーの内容を出力
            # フォルダ選択ダイアログは呼び出し元で処理される
            raise  # エラーを再発生させて呼び出し元で処理
    
    def load_filtered_images(self, image_list, description="フィルタリング結果"):
        """フィルタリングされた画像リストをビューアーに読み込み"""
        try:
            # 存在する画像ファイルのみをフィルタ
            self.images = [img_path for img_path in image_list if os.path.exists(img_path)]
            
            if not self.images:
                raise ValueError("No valid images in the filtered list.")
            
            self.current_image_index = 0  # 最初の画像から開始
            self.sort_images()
            self.initialize_grid_system()
            self.show_image()
            
            # フィルタモードに設定
            self.list_mode = "filter"
            self.filter_description = description
            self.current_folder = None  # フォルダベースではない
            self.update_window_title()
            
            # ビューアータブに切り替え
            self.tabs.setCurrentWidget(self.image_tab)
            
            self.show_message(f"📋 {description} ({len(self.images)}枚)")
            
            # ZIP圧縮メニューの状態を更新
            self.update_zip_menu_state()
        except Exception as e:
            print(f"load_filtered_images Error: {e}")
            raise
    
    def update_window_title(self):
        """ウィンドウタイトルを現在の状態に応じて更新"""
        if hasattr(self, 'list_mode'):
            if self.list_mode == "folder" and hasattr(self, 'current_folder'):
                folder_name = os.path.basename(self.current_folder) if self.current_folder else ""
                title = f"KabaViewer - {folder_name} ({len(self.images)}枚)" if self.images else "KabaViewer"
            elif self.list_mode == "filter" and hasattr(self, 'filter_description'):
                title = f"KabaViewer - {self.filter_description} ({len(self.images)}枚)" if self.images else "KabaViewer"
            else:
                title = "KabaViewer"
        else:
            title = "KabaViewer"
        
        self.setWindowTitle(title)

    def show_image(self):
        if self.display_mode == 'single':
            self.show_image_single()
        else:
            self.show_image_grid()
        
        # サイドバーが表示されている場合のみメタデータを更新
        if self.sidebar_visible:
            self.update_sidebar_metadata()

    def initialize_grid_system(self):
        """4つの独立したランダムグリッドシステムを初期化"""
        if not self.images:
            return
        
        total_images = len(self.images)
        
        # 各グリッドに独立したランダム配列を作成
        for i in range(4):
            # 全画像インデックスのリストを作成
            indices = list(range(total_images))
            # 各グリッドを独立してランダムシャッフル
            random.shuffle(indices)
            self.grid_indices[i] = indices
            self.grid_positions[i] = 0  # 各グリッドの開始位置をリセット
        
        # 独立グリッドシステム初期化完了

    def shuffle_grid_system(self):
        """グリッドシステムを再シャッフル（手動実行用）"""
        self.initialize_grid_system()
        if self.display_mode == 'grid':
            self.show_image()

    def draw_favorite_heart_on_canvas(self, canvas, heart_size=40, image_x=0, image_y=0, image_width=0, image_height=0):
        """キャンバス上の画像の左下を基準にハートを描画"""
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # カードのパディング（正方形に近づける）
        card_padding = 8  # 均等なパディング
        card_width = heart_size + card_padding * 2
        card_height = heart_size + card_padding * 2
        
        # カードの位置（画像の左下から固定距離）
        margin_x = 30  # 画像の左端からのマージン（小さくして右に寄せる）
        margin_y = 10  # 画像の下端からのマージン（小さくして下に寄せる）
        card_x = image_x + margin_x
        card_y = image_y + image_height - card_height - margin_y
        
        # 半透明の黒いカード背景を描画
        card_color = QColor(0, 0, 0, 80)  # 黒、透明度80/255
        painter.setBrush(QBrush(card_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(card_x, card_y, card_width, card_height, 8, 8)
        
        # ハートの中心位置（カード内の中央）
        center_x = card_x + card_padding + heart_size / 2
        center_y = card_y + card_padding + heart_size / 2
        
        # ハートの形を作成
        heart_path = QPainterPath()
        
        # ハートのサイズ調整
        scale = heart_size / 40.0
        
        # ハートの上部（2つの半円）
        # 左側の半円
        heart_path.moveTo(QPointF(center_x, center_y - 5 * scale))
        heart_path.cubicTo(
            QPointF(center_x, center_y - 12 * scale),
            QPointF(center_x - 12 * scale, center_y - 12 * scale),
            QPointF(center_x - 12 * scale, center_y - 5 * scale)
        )
        # 左側の半円の下部
        heart_path.cubicTo(
            QPointF(center_x - 12 * scale, center_y + 2 * scale),
            QPointF(center_x, center_y + 10 * scale),
            QPointF(center_x, center_y + 15 * scale)
        )
        # 右側の半円の下部
        heart_path.cubicTo(
            QPointF(center_x, center_y + 10 * scale),
            QPointF(center_x + 12 * scale, center_y + 2 * scale),
            QPointF(center_x + 12 * scale, center_y - 5 * scale)
        )
        # 右側の半円
        heart_path.cubicTo(
            QPointF(center_x + 12 * scale, center_y - 12 * scale),
            QPointF(center_x, center_y - 12 * scale),
            QPointF(center_x, center_y - 5 * scale)
        )
        
        heart_path.closeSubpath()
        
        # 赤で塗りつぶし、濃い赤の縁取り
        painter.setBrush(QBrush(QColor(255, 50, 80)))  # 明るい赤
        painter.setPen(QPen(QColor(200, 20, 50), 2))  # 濃い赤の縁
        painter.drawPath(heart_path)
        
        painter.end()
        
        return canvas
    
    def draw_favorite_heart(self, pixmap, heart_size=40):
        """pixmapの左下に半透明の黒いカード背景付きの赤いハートを描画（グリッド用）"""
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # カードのパディング（正方形に近づける）
        card_padding = 8  # 均等なパディング
        card_width = heart_size + card_padding * 2
        card_height = heart_size + card_padding * 2
        
        # カードの位置（画像の左下から固定距離）
        margin_x = 15  # 左端からのマージン（グリッドでは小さめに）
        margin_y = 5  # 下端からのマージン（グリッドでは小さめに）
        card_x = margin_x
        card_y = pixmap.height() - card_height - margin_y
        
        # 半透明の黒いカード背景を描画
        card_color = QColor(0, 0, 0, 80)  # 黒、透明度80/255
        painter.setBrush(QBrush(card_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(card_x, card_y, card_width, card_height, 8, 8)
        
        # ハートの中心位置（カード内の中央）
        center_x = card_x + card_padding + heart_size / 2
        center_y = card_y + card_padding + heart_size / 2
        
        # ハートの形を作成
        heart_path = QPainterPath()
        
        # ハートのサイズ調整
        scale = heart_size / 40.0
        
        # ハートの上部（2つの半円）
        # 左側の半円
        heart_path.moveTo(QPointF(center_x, center_y - 5 * scale))
        heart_path.cubicTo(
            QPointF(center_x, center_y - 12 * scale),
            QPointF(center_x - 12 * scale, center_y - 12 * scale),
            QPointF(center_x - 12 * scale, center_y - 5 * scale)
        )
        # 左側の半円の下部
        heart_path.cubicTo(
            QPointF(center_x - 12 * scale, center_y + 2 * scale),
            QPointF(center_x, center_y + 10 * scale),
            QPointF(center_x, center_y + 15 * scale)
        )
        # 右側の半円の下部
        heart_path.cubicTo(
            QPointF(center_x, center_y + 10 * scale),
            QPointF(center_x + 12 * scale, center_y + 2 * scale),
            QPointF(center_x + 12 * scale, center_y - 5 * scale)
        )
        # 右側の半円
        heart_path.cubicTo(
            QPointF(center_x + 12 * scale, center_y - 12 * scale),
            QPointF(center_x, center_y - 12 * scale),
            QPointF(center_x, center_y - 5 * scale)
        )
        
        heart_path.closeSubpath()
        
        # 赤で塗りつぶし、濃い赤の縁取り
        painter.setBrush(QBrush(QColor(255, 50, 80)))  # 明るい赤
        painter.setPen(QPen(QColor(200, 20, 50), 2))  # 濃い赤の縁
        painter.drawPath(heart_path)
        
        painter.end()
        
        return pixmap

    def show_image_single(self):
        """シングル表示モード（従来の1枚表示）"""
        if self.images:
            image_path = self.images[self.current_image_index]
            try:
                with Image.open(image_path) as img:
                    # 実際の利用可能スペースを計算（サイドバーとマージンを考慮）
                    total_width = self.width()
                    total_height = self.height()
                    
                    # サイドバーが表示されている場合はその分を差し引く
                    sidebar_width = 0
                    if self.sidebar_visible and hasattr(self, 'sidebar_widget'):
                        sidebar_width = self.sidebar_widget.width()
                    
                    # 利用可能な画像表示スペース（マージンも考慮）
                    available_width = total_width - sidebar_width - 50  # 50pxマージン
                    available_height = total_height - 150  # タブとメニューバー分を差し引く
                    
                    # 最小サイズの保証
                    available_width = max(400, available_width)
                    available_height = max(300, available_height)
                    
                    image_ratio = img.width / img.height
                    window_ratio = available_width / available_height

                    if window_ratio > image_ratio:
                        new_height = available_height
                        new_width = int(available_height * image_ratio)
                    else:
                        new_width = available_width
                        new_height = int(available_width / image_ratio)

                    # 高品質リサイズ
                    image = img.resize((new_width, new_height), Image.LANCZOS)
                    image_rgba = image.convert("RGBA")
                    
                    # バイト配列を変数に保持してGCを防ぐ
                    image_bytes = image_rgba.tobytes("raw", "RGBA")
                    
                    # 表示領域サイズの透明なキャンバスを作成
                    canvas = QPixmap(available_width, available_height)
                    canvas.fill(Qt.transparent)
                    
                    # キャンバスに画像を中央配置で描画
                    painter = QPainter(canvas)
                    image_x = (available_width - new_width) // 2
                    image_y = (available_height - new_height) // 2
                    
                    # QImage作成時にバッファのコピーを確実に保持
                    qimage = QImage(image_bytes, new_width, new_height, QImage.Format_RGBA8888).copy()
                    image_pixmap = QPixmap.fromImage(qimage)
                    painter.drawPixmap(image_x, image_y, image_pixmap)
                    painter.end()
                
                # お気に入りの場合はハートを表示（画像の左下を基準）
                if self.tag_manager:
                    try:
                        is_favorite = self.tag_manager.get_favorite_status(image_path)
                        if is_favorite:
                            # 画像の位置情報を渡してハートを描画
                            canvas = self.draw_favorite_heart_on_canvas(canvas, heart_size=25, 
                                                                        image_x=image_x, 
                                                                        image_y=image_y, 
                                                                        image_width=new_width, 
                                                                        image_height=new_height)
                    except Exception as e:
                        print(f"Failed to check favorite status: {e}")

                # ピクセル単位で正確に表示
                self.single_label.setPixmap(canvas)

                self.update_window_title()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to display image {image_path}.")
                print(f"Failed to load image {image_path}: {e}")

    def show_image_grid(self):
        """4分割グリッド表示モード"""
        if not self.images:
            return
            
        # 現在のindexを中心とした4枚の画像インデックスを計算
        indices = self.calculate_grid_indices()
        
        for i, img_index in enumerate(indices):
            if 0 <= img_index < len(self.images):
                try:
                    image_path = self.images[img_index]
                    with Image.open(image_path) as img:
                        # グリッド用にサイズ調整（小さめ）
                        label_size = self.grid_labels[i].size()
                        preview_size = (label_size.width() - 10, label_size.height() - 10)
                        
                        # 縦横比を維持してリサイズ
                        img.thumbnail(preview_size, Image.Resampling.LANCZOS)
                        
                        # QPixmapに変換（バイト配列を変数に保持）
                        image_rgba = img.convert("RGBA")
                        w, h = image_rgba.size
                        image_bytes = image_rgba.tobytes("raw", "RGBA")
                        qimage = QImage(image_bytes, w, h, QImage.Format_RGBA8888).copy()
                        pixmap = QPixmap.fromImage(qimage)
                    
                    # お気に入りの場合はハートを表示（グリッドでは小さめのハート）
                    if self.tag_manager:
                        try:
                            is_favorite = self.tag_manager.get_favorite_status(image_path)
                            if is_favorite:
                                pixmap = self.draw_favorite_heart(pixmap, heart_size=15)
                        except Exception as e:
                            print(f"Failed to check favorite status: {e}")
                    
                    # 選択されたグリッドには赤い境界線、その他は通常の境界線
                    # selected_grid が -1 の場合はどのグリッドも選択されていない
                    if self.selected_grid != -1 and i == self.selected_grid:
                        self.grid_labels[i].setStyleSheet("border: 3px solid red;")
                    else:
                        self.grid_labels[i].setStyleSheet("border: 1px solid gray;")
                    
                    self.grid_labels[i].setPixmap(pixmap)
                    
                except Exception as e:
                    self.grid_labels[i].setText("読み込み\nエラー")
                    print(f"Failed to load grid image {image_path}: {e}")
                    
                    # エラー時も選択状態に応じて境界線を設定
                    if self.selected_grid != -1 and i == self.selected_grid:
                        self.grid_labels[i].setStyleSheet("border: 3px solid red;")
                    else:
                        self.grid_labels[i].setStyleSheet("border: 1px solid gray;")
            else:
                self.grid_labels[i].clear()
                self.grid_labels[i].setText("画像なし")
                
                # 画像がない場合も選択状態に応じて境界線を設定
                if self.selected_grid != -1 and i == self.selected_grid:
                    self.grid_labels[i].setStyleSheet("border: 3px solid red;")
                else:
                    self.grid_labels[i].setStyleSheet("border: 1px solid gray;")
        
        self.update_window_title()

    def calculate_grid_indices(self):
        """グリッド表示用の4つの画像インデックスを計算（独立ランダム配列使用）"""
        if not self.images or not self.grid_indices[0]:
            return [0, 0, 0, 0]
        
        indices = []
        for i in range(4):
            # 各グリッドの現在位置から画像インデックスを取得
            grid_array = self.grid_indices[i]
            position = self.grid_positions[i] % len(grid_array)
            actual_image_index = grid_array[position]
            indices.append(actual_image_index)
        
        return indices

    def update_window_title(self):
        """ウィンドウタイトルを更新"""
        if self.images:
            folder_name = os.path.basename(os.path.dirname(self.images[self.current_image_index]))
            order_type, is_ascending = self.sort_order
            order_type_str = {
                'random': 'ランダム',
                'date_modified': '変更日順',
                'date_added': '追加日順',
                'date_created': '作成日順',
                'name': '名前順'
            }.get(order_type, '不明な順番')
            order_direction = '昇順' if is_ascending else '降順'
            
            mode_str = "シングル" if self.display_mode == 'single' else "4分割"
            
            self.setWindowTitle(f"KabaViewer - {folder_name} - {self.current_image_index + 1}/{len(self.images)} - {order_type_str} ({order_direction}) - {mode_str}モード")

    def grid_label_clicked(self, grid_index):
        """グリッド内の画像がクリックされた時の処理（トグル動作）"""
        if 0 <= grid_index < 4:
            # 既に選択されているグリッドをクリックした場合は選択解除
            if self.selected_grid == grid_index:
                self.selected_grid = -1  # 選択解除
                self.show_message("グリッド選択を解除")
            else:
                # 新しいグリッドを選択
                self.selected_grid = grid_index
                
                # そのグリッドの現在の画像を全体の選択として設定
                indices = self.calculate_grid_indices()
                if indices and 0 <= indices[grid_index] < len(self.images):
                    self.current_image_index = indices[grid_index]
                
                self.show_message(f"グリッド {grid_index + 1} を選択")
            
            self.show_image()  # 表示を更新（選択状態の境界線も更新）

    def toggle_display_mode(self):
        """表示モードを切り替える（シングル ⇔ 4分割）"""
        if self.display_mode == 'single':
            self.display_mode = 'grid'
            self.single_label.setVisible(False)
            self.grid_widget.setVisible(True)
        else:
            self.display_mode = 'single'
            self.single_label.setVisible(True)
            self.grid_widget.setVisible(False)
        
        self.show_image()  # 新しいモードで表示更新
        self.show_message(f"{'4分割' if self.display_mode == 'grid' else 'シングル'}モードに切り替え")

    def set_display_mode(self, mode):
        """表示モードを指定のモードに設定"""
        if mode != self.display_mode:
            self.display_mode = mode
            if mode == 'single':
                self.single_label.setVisible(True)
                self.grid_widget.setVisible(False)
            else:
                self.single_label.setVisible(False)
                self.grid_widget.setVisible(True)
            
            # メニューバーのチェック状態を更新
            if hasattr(self, 'single_display_action') and hasattr(self, 'grid_display_action'):
                self.single_display_action.setChecked(mode == 'single')
                self.grid_display_action.setChecked(mode == 'grid')
            
            self.show_image()
            self.show_message(f"{'4分割' if mode == 'grid' else 'シングル'}モードに切り替え")

    def next_image(self):
        if self.display_mode == 'single':
            # シングルモードでは従来通り
            self.current_image_index = (self.current_image_index + 1) % len(self.images)
        else:
            # グリッドモードでは4つのグリッドが独立して次へ進む
            for i in range(4):
                if self.grid_indices[i]:
                    self.grid_positions[i] = (self.grid_positions[i] + 1) % len(self.grid_indices[i])
        
        self.show_image()

    def previous_image(self):
        if self.display_mode == 'single':
            # シングルモードでは従来通り
            self.current_image_index = (self.current_image_index - 1) % len(self.images)
        else:
            # グリッドモードでは4つのグリッドが独立して前へ戻る
            for i in range(4):
                if self.grid_indices[i]:
                    self.grid_positions[i] = (self.grid_positions[i] - 1) % len(self.grid_indices[i])
        
        self.show_image()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.next_image()
        elif event.key() == Qt.Key_Left:
            self.previous_image()
        elif event.key() == Qt.Key_G:
            # Gキーで表示モード切り替え
            self.toggle_display_mode()
        elif event.key() == Qt.Key_Tab:
            # Tabキーで表示モード切り替え
            self.toggle_display_mode()
        elif event.key() == Qt.Key_R:
            # Rキーで独立グリッドを再シャッフル
            if self.display_mode == 'grid':
                self.shuffle_grid_system()
                self.show_message("グリッドを再シャッフルしました")
        elif event.key() == Qt.Key_S:
            # Sキーでサイドバー切り替え
            if self.tabs.currentWidget() == self.image_tab:
                self.toggle_sidebar()
        elif event.key() == Qt.Key_Delete:
            # Deleteキーで画像を削除
            if self.tabs.currentWidget() == self.image_tab:
                self.delete_current_image()
        elif event.key() == Qt.Key_T:
            # Tキーでタグ編集ダイアログを表示
            if self.tabs.currentWidget() == self.image_tab and TAG_SYSTEM_AVAILABLE and self.tag_manager:
                self.show_tag_edit_dialog()
        elif event.key() == Qt.Key_F:
            # Fキーでお気に入り状態をトグル
            if self.tabs.currentWidget() == self.image_tab and TAG_SYSTEM_AVAILABLE and self.tag_manager:
                self.toggle_favorite_status()
        elif event.key() == Qt.Key_A:
            # Aキーでプロンプト解析による自動タグ付けを開始
            if self.tabs.currentWidget() == self.image_tab and TAG_SYSTEM_AVAILABLE and self.tag_manager:
                self.show_auto_tag_dialog()

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

            # 表示モード切り替えメニューを追加
            display_menu = context_menu.addMenu("表示モード")
            single_action = display_menu.addAction("シングル表示")
            grid_action = display_menu.addAction("4分割表示")
            
            # 現在のモードにチェックを入れる
            single_action.setCheckable(True)
            grid_action.setCheckable(True)
            if self.display_mode == 'single':
                single_action.setChecked(True)
            else:
                grid_action.setChecked(True)
            
            single_action.triggered.connect(lambda: self.set_display_mode('single'))
            grid_action.triggered.connect(lambda: self.set_display_mode('grid'))

            # 4分割モードの時のみシャッフル機能を追加
            if self.display_mode == 'grid':
                shuffle_action = context_menu.addAction("グリッドを再シャッフル")
                shuffle_action.triggered.connect(self.shuffle_grid_system)

            # 区切り線を追加
            context_menu.addSeparator()
            
            # サイドバー表示/非表示メニューを追加
            if self.sidebar_visible:
                sidebar_action = context_menu.addAction("📋 サイドバーを非表示 (S)")
            else:
                sidebar_action = context_menu.addAction("📋 サイドバーを表示 (S)")
            sidebar_action.triggered.connect(self.toggle_sidebar)

            # タグ関連メニューをサブメニューにまとめる（タグシステムが利用可能な場合）
            if TAG_SYSTEM_AVAILABLE and self.tag_manager:
                context_menu.addSeparator()
                tag_menu = context_menu.addMenu("🏷️ タグ")
                
                # タグ編集
                tag_edit_action = tag_menu.addAction("✏️ タグを編集 (T)")
                tag_edit_action.triggered.connect(self.show_tag_edit_dialog)
                
                tag_menu.addSeparator()
                
                # 自動タグ付け
                auto_tag_action = tag_menu.addAction("🤖 プロンプト解析で自動タグ付け (A)")
                auto_tag_action.triggered.connect(self.show_auto_tag_dialog)
                
                tag_menu.addSeparator()
                
                # 設定メニュー
                exclude_settings_action = tag_menu.addAction("⚙️ 除外キーワード設定")
                exclude_settings_action.triggered.connect(self.show_exclude_settings_dialog)
                
                mapping_rules_action = tag_menu.addAction("🔧 自動タグルール設定")
                mapping_rules_action.triggered.connect(self.show_mapping_rules_dialog)

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
            try:
                self.load_images(folder_path)
            except ValueError as e:
                # 画像が見つからない場合などのエラー
                QMessageBox.warning(self, "エラー", f"選択されたフォルダに画像が見つかりませんでした:\n{folder_path}\n別のフォルダを選択してください。")
                self.select_folder()  # 再度選択を促す
            except Exception as e:
                # その他の読み込みエラー
                QMessageBox.warning(self, "エラー", f"フォルダの読み込み中にエラーが発生しました:\n{str(e)}")

    def init_menu(self):
        menubar = self.menuBar()
        # [ファイル]メニュー
        file_menu = menubar.addMenu('ファイル')
        select_folder_action = file_menu.addAction('フォルダを選択')
        select_folder_action.triggered.connect(self.select_folder)
        
        # 区切り線を追加
        file_menu.addSeparator()
        
        # リストをZIP圧縮メニュー項目を追加
        zip_images_action = file_menu.addAction('📦 リストをZIP圧縮')
        zip_images_action.triggered.connect(self.export_images_to_zip)
        zip_images_action.setEnabled(False)  # 初期状態では無効
        self.zip_images_action = zip_images_action  # 後で有効/無効を切り替えるために保存

        # [表示]メニュー
        show_menu = menubar.addMenu('表示')

        # サイドバー切り替えアクション
        sidebar_action = show_menu.addAction('サイドバー切り替え (S)')
        sidebar_action.triggered.connect(self.toggle_sidebar)

        # 区切り線
        show_menu.addSeparator()

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

        # 表示モードのサブメニューを追加
        display_mode_menu = show_menu.addMenu('表示モード')
        
        single_display_action = display_mode_menu.addAction('シングル表示')
        single_display_action.setCheckable(True)
        single_display_action.setChecked(True)  # 初期状態はシングル表示
        single_display_action.triggered.connect(lambda: self.set_display_mode('single'))
        
        grid_display_action = display_mode_menu.addAction('4分割表示')
        grid_display_action.setCheckable(True)
        grid_display_action.triggered.connect(lambda: self.set_display_mode('grid'))
        
        # 表示モードアクションをインスタンス変数として保存（状態管理用）
        self.single_display_action = single_display_action
        self.grid_display_action = grid_display_action

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

        # [登録リスト]メニュー
        favorite_menu = menubar.addMenu('登録リスト')
        add_favorite_action = QAction('登録リストに追加', self)
        add_favorite_action.triggered.connect(self.add_current_folder_to_favorites)
        favorite_menu.addAction(add_favorite_action)



    def add_current_folder_to_favorites(self):
        current_folder = self.settings.value("last_folder", "")
        if current_folder and os.path.exists(current_folder):
            self.favorite_tab.add_to_favorites(current_folder)
        else:
            QMessageBox.warning(self, "Error", "No valid folder to add to registered list.")

    def delete_current_image(self):
        if not self.images:
            return
        current_image_path = self.images[self.current_image_index]
        # 確認メッセージの表示
        reply = QMessageBox.question(self, '画像を削除',
                                     f'本当に {os.path.basename(current_image_path)} を削除しますか？',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            try:
                os.remove(current_image_path)  # 画像ファイルを削除
                del self.images[self.current_image_index]  # リストから削除

                if self.images:
                    # 画像リストが残っている場合は次の画像を表示
                    self.current_image_index %= len(self.images)
                    # グリッドシステムを再初期化（削除された画像を反映）
                    self.initialize_grid_system()
                    self.show_image()
                else:
                    # 画像リストが空になった場合はラベルをクリア
                    self.single_label.clear()
                    # グリッドラベルもクリア
                    for label in self.grid_labels:
                        label.clear()
                        label.setText("画像なし")
                        label.setStyleSheet("border: 1px solid gray;")
                    
                    self.selected_grid = -1  # 選択状態をリセット
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
        
        # 画像表示を更新（サイズ変更に対応）
        if hasattr(self, 'images') and self.images and hasattr(self, 'display_mode'):
            # 少し遅延させて画像を再表示（連続的なリサイズに対する最適化）
            if hasattr(self, 'resize_timer'):
                self.resize_timer.stop()
            self.resize_timer = QTimer()
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self.show_image)
            self.resize_timer.start(100)  # 100ms後に画像を再表示
        
        # ウィンドウサイズ変更時にジオメトリを保存（タイマーで少し遅延）
        if hasattr(self, 'geometry_timer'):
            self.geometry_timer.stop()
        self.geometry_timer = QTimer()
        self.geometry_timer.setSingleShot(True)
        self.geometry_timer.timeout.connect(self.save_window_geometry)
        self.geometry_timer.start(500)  # 500ms後に保存
    
    def moveEvent(self, event):
        """ウィンドウ移動時の処理"""
        super().moveEvent(event)
        # ウィンドウ位置変更時にジオメトリを保存（タイマーで少し遅延）
        if hasattr(self, 'geometry_timer'):
            self.geometry_timer.stop()
        self.geometry_timer = QTimer()
        self.geometry_timer.setSingleShot(True)
        self.geometry_timer.timeout.connect(self.save_window_geometry)
        self.geometry_timer.start(500)  # 500ms後に保存
    
    def save_window_geometry(self):
        """ウィンドウのジオメトリ（サイズと位置）を設定に保存"""
        self.settings.setValue("window_geometry", self.saveGeometry())
    
    def closeEvent(self, event):
        """アプリケーション終了時にウィンドウサイズと位置を保存"""
        # 実行中のバックグラウンド処理がある場合は確認
        if self.tag_apply_worker and self.tag_apply_worker.isRunning():
            reply = QMessageBox.question(
                self, '処理中',
                "現在タグを適用中です。処理を中断して終了しますか？\n"
                "（「いいえ」を選ぶと、処理完了を待ちます）",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.tag_apply_worker.cancel()
                self.tag_apply_worker.wait(2000)  # 最大2秒待機
            else:
                # 完了まで待つ
                progress = QProgressDialog("残りの処理を完了させています...", None, 0, 0, self)
                progress.setWindowModality(Qt.WindowModal)
                progress.show()
                while self.tag_apply_worker.isRunning():
                    QApplication.processEvents()
                progress.close()

        # 最終的なウィンドウのジオメトリを保存
        self.save_window_geometry()
        # 親クラスのcloseEventを呼び出す
        super().closeEvent(event)

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
    
    def get_exif_data(self, image_path):
        """画像ファイルからEXIF情報とAI生成画像のメタデータを取得"""
        try:
            with Image.open(image_path) as img:
                # 標準的なEXIF情報を取得
                exif_data = img._getexif() if hasattr(img, '_getexif') and img._getexif() else {}
                
                # AI生成画像のメタデータも取得（PNG chunks, JPEG comments等）
                ai_metadata = {}
                
                # PIL.Image.infoから全ての情報を取得（PNG chunks等を含む）
                if hasattr(img, 'info') and img.info:
                    for key, value in img.info.items():
                        # Stable Diffusionでよく使われるキー
                        if key.lower() in ['parameters', 'prompt', 'negative_prompt', 'steps', 'sampler', 
                                         'cfg_scale', 'seed', 'model', 'software', 'comment', 'description',
                                         'workflow', 'comfyui', 'automatic1111']:
                            ai_metadata[f"AI_{key}"] = value
                        # その他の興味深い情報
                        elif isinstance(value, (str, int, float)) and len(str(value)) < 10000:
                            ai_metadata[f"Meta_{key}"] = value
                
                # EXIFのUserCommentを特別処理（AI生成画像のプロンプトが含まれることが多い）
                if exif_data and 37510 in exif_data:  # 37510 = UserComment
                    user_comment_raw = exif_data[37510]
                    if isinstance(user_comment_raw, bytes):
                        try:
                            decoded_comment = None
                            
                            # 複数のデコード方法を試行
                            decode_attempts = [
                                # 方法1: 標準的なEXIF UserComment形式（先頭8バイトがエンコーディング）
                                lambda data: data[8:].decode('ascii', errors='ignore') if data.startswith(b'ASCII\x00\x00\x00') else None,
                                # UNICODE形式を正しく処理（UTF-16BEでデコード）
                                lambda data: data[8:].decode('utf-16be', errors='ignore').rstrip('\x00') if data.startswith(b'UNICODE\x00') else None,
                                
                                # 方法2: UTF-16 (Little Endian / Big Endian)
                                lambda data: data.decode('utf-16le', errors='ignore'),
                                lambda data: data.decode('utf-16be', errors='ignore'),
                                
                                # 方法3: ヌル文字ごとに区切られたUTF-16パターン
                                lambda data: data.replace(b'\x00', b'').decode('utf-8', errors='ignore'),
                                
                                # 方法4: 先頭バイトをスキップしてUTF-16LE
                                lambda data: data[8:].decode('utf-16le', errors='ignore'),
                                lambda data: data[8:].decode('utf-16be', errors='ignore'),
                                
                                # 方法5: 直接UTF-8デコード
                                lambda data: data.decode('utf-8', errors='ignore'),
                                
                                # 方法6: UTF-16として読み込み、BOMをスキップ
                                lambda data: data.decode('utf-16', errors='ignore') if len(data) % 2 == 0 else None,
                                
                                # 方法7: バイト配列を2つずつ区切ってUTF-16LE処理
                                lambda data: ''.join(chr(b + (a << 8)) for a, b in zip(data[::2], data[1::2]) if chr(b + (a << 8)).isprintable()) if len(data) % 2 == 0 else None,
                                
                                # 方法8: バイト配列を2つずつ区切ってUTF-16BE処理  
                                lambda data: ''.join(chr(a + (b << 8)) for a, b in zip(data[::2], data[1::2]) if chr(a + (b << 8)).isprintable()) if len(data) % 2 == 0 else None,
                                
                                # 方法9: Latin-1でデコード
                                lambda data: data.decode('latin-1', errors='ignore'),
                                
                                # 方法10: 制御文字をスキップしてUTF-8
                                lambda data: data.lstrip(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08').decode('utf-8', errors='ignore'),
                            ]
                            
                            # 各方法を試行
                            for attempt in decode_attempts:
                                try:
                                    result = attempt(user_comment_raw)
                                    if result and len(result.strip()) > 10:
                                        # 制御文字や不可視文字を除去
                                        cleaned_result = ''.join(char for char in result if char.isprintable() or char in '\n\r\t')
                                        if len(cleaned_result.strip()) > 10:
                                            decoded_comment = cleaned_result.strip()
                                            break
                                except:
                                    continue
                            
                            # デコードできた場合は AI情報として追加
                            if decoded_comment:
                                # プロンプトの特徴をチェック（より緩い条件）
                                prompt_indicators = [
                                    'best quality', 'good quality', 'amazing quality', 'masterpiece', 
                                    'absurdres', 'very aesthetic', 'break', '1girl', 'solo',
                                    'negative prompt', 'hires prompt', 'steps:', 'sampler:', 'cfg scale:', 'seed:', 'model:'
                                ]
                                
                                # プロンプトらしい内容があるか、または十分に長いテキストの場合
                                is_likely_prompt = (
                                    any(indicator in decoded_comment.lower() for indicator in prompt_indicators) or
                                    len(decoded_comment) > 50  # 50文字以上の場合はプロンプトの可能性が高い
                                )
                                
                                if is_likely_prompt:
                                    ai_metadata["AI_Prompt_from_UserComment"] = decoded_comment
                                    # EXIFから元のバイナリデータを削除（重複を避ける）
                                    exif_data.pop(37510, None)
                                
                        except Exception as e:
                            pass  # エラーは静かに無視
                
                # 結合してリターン
                combined_data = {}
                combined_data.update(exif_data)
                combined_data.update(ai_metadata)
                
                return combined_data
                
        except Exception as e:
            print(f"メタデータ読み取りエラー: {e}")
            return {}
    
    # お気に入り関連メソッド
    def toggle_favorite_status(self, image_path=None):
        """お気に入り状態をトグル"""
        if not (TAG_SYSTEM_AVAILABLE and self.tag_manager):
            QMessageBox.warning(self, "エラー", "タグシステムが利用できません。")
            return
        
        # image_pathが無効な値（None、False、空文字列など）の場合は現在の画像を取得
        if not image_path or not isinstance(image_path, str):
            if not hasattr(self, 'images') or not self.images:
                QMessageBox.warning(self, "エラー", "表示する画像がありません。")
                return
            
            try:
                image_path = self.images[self.current_image_index]
            except (IndexError, TypeError) as e:
                QMessageBox.warning(self, "エラー", f"画像パスの取得に失敗しました: {e}")
                return
        
        # image_pathの型をチェック
        if not isinstance(image_path, str):
            QMessageBox.warning(self, "エラー", f"画像パスが無効です")
            return
            
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "エラー", f"画像ファイル {image_path} が見つかりません。")
            return
        
        try:
            # お気に入り状態をトグル
            result = self.tag_manager.toggle_favorite(image_path)
            if result:
                # 新しい状態を取得
                is_favorite = self.tag_manager.get_favorite_status(image_path)
                
                # UIを更新
                self.update_sidebar_metadata()
                
                # ハートボタンの状態も更新
                if hasattr(self, 'favorite_heart_button') and self.favorite_heart_button:
                    self.update_favorite_heart_button(is_favorite)
                
                # 画像を再描画してハートの表示を更新
                self.show_image()
                
                # 状態を表示
                status = "お気に入りに追加" if is_favorite else "お気に入りから削除"
                file_name = os.path.basename(image_path)
                self.show_message(f"✨ 「{file_name}」を{status}しました")
            else:
                QMessageBox.warning(self, "エラー", "お気に入り状態の更新に失敗しました。")
                
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"お気に入り更新エラー: {str(e)}")
    
    def show_favorite_images_dialog(self):
        """お気に入り画像タブを表示"""
        if not (TAG_SYSTEM_AVAILABLE and self.tag_manager):
            QMessageBox.warning(self, "エラー", "タグシステムが利用できません。")
            return
        
        if not self.favorites_tab:
            QMessageBox.warning(self, "エラー", "お気に入りタブが利用できません。")
            return
        
        try:
            # お気に入りタブに切り替え
            self.tabs.setCurrentWidget(self.favorites_tab)
            
            # お気に入りリストを更新
            self.favorites_tab.refresh_favorites()
            
            self.show_message("♡ お気に入りタブを表示しました")
                    
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"お気に入りタブ表示エラー: {str(e)}")
    
    def show_tag_edit_dialog(self):
        """現在の画像のタグ編集ダイアログを表示"""
        if not self.images:
            QMessageBox.warning(self, "エラー", "表示する画像がありません。")
            return
        
        if not (TAG_SYSTEM_AVAILABLE and self.tag_manager):
            QMessageBox.warning(self, "エラー", "タグシステムが利用できません。")
            return
        
        current_image_path = self.images[self.current_image_index]
        if not os.path.exists(current_image_path):
            QMessageBox.warning(self, "エラー", f"画像ファイル {current_image_path} が見つかりません。")
            return
        
        try:
            # タグ編集ダイアログを作成・表示
            tag_dialog = TagEditDialog(current_image_path, self.tag_manager, self)
            if tag_dialog.exec_() == QDialog.Accepted:
                # タグが更新された場合、サイドバーも更新
                self.update_sidebar_metadata()
                
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"タグ編集ダイアログの表示に失敗しました: {str(e)}")
    
    def show_auto_tag_dialog(self):
        """プロンプト解析による自動タグ付けダイアログを表示"""
        if not self.images:
            QMessageBox.warning(self, "エラー", "画像リストが空です。フォルダを選択してから実行してください。")
            return
        
        if not (TAG_SYSTEM_AVAILABLE and self.tag_manager):
            QMessageBox.warning(self, "エラー", "タグシステムが利用できません。")
            return
        
        try:
            # 現在の画像リストを自動タグ付けダイアログに渡す
            show_auto_tag_dialog(
                self.images,
                self.get_exif_data,  # メタデータ取得用メソッドを渡す
                self.tag_manager,
                self
            )
            # サイドバー更新は AutoTagDialog 内で実行される
            
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"自動タグ付けダイアログの表示に失敗しました: {str(e)}")

    def cancel_background_process(self):
        """バックグラウンド処理をキャンセル"""
        if self.tag_apply_worker:
            self.tag_apply_worker.cancel()
            self.background_progress_label.setText("キャンセル中...")
            self.bg_cancel_button.setEnabled(False)

    def start_background_tag_application(self, items, is_replace_mode, analysis_results):
        """バックグラウンドでタグ適用を開始"""
        if self.tag_apply_worker and self.tag_apply_worker.isRunning():
            QMessageBox.warning(self, "実行中", "既にタグ適用処理が実行中です。")
            return

        from tag_ui import TagApplyWorker
        
        self.tag_apply_worker = TagApplyWorker(items, self.tag_manager, is_replace_mode, analysis_results)
        
        # UI更新の接続
        self.tag_apply_worker.progress_updated.connect(self.update_background_progress)
        self.tag_apply_worker.completion_finished.connect(self.on_background_apply_completed)
        self.tag_apply_worker.error_occurred.connect(self.on_background_apply_error)
        
        # キャンセルボタンの接続（テキストをリセット）
        try:
            self.bg_cancel_button.clicked.disconnect()
        except:
            pass
        self.bg_cancel_button.clicked.connect(self.cancel_background_process)
        self.bg_cancel_button.setEnabled(True)
        self.bg_cancel_button.setText("キャンセル")
        
        # 表示開始
        self.background_progress_bar.setMaximum(len(items))
        self.background_progress_bar.setValue(0)
        self.background_progress_label.setText(f"タグ適用開始... (0/{len(items)})")
        self.background_progress_widget.show()
        
        self.tag_apply_worker.start()

    def update_background_progress(self, current, message):
        """バックグラウンド処理の進捗を更新"""
        self.background_progress_bar.setValue(current)
        self.background_progress_label.setText(message)

    def on_background_apply_completed(self, applied_count, total_tags, elapsed_time, failed_count):
        """バックグラウンド適用完了時の処理"""
        # ウィンドウを前面に持ってくる（別の仮想デスクトップにいても通知が行くようにする）
        self.activateWindow()
        self.raise_()
        QApplication.alert(self) # Dockのアイコンを跳ねさせて通知
        
        if failed_count == 0:
            # 成功時: 進捗エリアを成功色に変更して目立たせる
            self.background_progress_widget.setStyleSheet("""
                QWidget {
                    background-color: #2d5016;
                    border-top: 2px solid #4CAF50;
                }
                QLabel {
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: bold;
                }
            """)
            message = f"✅ {applied_count}枚に{total_tags}個のタグを適用完了 ({elapsed_time:.2f}秒)"
            self.background_progress_label.setText(message)
            self.background_progress_bar.setValue(self.background_progress_bar.maximum())
            self.bg_cancel_button.setText("閉じる")
            self.bg_cancel_button.setEnabled(True)
            
            # ボタン接続を更新
            try:
                self.bg_cancel_button.clicked.disconnect()
            except:
                pass
            
            def close_and_reset():
                self.background_progress_widget.hide()
                # スタイルをリセット
                self.background_progress_widget.setStyleSheet("""
                    QWidget {
                        background-color: #333333;
                        border-top: 1px solid #555555;
                    }
                    QLabel {
                        color: #ffffff;
                        font-size: 12px;
                    }
                """)
            
            self.bg_cancel_button.clicked.connect(close_and_reset)
            
            # 20秒後に自動非表示（以前より長く）
            QTimer.singleShot(20000, lambda: close_and_reset() if self.background_progress_widget.isVisible() and self.bg_cancel_button.text() == "閉じる" else None)
        else:
            # 失敗時: ダイアログを表示
            self.background_progress_widget.hide()
            message = (f"⚠️ タグ適用が完了しました。\n\n"
                      f"✅ 成功: {applied_count}枚（{total_tags}個のタグ）\n"
                      f"❌ 失敗: {failed_count}枚\n"
                      f"⏱️ 処理時間: {elapsed_time:.2f}秒\n\n"
                      f"一部の画像でタグの書き込みに失敗しました。")
            QMessageBox.warning(self, "適用完了（一部失敗）", message)
        
        # サイドバー更新
        self.update_sidebar_metadata()

    def on_background_apply_error(self, error_message, applied_count, failed_count):
        """バックグラウンド適用エラー時の処理"""
        # ウィンドウを前面に持ってくる
        self.activateWindow()
        self.raise_()
        QApplication.alert(self)
        
        # エラー時は進捗エリアを赤色に変更
        self.background_progress_widget.setStyleSheet("""
            QWidget {
                background-color: #5d1616;
                border-top: 2px solid #f44336;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        
        error_summary = f"❌ エラー発生 - 成功: {applied_count}枚, 失敗: {failed_count}枚"
        self.background_progress_label.setText(error_summary)
        self.bg_cancel_button.setText("閉じる")
        self.bg_cancel_button.setEnabled(True)
        
        # ボタン接続を更新
        try:
            self.bg_cancel_button.clicked.disconnect()
        except:
            pass
        
        def close_and_reset():
            self.background_progress_widget.hide()
            # スタイルをリセット
            self.background_progress_widget.setStyleSheet("""
                QWidget {
                    background-color: #333333;
                    border-top: 1px solid #555555;
                }
                QLabel {
                    color: #ffffff;
                    font-size: 12px;
                }
            """)
        
        self.bg_cancel_button.clicked.connect(close_and_reset)
        
        # 詳細なエラーメッセージをダイアログで表示
        message = (f"タグ適用中にエラーが発生しました:\n{error_message}\n\n"
                  f"途中経過:\n"
                  f"✅ 成功: {applied_count}枚\n"
                  f"❌ 失敗: {failed_count}枚")
        QMessageBox.critical(self, "エラー", message)
        
        # サイドバー更新（部分的にでも成功していた場合）
        if applied_count > 0:
            self.update_sidebar_metadata()
    
    def show_exclude_settings_dialog(self):
        """自動タグ除外設定ダイアログを表示"""
        if not (TAG_SYSTEM_AVAILABLE and self.tag_manager):
            QMessageBox.warning(self, "エラー", "タグシステムが利用できません。")
            return
        
        try:
            # AutoTagAnalyzerを初期化
            from auto_tag_analyzer import AutoTagAnalyzer
            analyzer = AutoTagAnalyzer()
            
            # 除外設定ダイアログを表示
            show_exclude_settings_dialog(analyzer, self)
            
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"除外設定ダイアログの表示に失敗しました: {str(e)}")
    
    def show_mapping_rules_dialog(self):
        """自動タグルール設定ダイアログを表示"""
        if not (TAG_SYSTEM_AVAILABLE and self.tag_manager):
            QMessageBox.warning(self, "エラー", "タグシステムが利用できません。")
            return
        
        try:
            # AutoTagAnalyzerを初期化
            from auto_tag_analyzer import AutoTagAnalyzer
            analyzer = AutoTagAnalyzer()
            
            # ルール設定ダイアログを表示
            show_mapping_rules_dialog(analyzer, self)
            
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"ルール設定ダイアログの表示に失敗しました: {str(e)}")
    
    def export_images_to_zip(self):
        """現在のリストの画像をZIPファイルに圧縮してダウンロード"""
        if not hasattr(self, 'images') or not self.images:
            QMessageBox.warning(self, "エラー", "圧縮する画像がありません。\nフォルダを開くか、タグでフィルタしてください。")
            return
        
        # ZIPファイルの保存先を選択
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # リストの種類に応じてファイル名を設定
        if hasattr(self, 'list_mode') and self.list_mode == "filter":
            # フィルタリング結果の場合
            if hasattr(self, 'filter_description'):
                default_name = f"filtered_images_{self.filter_description}_{timestamp}.zip"
            else:
                default_name = f"filtered_images_{timestamp}.zip"
        else:
            # フォルダモードの場合
            if hasattr(self, 'current_folder') and self.current_folder:
                folder_name = os.path.basename(self.current_folder)
                default_name = f"images_from_{folder_name}_{timestamp}.zip"
            else:
                default_name = f"images_{timestamp}.zip"
        
        # ファイル名から無効な文字を除去
        import re
        default_name = re.sub(r'[<>:"/\\|?*]', '_', default_name)
        
        # 保存ダイアログを表示
        zip_file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "ZIPファイルの保存先を選択", 
            default_name,
            "ZIP files (*.zip)"
        )
        
        if not zip_file_path:
            return  # キャンセルされた
        
        # プログレスダイアログの設定
        progress_dialog = QProgressDialog("画像をZIPに圧縮中...", "キャンセル", 0, len(self.images), self)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)  # すぐに表示
        progress_dialog.show()
        
        try:
            # ZIPファイルを作成
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                successful_count = 0
                skipped_count = 0
                permission_errors = []
                other_errors = []
                
                for i, image_path in enumerate(self.images):
                    # キャンセルボタンが押された場合
                    if progress_dialog.wasCanceled():
                        # 作成途中のZIPファイルを削除
                        try:
                            os.remove(zip_file_path)
                        except:
                            pass
                        return
                    
                    # プログレス更新
                    progress_dialog.setValue(i)
                    progress_dialog.setLabelText(f"圧縮中... ({i+1}/{len(self.images)})")
                    QApplication.processEvents()  # UIを更新
                    
                    # ファイルの存在確認
                    if not os.path.exists(image_path):
                        skipped_count += 1
                        other_errors.append(f"• {os.path.basename(image_path)}: ファイルが存在しません")
                        continue
                    
                    # 読み取り権限の確認
                    if not os.access(image_path, os.R_OK):
                        skipped_count += 1
                        permission_errors.append(f"• {os.path.basename(image_path)}: 読み取り権限がありません")
                        continue
                    
                    try:
                        # ファイル名の重複を避けるために番号を付ける
                        base_name = os.path.basename(image_path)
                        name, ext = os.path.splitext(base_name)
                        
                        # 同名ファイルがある場合は番号を追加
                        counter = 1
                        archive_name = base_name
                        while archive_name in [info.filename for info in zipf.infolist()]:
                            archive_name = f"{name}_{counter:03d}{ext}"
                            counter += 1
                        
                        # ZIPに追加
                        zipf.write(image_path, archive_name)
                        successful_count += 1
                        
                    except PermissionError as e:
                        print(f"Permission denied for {image_path}: {str(e)}")
                        skipped_count += 1
                        permission_errors.append(f"• {os.path.basename(image_path)}: アクセス権限エラー")
                        continue
                    except Exception as e:
                        print(f"Failed to add {image_path}: {str(e)}")
                        skipped_count += 1
                        other_errors.append(f"• {os.path.basename(image_path)}: {str(e)}")
                        continue
                
                # プログレス完了
                progress_dialog.setValue(len(self.images))
            
            # 結果をメッセージで表示
            total_files = len(self.images)
            message = f"📦 ZIP圧縮が完了しました！\n\n"
            message += f"💾 保存先: {zip_file_path}\n"
            message += f"✅ 成功: {successful_count} ファイル\n"
            if skipped_count > 0:
                message += f"⚠️ スキップ: {skipped_count} ファイル\n"
            message += f"📊 合計: {total_files} ファイル"
            
            # 権限エラーがある場合は詳細を表示
            if permission_errors:
                message += f"\n\n🔒 権限エラー ({len(permission_errors)}件):\n"
                # 最初の5件のみ表示
                for error in permission_errors[:5]:
                    message += f"{error}\n"
                if len(permission_errors) > 5:
                    message += f"...他{len(permission_errors) - 5}件\n"
            
            # その他のエラーがある場合は詳細を表示
            if other_errors:
                message += f"\n\n⚠️ その他のエラー ({len(other_errors)}件):\n"
                # 最初の5件のみ表示
                for error in other_errors[:5]:
                    message += f"{error}\n"
                if len(other_errors) > 5:
                    message += f"...他{len(other_errors) - 5}件\n"
            
            # メッセージタイプを決定
            if successful_count == 0:
                QMessageBox.critical(self, "エラー", message)
            elif skipped_count > 0:
                QMessageBox.warning(self, "圧縮完了（一部エラー）", message)
            else:
                QMessageBox.information(self, "圧縮完了", message)
            
        except PermissionError as e:
            # 権限エラーが発生した場合
            error_msg = f"ZIPファイルの作成に失敗しました。\n\n"
            error_msg += f"🔒 権限エラー: {str(e)}\n\n"
            error_msg += f"以下を確認してください:\n"
            error_msg += f"• 保存先フォルダへの書き込み権限があるか\n"
            error_msg += f"• macOSの場合、システム環境設定でアプリに\n"
            error_msg += f"  適切なアクセス権限が付与されているか"
            QMessageBox.critical(self, "権限エラー", error_msg)
            
            # 作成途中のZIPファイルを削除
            try:
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
            except:
                pass
        except Exception as e:
            # その他のエラーが発生した場合
            QMessageBox.critical(self, "エラー", f"ZIP圧縮中にエラーが発生しました:\n{str(e)}")
            
            # 作成途中のZIPファイルを削除
            try:
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
            except:
                pass
        
        finally:
            progress_dialog.close()
    
    def update_zip_menu_state(self):
        """ZIP圧縮メニューの有効/無効を更新"""
        if hasattr(self, 'zip_images_action'):
            has_images = hasattr(self, 'images') and bool(self.images)
            self.zip_images_action.setEnabled(has_images)