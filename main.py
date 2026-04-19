# back
import sys
from PyQt5.QtWidgets import QApplication
from image_viewer import ImageViewer  # 変更点
from version import __app_name__, __version__

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setApplicationVersion(__version__)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
