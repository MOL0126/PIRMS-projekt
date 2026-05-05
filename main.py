import sys
from PyQt6.QtWidgets import QApplication

# TADY IMPORTUJEME NAŠE OKNO ZE SOUBORU gui.py
from gui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())