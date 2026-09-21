import sys
print("测试PyQt5导入")
print("Python版本:", sys.version)

try:
    import PyQt5
    print("✓ 成功导入PyQt5")
    print("PyQt5版本:", PyQt5.__version__)
    
    from PyQt5 import QtCore
    print("✓ 成功导入QtCore")
    
    from PyQt5 import QtGui
    print("✓ 成功导入QtGui")
    
    from PyQt5 import QtWidgets
    print("✓ 成功导入QtWidgets")
    
    app = QtWidgets.QApplication(sys.argv)
    print("✓ 成功创建QApplication")
    
    print("\n🎉 所有测试通过！PyQt5基本功能正常。")
    app.quit()
    sys.exit(0)
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)