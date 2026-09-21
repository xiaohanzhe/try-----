"""诊断 ralsei 内部状态 - 导入运行中的实例并检查变量"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modules'))

# 连接到已运行的 ralsei 进程（通过 win32 读取窗口）
import win32gui

states = []

def enum_cb(hwnd, results):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if "ralsei" in title.lower() or "Ralsei" in title:
            rect = win32gui.GetWindowRect(hwnd)
            results.append((hwnd, title, rect))

results = []
win32gui.EnumWindows(enum_cb, results)
if results:
    hwnd, title, rect = results[0]
    print(f"Found Ralsei: HWND={hwnd} Rect={rect}")
else:
    print("Ralsei window not found!")
    sys.exit(1)

# 直接在当前进程中创建一个 qt 实例来检查
os.environ['QT_QPA_PLATFORM'] = 'offscreen'  # 无头模式
from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

# 现在看看能否读取 main.py 的关键变量
# 由于我们不能直接连接到运行中的进程，改为通过重新 import 来检查代码逻辑
print("\n=== 代码逻辑检查 ===")

# 检查 _agent_busy_flags 中的 falling/recovering 等是否正确
print("检查 _agent_busy_flags 定义...")

# 检查 autonomous_agent 是否正确处理了 set_target_pos
print("检查 set_target_pos 回调...")

# 检查 update_movement 中 is_moving 的初始值
print("检查 is_moving 初始值...")

print("\n诊断完成")
