"""UI テーマシステム

ダーク / ライトの 2 テーマを QApplication 全体に適用する。
個別ウィジェットで setStyleSheet している箇所は selector の特異性で
このグローバルスタイルを上書きできるが、可能な限りこのファイルの
トークンに揃えることでアプリ全体のトーンを統一できる。
"""

from PyQt5.QtCore import QSettings


# ---- デザイントークン（コード側からも参照できるよう公開）----

class DarkTokens:
    bg = "#1e1e22"            # アプリ全体の背景
    surface = "#2a2a2e"       # サイドバー・カード・入力欄
    surface_elevated = "#33333a"  # ダイアログ・ボタン
    surface_hover = "#3d3d44"
    border = "#3d3d44"
    border_subtle = "#33333a"
    text = "#e8e8ea"
    text_muted = "#9c9ca5"
    text_disabled = "#5a5a64"
    accent = "#4ea1ff"        # プライマリ操作・選択
    accent_hover = "#6ab4ff"
    accent_pressed = "#3a8ce0"
    heart = "#ff5277"         # お気に入り
    danger = "#ff6b6b"        # 削除
    danger_hover = "#ff8484"


class LightTokens:
    bg = "#ffffff"
    surface = "#f6f6f8"
    surface_elevated = "#ffffff"
    surface_hover = "#eceef2"
    border = "#d8d8de"
    border_subtle = "#e8e8ec"
    text = "#1c1c20"
    text_muted = "#6a6a72"
    text_disabled = "#b0b0b8"
    accent = "#1f6feb"
    accent_hover = "#3b85ff"
    accent_pressed = "#175bc7"
    heart = "#e6395b"
    danger = "#d64545"
    danger_hover = "#ee5b5b"


