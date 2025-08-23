# back
import sys
from PyQt5.QtWidgets import QApplication
from image_viewer import ImageViewer  # 変更点

def main():
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()