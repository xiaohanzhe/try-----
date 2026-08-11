import sys
import traceback
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt

print(f"Python version: {sys.version}")
print(f"PyQt5 imported successfully")

try:
    app = QApplication(sys.argv)
    print("QApplication created successfully")
    
    window = QWidget()
    window.setWindowTitle('PyQt5 Test')
    window.setGeometry(100, 100, 300, 200)
    window.setWindowFlags(Qt.WindowStaysOnTopHint)
    print("Window created successfully")
    
    window.show()
    print("Window shown")
    
    print("Entering event loop...")
    result = app.exec_()
    print(f"Event loop exited with result: {result}")
    
    sys.exit(result)
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()