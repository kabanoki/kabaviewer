# back
import sys
from PyQt5.QtWidgets import QApplication
from image_viewer import ImageViewer  # 変更点
from version import __app_name__, __version__
from theme import apply_theme, apply_font_size

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setApplicationVersion(__version__)
    # 基本フォントサイズを QSettings から復元（環境設定で変更可）
    apply_font_size(app)
    # UI テーマを QSettings から復元して適用（既定はダーク + ブルー）
    apply_theme(app)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
