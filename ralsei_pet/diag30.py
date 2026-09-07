"""30秒稳定性诊断 - 每2秒截屏 + 记录位置"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import win32gui
from PIL import ImageGrab

out_dir = os.path.join(os.path.dirname(__file__), "diag_frames2")
os.makedirs(out_dir, exist_ok=True)
log_path = os.path.join(out_dir, "log.txt")

def enum_cb(hwnd, results):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if "ralsei" in title.lower() or "Ralsei" in title:
            results.append((hwnd, title, win32gui.GetWindowRect(hwnd)))

print("开始 30 秒稳定性诊断...")
with open(log_path, "w") as f:
    f.write(f"{'t':>4} | {'Rect':>40} | {'变化':>12}\n")
    prev_rect = None
    for i in range(15):
        results = []
        win32gui.EnumWindows(enum_cb, results)
        line = f"{i*2:>4}s | "
        change = ""
        for hwnd, title, rect in results:
            line += str(rect)
            if prev_rect and rect != prev_rect:
                change = f"dx={rect[0]-prev_rect[0]} dy={rect[1]-prev_rect[1]}"
        f.write(line + f" | {change or '-'}\n")
        prev_rect = results[0][2] if results else None
        
        try:
            img = ImageGrab.grab(all_screens=True)
            img_path = os.path.join(out_dir, f"frame_{i:02d}.png")
            img.save(img_path)
        except Exception as e:
            f.write(f"  截屏失败: {e}\n")
        
        print(f"  {i*2}s: {results} {change}")
        time.sleep(2)

print(f"\n诊断完成！日志: {log_path}")
print(f"截屏目录: {out_dir}")