def _build_qss(t):
    """共通テンプレートから QSS を生成する。"""
    return f"""
/* === Base ============================================================== */
QMainWindow, QDialog, QWidget {{
    background-color: {t.bg};
    color: {t.text};
}}

QLabel {{
    color: {t.text};
    background: transparent;
}}

QToolTip {{
    background-color: {t.surface_elevated};
    color: {t.text};
    border: 1px solid {t.border};
    padding: 4px 8px;
}}

/* === Buttons =========================================================== */
QPushButton {{
    background-color: {t.surface_elevated};
    color: {t.text};
    border: 1px solid {t.border};
    padding: 6px 12px;
    border-radius: 4px;
}}
QPushButton:hover {{
    background-color: {t.surface_hover};
    border-color: {t.accent};
}}
QPushButton:pressed {{
    background-color: {t.surface};
}}
QPushButton:disabled {{
    color: {t.text_disabled};
    background-color: {t.surface};
    border-color: {t.border_subtle};
}}
QPushButton:checked {{
    background-color: {t.accent};
    color: white;
    border-color: {t.accent};
}}

/* === Inputs ============================================================ */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {t.accent};
    selection-color: white;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {t.accent};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    color: {t.text_disabled};
}}

QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    selection-background-color: {t.accent};
    selection-color: white;
}}

/* === CheckBox / RadioButton =========================================== */
QCheckBox, QRadioButton {{
    color: {t.text};
    spacing: 6px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}

/* === Tabs ============================================================== */
QTabWidget::pane {{
    border: 1px solid {t.border};
    background-color: {t.bg};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {t.surface};
    color: {t.text_muted};
    padding: 8px 16px;
    border: 1px solid {t.border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {t.bg};
    color: {t.text};
    border-bottom: 2px solid {t.accent};
}}
QTabBar::tab:hover:!selected {{
    background-color: {t.surface_hover};
    color: {t.text};
}}

/* === List / Tree ======================================================= */
QListWidget, QTreeWidget, QListView, QTreeView, QTableView {{
    background-color: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: 4px;
    alternate-background-color: {t.surface_elevated};
    outline: none;
}}
QListWidget::item, QTreeWidget::item {{
    padding: 4px;
}}
QListWidget::item:selected, QTreeWidget::item:selected,
QListView::item:selected, QTreeView::item:selected, QTableView::item:selected {{
    background-color: {t.accent};
    color: white;
}}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected,
QListView::item:hover:!selected, QTreeView::item:hover:!selected {{
    background-color: {t.surface_hover};
}}

QHeaderView::section {{
    background-color: {t.surface_elevated};
    color: {t.text};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {t.border};
    border-bottom: 1px solid {t.border};
}}

/* === Menu ============================================================== */
QMenuBar {{
    background-color: {t.bg};
    color: {t.text};
    border-bottom: 1px solid {t.border};
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 10px;
}}
QMenuBar::item:selected {{
    background-color: {t.surface_hover};
}}
QMenu {{
    background-color: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 24px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {t.accent};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {t.border_subtle};
    margin: 4px 8px;
}}

/* === Scrollbars ======================================================== */
QScrollBar:vertical {{
    background-color: {t.surface};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {t.surface_hover};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {t.text_disabled};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0;
    border: none;
}}

QScrollBar:horizontal {{
    background-color: {t.surface};
    height: 12px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: {t.surface_hover};
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {t.text_disabled};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
    width: 0;
    border: none;
}}

/* === GroupBox ========================================================== */
QGroupBox {{
    border: 1px solid {t.border};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    color: {t.text};
}}
QGroupBox::title {{
    color: {t.text_muted};
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}

/* === Progress ========================================================== */
QProgressBar {{
    background-color: {t.surface};
    border: 1px solid {t.border};
    border-radius: 4px;
    text-align: center;
    color: {t.text};
    min-height: 16px;
}}
QProgressBar::chunk {{
    background-color: {t.accent};
    border-radius: 3px;
}}

/* === Splitter ========================================================== */
QSplitter::handle {{
    background-color: {t.border_subtle};
}}
QSplitter::handle:hover {{
    background-color: {t.accent};
}}

/* === Status / Misc ===================================================== */
QStatusBar {{
    background-color: {t.surface};
    color: {t.text_muted};
    border-top: 1px solid {t.border};
}}

/* === Sidebar (object name based) ====================================== */
QWidget#Sidebar {{
    background-color: {t.surface};
    border-left: 1px solid {t.border};
}}
QWidget#SidebarContent, QWidget#SidebarContent > QWidget {{
    background-color: transparent;
}}
QLabel#SidebarTitle {{
    color: {t.text};
    font-size: 15px;
    font-weight: 600;
    padding: 8px 0;
    border-bottom: 1px solid {t.border};
}}
QLabel#SidebarPlaceholder {{
    color: {t.text_muted};
    font-style: italic;
    padding: 20px;
}}
QPushButton#PrimaryButton {{
    background-color: {t.accent};
    color: white;
    border: 1px solid {t.accent};
}}
QPushButton#PrimaryButton:hover {{
    background-color: {t.accent_hover};
    border-color: {t.accent_hover};
}}
QPushButton#PrimaryButton:pressed {{
    background-color: {t.accent_pressed};
    border-color: {t.accent_pressed};
}}
QPushButton#DangerButton {{
    background-color: {t.danger};
    color: white;
    border: 1px solid {t.danger};
}}
QPushButton#DangerButton:hover {{
    background-color: {t.danger_hover};
    border-color: {t.danger_hover};
}}
QPushButton#SuccessButton {{
    background-color: #43a047;
    color: white;
    border: 1px solid #43a047;
}}
QPushButton#SuccessButton:hover {{
    background-color: #4caf50;
    border-color: #4caf50;
}}
QPushButton#SuccessButton:pressed {{
    background-color: #388e3c;
}}
QPushButton#IconButton {{
    padding: 4px 8px;
    font-size: 14px;
}}
QPushButton#ChipButton {{
    background-color: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
}}
QPushButton#ChipButton:hover {{
    background-color: {t.surface_hover};
    border-color: {t.accent};
}}
QLabel#DialogHeading {{
    background-color: {t.surface_elevated};
    color: {t.text};
    border: 1px solid {t.border_subtle};
}}
QLabel#DescLabel {{
    color: {t.text_muted};
}}
QLabel#InfoBanner {{
    color: {t.accent};
    background-color: rgba(78, 161, 255, 0.10);
    border: 1px solid rgba(78, 161, 255, 0.35);
    padding: 8px 12px;
    border-radius: 4px;
    font-weight: 600;
    margin: 5px 0;
}}

/* ハートボタン（お気に入り） — dynamic property [favorited="true"] で着色変更 */
QPushButton#HeartButton {{
    background-color: {t.surface_elevated};
    color: {t.text_muted};
    border: 1px solid {t.border};
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 18px;
}}
QPushButton#HeartButton:hover {{
    background-color: {t.surface_hover};
    border-color: {t.heart};
    color: {t.heart};
}}
QPushButton#HeartButton[favorited="true"] {{
    color: {t.heart};
    border-color: {t.heart};
    font-weight: bold;
}}

/* × クリアボタン（検索/除外をクリア） */
QPushButton#ClearButton {{
    background-color: transparent;
    color: {t.text_muted};
    border: 1px solid transparent;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 14px;
    min-width: 24px;
    max-width: 32px;
}}
QPushButton#ClearButton:hover {{
    background-color: {t.danger};
    color: white;
    border-color: {t.danger};
}}
QPushButton#ClearButton:pressed {{
    background-color: {t.danger_hover};
}}

/* メタデータカード用フレーム */
QFrame#MetaCard {{
    background-color: {t.surface_elevated};
    border: 1px solid {t.border_subtle};
    border-radius: 6px;
}}
QLabel#MetaCardTitle {{
    color: {t.text_muted};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* メッセージラベル（一時表示） */
QLabel#TransientMessage {{
    background-color: {t.surface_elevated};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}}
"""


DARK_QSS = _build_qss(DarkTokens)
LIGHT_QSS = _build_qss(LightTokens)

_THEME_KEY = "ui_theme"
_DEFAULT = "dark"


def load_theme_name():
    """QSettings から保存済みのテーマ名を取得する。デフォルトはダーク。"""
    s = QSettings("MyCompany", "ImageViewerApp")
    val = s.value(_THEME_KEY, _DEFAULT)
    return val if val in ("dark", "light") else _DEFAULT


def save_theme_name(name):
    if name not in ("dark", "light"):
        return
    s = QSettings("MyCompany", "ImageViewerApp")
    s.setValue(_THEME_KEY, name)


def tokens_for(name):
    return DarkTokens if name == "dark" else LightTokens


def apply_theme(app, name=None):
    """QApplication にテーマを適用する。

    name=None で QSettings の値を利用。
    """
    if name is None:
        name = load_theme_name()
    if name not in ("dark", "light"):
        name = _DEFAULT
    app.setStyleSheet(DARK_QSS if name == "dark" else LIGHT_QSS)
    return name
