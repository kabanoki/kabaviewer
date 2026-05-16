"""アプリ全体の見た目・挙動を調整する設定ダイアログ。

- UI フォントサイズ
- テーマ (ダーク / ライト)
- アクセントカラー

QApplication 起動後にメニュー「ファイル → ⚙️ 環境設定…」から開く想定。
変更は即座に QApplication.styleSheet と setFont に反映される。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QSpinBox,
    QPushButton, QDialogButtonBox, QGroupBox, QRadioButton, QButtonGroup,
    QComboBox, QApplication, QFrame, QCheckBox,
)

from theme import (
    apply_theme, apply_font_size,
    load_theme_name, save_theme_name,
    load_accent_id, save_accent_id,
    load_font_pt, save_font_pt,
    load_write_exif, save_write_exif,
    FONT_PT_RANGE, ACCENT_PRESETS,
)


_ACCENT_LABELS = {
    "blue":   "ブルー",
    "cyan":   "シアン",
    "purple": "パープル",
    "teal":   "ティールグリーン",
}


class SettingsDialog(QDialog):
    """環境設定ダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("環境設定")
        self.setModal(True)
        self.resize(460, 360)

        self._original_font_pt = load_font_pt()
        self._original_theme = load_theme_name()
        self._original_accent = load_accent_id()
        self._original_write_exif = load_write_exif()

        self._build_ui()
        self._load_current_values()

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        # ── フォントサイズ ─────────────────────────────────────
        font_group = QGroupBox("文字サイズ")
        font_layout = QVBoxLayout(font_group)
        font_row = QHBoxLayout()
        self.font_slider = QSlider(Qt.Horizontal)
        lo, hi = FONT_PT_RANGE
        self.font_slider.setRange(lo, hi)
        self.font_slider.setSingleStep(1)
        self.font_slider.setTickInterval(2)
        self.font_slider.setTickPosition(QSlider.TicksBelow)
        self.font_spin = QSpinBox()
        self.font_spin.setRange(lo, hi)
        self.font_spin.setSuffix(" pt")
        font_row.addWidget(self.font_slider, 1)
        font_row.addWidget(self.font_spin)
        font_layout.addLayout(font_row)
        self.font_preview = QLabel("プレビュー: KabaViewer サンプル文字 ABC あいう 123")
        self.font_preview.setObjectName("DescLabel")
        font_layout.addWidget(self.font_preview)
        root.addWidget(font_group)

        # スライダーとスピンを連動 + プレビューに即反映
        self.font_slider.valueChanged.connect(self._on_font_slider)
        self.font_spin.valueChanged.connect(self._on_font_spin)

        # ── テーマ ───────────────────────────────────────────
        theme_group = QGroupBox("テーマ")
        theme_layout = QHBoxLayout(theme_group)
        self.theme_group = QButtonGroup(self)
        self.theme_dark = QRadioButton("🌙 ダーク")
        self.theme_light = QRadioButton("☀️ ライト")
        self.theme_group.addButton(self.theme_dark)
        self.theme_group.addButton(self.theme_light)
        theme_layout.addWidget(self.theme_dark)
        theme_layout.addWidget(self.theme_light)
        theme_layout.addStretch()
        root.addWidget(theme_group)

        # ── アクセントカラー ────────────────────────────────
        accent_group = QGroupBox("アクセントカラー")
        accent_layout = QHBoxLayout(accent_group)
        self.accent_combo = QComboBox()
        for aid in ACCENT_PRESETS.keys():
            self.accent_combo.addItem(_ACCENT_LABELS.get(aid, aid), aid)
        accent_layout.addWidget(self.accent_combo)
        accent_layout.addStretch()
        root.addWidget(accent_group)

        # ── タグ書き込み挙動 ────────────────────────────────
        tag_group = QGroupBox("タグ保存先")
        tag_layout = QVBoxLayout(tag_group)
        self.write_exif_check = QCheckBox("画像ファイルにも EXIF タグを書き込む")
        self.write_exif_check.setToolTip(
            "OFF にすると DB と内部設定にのみタグを保存し、画像本体は変更しません。\n"
            "大量画像の一括タグ付けが劇的に高速になります。\n"
            "ON のままだとポータビリティ（他ツールからもタグが見える）は保たれます。"
        )
        tag_layout.addWidget(self.write_exif_check)
        hint = QLabel("OFF にすると一括タグ付けが高速になりますが、画像本体にタグは残りません。")
        hint.setObjectName("MutedHint")
        hint.setWordWrap(True)
        tag_layout.addWidget(hint)
        root.addWidget(tag_group)

        # 即時プレビュー: 変更を即 QApplication に反映
        self.theme_dark.toggled.connect(self._on_theme_changed)
        self.theme_light.toggled.connect(self._on_theme_changed)
        self.accent_combo.currentIndexChanged.connect(self._on_accent_changed)

        # ── ボタン ───────────────────────────────────────────
        root.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset
        )
        buttons.button(QDialogButtonBox.Ok).setText("適用して閉じる")
        buttons.button(QDialogButtonBox.Cancel).setText("キャンセル")
        buttons.button(QDialogButtonBox.Reset).setText("デフォルトに戻す")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self._reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self._reset_defaults)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    # 現在値ロード
    # ------------------------------------------------------------------

    def _load_current_values(self):
        # フォント
        self.font_slider.blockSignals(True)
        self.font_spin.blockSignals(True)
        self.font_slider.setValue(self._original_font_pt)
        self.font_spin.setValue(self._original_font_pt)
        self.font_slider.blockSignals(False)
        self.font_spin.blockSignals(False)
        self._update_font_preview(self._original_font_pt)

        # テーマ
        if self._original_theme == "dark":
            self.theme_dark.setChecked(True)
        else:
            self.theme_light.setChecked(True)

        # アクセント
        idx = self.accent_combo.findData(self._original_accent)
        if idx >= 0:
            self.accent_combo.setCurrentIndex(idx)

        # EXIF 書き込み
        self.write_exif_check.setChecked(self._original_write_exif)

    def _update_font_preview(self, pt):
        font = self.font_preview.font()
        font.setPointSize(pt)
        self.font_preview.setFont(font)

    # ------------------------------------------------------------------
    # シグナルハンドラ
    # ------------------------------------------------------------------

    def _on_font_slider(self, value):
        self.font_spin.blockSignals(True)
        self.font_spin.setValue(value)
        self.font_spin.blockSignals(False)
        self._update_font_preview(value)
        self._apply_font_live(value)

    def _on_font_spin(self, value):
        self.font_slider.blockSignals(True)
        self.font_slider.setValue(value)
        self.font_slider.blockSignals(False)
        self._update_font_preview(value)
        self._apply_font_live(value)

    def _apply_font_live(self, pt):
        app = QApplication.instance()
        if app is not None:
            apply_font_size(app, pt)

    def _on_theme_changed(self, _checked):
        name = "dark" if self.theme_dark.isChecked() else "light"
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, name=name, accent_id=self.accent_combo.currentData() or load_accent_id())

    def _on_accent_changed(self, _idx):
        app = QApplication.instance()
        if app is not None:
            apply_theme(
                app,
                name="dark" if self.theme_dark.isChecked() else "light",
                accent_id=self.accent_combo.currentData(),
            )

    # ------------------------------------------------------------------
    # OK / Cancel / Reset
    # ------------------------------------------------------------------

    def _accept(self):
        # 永続化
        save_font_pt(self.font_spin.value())
        save_theme_name("dark" if self.theme_dark.isChecked() else "light")
        save_accent_id(self.accent_combo.currentData() or "blue")
        save_write_exif(self.write_exif_check.isChecked())
        self.accept()

    def _reject(self):
        # 入る前の状態に戻して閉じる
        app = QApplication.instance()
        if app is not None:
            apply_font_size(app, self._original_font_pt)
            apply_theme(app, name=self._original_theme, accent_id=self._original_accent)
        self.reject()

    def _reset_defaults(self):
        """既定値（フォント 13pt / ダーク / ブルー / EXIF 書き込み ON）にセット。"""
        self.font_spin.setValue(13)
        self.theme_dark.setChecked(True)
        idx = self.accent_combo.findData("blue")
        if idx >= 0:
            self.accent_combo.setCurrentIndex(idx)
        self.write_exif_check.setChecked(True)
