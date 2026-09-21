"""截屏诊断 - 每秒截一次桌面，同时尝试读取 ralsei 窗口位置"""
import sys, os, time, ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import win32gui
import win32process
from PIL import ImageGrab

out_dir = os.path.join(os.path.dirname(__file__), "diag_frames")
os.makedirs(out_dir, exist_ok=True)

def enum_cb(hwnd, results):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if "ralsei" in title.lower() or "Ralsei" in title:
            results.append((hwnd, title, win32gui.GetWindowRect(hwnd)))

print("开始诊断，持续 15 秒...")
for i in range(15):
    results = []
    win32gui.EnumWindows(enum_cb, results)
    print(f"\n--- 第 {i} 秒 ---")
    for hwnd, title, rect in results:
        print(f"  HWND={hwnd} Title='{title}' Rect={rect}")
    
    try:
        img = ImageGrab.grab(all_screens=True)
        img_path = os.path.join(out_dir, f"frame_{i:02d}.png")
        img.save(img_path)
        print(f"  截屏保存: {img_path} size={img.size}")
    except Exception as e:
        print(f"  截屏失败: {e}")
    
    time.sleep(1)

print("\n诊断完成，截屏在:", out_dir)
