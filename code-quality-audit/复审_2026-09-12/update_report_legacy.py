# -*- coding: utf-8 -*-
"""报告遗留清单补充：z-order 双方案并存 + 性能后续选项"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\代码质量复审报告_2026-09-12_第三轮.md"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

old = """6. **多份 `test_*.py` 散落根目录与 `ralsei_pet/`**：多为开发期遗留探测脚本，建议后续归档到 `tests/`。"""
new = """6. **多份 `test_*.py` 散落根目录与 `ralsei_pet/`**：多为开发期遗留探测脚本，建议后续归档到 `tests/`。
7. **窗口层级（Z-order）双方案并存**：实际生效的是 Qt 的 `WindowStaysOnTopHint`（main.py 2644/2651 行，在窗口/桌面间切换时重建窗口）；`floor_manager` 的 Win32 方案（`find_desktop_workerw_hwnd`/`set_window_behind`/`get_insert_after_hwnd`）在主程序**无任何调用点**，属未接入的冗余实现。当前行为正常（Ralsei 在窗口上可见），未来若要做"贴靠 WorkerW 层级"精细控制需二选一，避免两套逻辑互相打架。
8. **性能后续选项（若用户在多窗口桌面仍感卡顿）**：当前 TTL 缓存已把主线程枚举频率降至每 2 秒一次；若仍不满足，下一步可把窗口枚举移入后台守护线程（`get_all_visible_windows` 改为读线程缓存），主线程彻底零阻塞。属可选项，改动面更大，本次未做。"""
assert old in src, "anchor not found"
src = src.replace(old, new, 1)

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("report legacy list updated")
