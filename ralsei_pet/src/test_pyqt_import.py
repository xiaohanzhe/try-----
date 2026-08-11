import sys

print("测试PyQt5导入")
print("Python版本:", sys.version)

# 尝试导入PyQt5模块
try:
    import PyQt5
    print("✓ 成功导入PyQt5")
    print("PyQt5版本:", PyQt5.__version__)
except ImportError as e:
    print("✗ 导入PyQt5失败:", e)
    sys.exit(1)

# 尝试导入QtCore
try:
    from PyQt5 import QtCore
    print("✓ 成功导入QtCore")
except ImportError as e:
    print("✗ 导入QtCore失败:", e)
    sys.exit(1)

# 尝试导入QtGui
try:
    from PyQt5 import QtGui
    print("✓ 成功导入QtGui")
except ImportError as e:
    print("✗ 导入QtGui失败:", e)
    sys.exit(1)

# 尝试导入QtWidgets
try:
    from PyQt5 import QtWidgets
    print("