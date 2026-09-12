# -*- coding: utf-8 -*-
"""性能优化（第7区块）：主线程全量窗口枚举导致鼠标渲染掉帧
1) get_all_visible_windows 加 TTL 缓存（0.8s，深拷贝返回防污染）——floor 1s 检查
   与 nearby 3s 检查不再各自全量枚举，主线程周期性阻塞消除
2) window_info 补存 class_name，floor_manager 不再重复 GetClassName（省一次跨进程调用×窗口数）
3) check_nearby_desktop_elements 节拍 3s→5s（附近感知不需要那么频繁）
"""
import sys

D = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\desktop_interaction.py"
F = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\floor_manager.py"
M = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"


def patch(path, old, new):
    with open(path, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    src = raw.decode("utf-8").replace("\r\n", "\n")
    assert old in src, f"NOT FOUND in {path}:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE in {path}:\n{old[:200]}"
    src = src.replace(old, new, 1)
    out = src.replace("\n", "\r\n") if crlf else src
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print(f"patched: {path}")


# ---- 1) desktop_interaction: get_all_visible_windows 签名 + 缓存入口 + 存 class_name + 缓存出口 ----
patch(D,
"""    def get_all_visible_windows(self):
        # 获取所有可见窗口的信息，根据"建楼"要求实现楼层系统
        visible_windows = []""",
"""    def get_all_visible_windows(self, use_cache=True, cache_ttl=0.8):
        # 获取所有可见窗口的信息，根据"建楼"要求实现楼层系统
        # 修复（性能）：本方法做全量 EnumWindows 枚举，每个窗口多次跨进程 Win32 调用，
        # 单次耗时可达几十毫秒。而主线程每 1 秒（floor 追踪）+ 每 3 秒（nearby 感知）
        # 各调用一次 → GUI 线程周期性阻塞，表现为"鼠标移动渲染跟不上"。
        # 增加 TTL 缓存（默认 0.8s）：同一窗口状态快照被多次调用共享；返回深拷贝，
        # 调用方修改结果不会污染缓存。需要强实时数据时可传 use_cache=False。
        import copy
        if use_cache:
            _cache = getattr(self, '_visible_windows_cache', None)
            if _cache is not None and time.time() - _cache[0] < cache_ttl:
                return copy.deepcopy(_cache[1])
        visible_windows = []""")

patch(D,
"""            window_info = {
                'hwnd': hwnd,
                'title': title,
                'x': rect[0],
                'y': rect[1],
                'width': width,
                'height': height,
                'center_x': (rect[0] + rect[2]) / 2,
                'center_y': (rect[1] + rect[3]) / 2,
                'is_privacy': is_privacy_app,
                'is_visible': True,
                'rect': rect
            }
            visible_windows.append(window_info)
            return True""",
"""            window_info = {
                'hwnd': hwnd,
                'title': title,
                'class_name': class_name,  # 修复：补存已取得的类名，调用方不再重复 GetClassName
                'x': rect[0],
                'y': rect[1],
                'width': width,
                'height': height,
                'center_x': (rect[0] + rect[2]) / 2,
                'center_y': (rect[1] + rect[3]) / 2,
                'is_privacy': is_privacy_app,
                'is_visible': True,
                'rect': rect
            }
            visible_windows.append(window_info)
            return True""")

patch(D,
"""        # 按Z序排序，Z序越小，窗口越靠前（越上层）
        visible_windows.sort(key=lambda x: x['z_order'])
        
        return visible_windows""",
"""        # 按Z序排序，Z序越小，窗口越靠前（越上层）
        visible_windows.sort(key=lambda x: x['z_order'])
        
        if use_cache:
            self._visible_windows_cache = (time.time(), visible_windows)
        return visible_windows""")


# ---- 2) floor_manager: 复用 class_name，去掉重复 GetClassName ----
patch(F,
"""            class_name = ''
            try:
                class_name = win32gui.GetClassName(w['hwnd'])
            except Exception as e:
                _log.debug("floor_manager 防御性异常（已忽略）: %s", e)
            visible_windows.append({""",
"""            # 修复（性能）：get_all_visible_windows 已在枚举时取得并缓存 class_name，
            # 这里再 GetClassName 是对每个窗口的重复跨进程调用（量级翻倍），直接复用。
            class_name = w.get('class_name', '')
            visible_windows.append({""")


# ---- 3) main.py: check_nearby_desktop_elements 节拍 3s→5s ----
patch(M,
"""        # 低频检查附近的桌面元素（每3秒一次；修复：此前 check_nearby_desktop_elements
        # 从未被调用，Ralsei 对桌面文件夹/文件的"靠近反应"从未触发）
        # 修复：时间戳更新放在 try 外——原来在 try 内，若 check_* 抛错则时间戳不更新，
        # 每 30ms 全量重试（性能热循环）。
        try:
            if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 3.0:
                self.check_nearby_desktop_elements()""",
"""        # 低频检查附近的桌面元素（每5秒一次；修复：此前 check_nearby_desktop_elements
        # 从未被调用，Ralsei 对桌面文件夹/文件的"靠近反应"从未触发）
        # 修复：时间戳更新放在 try 外——原来在 try 内，若 check_* 抛错则时间戳不更新，
        # 每 30ms 全量重试（性能热循环）。
        # 性能：get_nearby_elements 内部会全量枚举窗口（现已有缓存），5s 节拍足够，
        # 避免主线程频繁被窗口枚举拖慢。
        try:
            if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
                self.check_nearby_desktop_elements()""")

print("ALL PATCHED OK")
