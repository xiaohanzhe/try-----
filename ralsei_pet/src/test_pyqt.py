import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel

app = QApplication(sys.argv)
window = QWidget()
window.setGeometry(100, 100, 300, 200)
window.setWindowTitle("PyQt5 Test")

label = QLabel("Hello PyQt5!", window)
label.setGeometry(50, 50, 200, 100)

window.show()
sys.exit(app.exec_())