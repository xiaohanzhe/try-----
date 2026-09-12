# -*- coding: utf-8 -*-
"""desktop_interaction.py 修复（第3区块）：
1) ctypes restype/argtypes（64位句柄截断） 2) EnumWindows 回调防御 3) PPT重复Close 4) 隐私文件类型表收窄"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\desktop_interaction.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

def patch(old, new):
    global src
    assert old in src, f"NOT FOUND:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE:\n{old[:200]}"
    src = src.replace(old, new, 1)

# ---- 1) ctypes 声明 ----
patch(
"""kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32""",
"""kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

# 修复：64 位系统上句柄/指针是 64 位值，ctypes 默认按 c_int(32位) 返回，
# OpenProcess/VirtualAllocEx 的返回值会被截断成错误句柄（实测 h_process=0），
# 桌面图标真实位置探测整条链路失效。显式声明 restype/argtypes 保证完整传递。
kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.VirtualAllocEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = ctypes.c_int
kernel32.VirtualFreeEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
kernel32.VirtualFreeEx.restype = ctypes.c_int
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
user32.SendMessageW.restype = ctypes.c_ssize_t""")

# ---- 2) 隐私文件类型表收窄：原表覆盖 .txt/.md/.py/.docx/.pdf 等几乎所有常见类型，
#      导致 get_file_content_preview 永远返回"这是隐私文件"，"看文件内容"功能形同虚设。
#      收窄为真正敏感的类型（密钥/密码库/环境变量等），文档与代码恢复可预览。 ----
patch(
"""        # 隐私文件类型列表
        self.privacy_file_types = [
            '.txt', '.md', '.py', '.js',
            '.docx', '.pdf', '.xlsx', '.pptx',
            '.jpg', '.png', '.gif'
        ]""",
"""        # 隐私文件类型列表
        # 修复：原表把 .txt/.md/.py/.docx/.pdf/.xlsx/.pptx/.jpg/.png/.gif 全列为隐私，
        # 而这些正是桌面上最常见的文档/代码/图片 → is_privacy_app 对几乎所有文件
        # 返回 True，get_file_content_preview 永远返回"这是隐私文件"（autonomous_agent
        # 的"看文件"能力实际从未生效）。收窄为真正敏感的类型（密钥/密码库/环境变量）。
        self.privacy_file_types = [
            '.key', '.pem', '.pfx', '.p12',   # 密钥/证书
            '.kdbx',                           # 密码库
            '.env',                            # 环境变量（常含密钥）
        ]""")

# ---- 3) EnumWindows 回调防御：窗口中途销毁时 GetWindowRect/GetWindowLong 抛异常
#        会中断整轮枚举（楼层表静默变短），改为单窗口失败即跳过。 ----
patch(
"""            # 获取窗口矩形
            rect = win32gui.GetWindowRect(hwnd)
            
            # 计算窗口大小（避免重复计算）
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            # 快速过滤：非常小的窗口（可能是系统组件）
            if width <= 100 or height <= 100:
                return True
            
            # 快速过滤：屏幕外的窗口
            if (rect[0] > screen_width or rect[1] > screen_height or 
                rect[2] < 0 or rect[3] < 0):
                return True
            
            # 只检测非透明窗口（优化：减少不必要的系统调用）
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)""",
"""            # 获取窗口矩形（修复：窗口可能在此刻被销毁，GetWindowRect 抛异常会
            # 中断整轮 EnumWindows，导致楼层表静默变短；单窗口失败直接跳过）
            try:
                rect = win32gui.GetWindowRect(hwnd)
            except Exception:
                return True
            
            # 计算窗口大小（避免重复计算）
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            # 快速过滤：非常小的窗口（可能是系统组件）
            if width <= 100 or height <= 100:
                return True
            
            # 快速过滤：屏幕外的窗口
            if (rect[0] > screen_width or rect[1] > screen_height or 
                rect[2] < 0 or rect[3] < 0):
                return True
            
            # 只检测非透明窗口（优化：减少不必要的系统调用）
            try:
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            except Exception:
                return True""")

# ---- 4) mark_app_as_opened 的 enum_callback 同样加防御 ----
patch(
"""            def enum_callback(hwnd, param):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    class_name = win32gui.GetClassName(hwnd)
                    if app_name.lower() in title.lower() or app_name.lower() in class_name.lower():
                        hwnds.append(hwnd)
                return True""",
"""            def enum_callback(hwnd, param):
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        class_name = win32gui.GetClassName(hwnd)
                        if app_name.lower() in title.lower() or app_name.lower() in class_name.lower():
                            hwnds.append(hwnd)
                except Exception:
                    pass
                return True""")

# ---- 5) ppt_control 重复 Close：_execute_ppt_action 已 Close 并返回，
#        这里再 Close 一次会对已关闭的 COM 对象抛异常 → 操作成功却返回 False。 ----
patch(
"""            # 保存并关闭（如果需要）
            if action in ["save", "save_as"]:
                presentation.Save()
            if action == "close":
                presentation.Close()
                # 本方法自己打开的实例才退出，避免关掉用户原有的 PowerPoint
                if self_opened:
                    powerpoint.Quit()""",
"""            # 保存（如果需要）
            if action in ["save", "save_as"]:
                presentation.Save()
            if action == "close":
                # 修复：演示文稿已由 _execute_ppt_action 的 close 分支关闭，
                # 这里若再 Close 一次会对已释放的 COM 对象抛异常，导致
                # "操作成功却返回失败"。这里只负责退出自己启动的实例。
                if self_opened:
                    powerpoint.Quit()""")

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("desktop_interaction.py patched OK")
