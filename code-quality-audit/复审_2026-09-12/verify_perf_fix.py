# -*- coding: utf-8 -*-
"""性能优化修复验证（第7区块）：
1) get_all_visible_windows TTL 缓存：0.8s 内重复调用只枚举一次
2) 返回深拷贝：调用方修改结果不污染缓存
3) TTL 过期后重新枚举；use_cache=False 绕过
4) floor_manager 复用 class_name，不再重复 GetClassName
"""
import os
import sys
import time

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

import desktop_interaction as di_mod
from desktop_interaction import DesktopInteraction


class FakeParent:
    pass


def _new_di():
    parent = FakeParent()
    di = DesktopInteraction.__new__(DesktopInteraction)
    di.parent = parent
    di.privacy_apps = ['微信', 'QQ']
    di.user_opened_privacy_apps = set()
    di.update_timer = None
    return di


def test_cache_hit_avoids_repeat_enum():
    di = _new_di()
    calls = {"n": 0}

    real_enum = di_mod.win32gui.EnumWindows

    def counting_enum(callback, param):
        calls["n"] += 1
        return real_enum(callback, param)

    di_mod.win32gui.EnumWindows = counting_enum
    try:
        di.get_all_visible_windows()
        di.get_all_visible_windows()
        di.get_all_visible_windows()
    finally:
        di_mod.win32gui.EnumWindows = real_enum
    assert calls["n"] == 1, f"0.8s 内三次调用应只枚举一次，实际 {calls['n']} 次"
    print(f"[PASS] 缓存命中：3 次调用仅 1 次全量枚举（省 {calls['n']*2} 次）")


def test_deepcopy_isolation():
    di = _new_di()
    first = di.get_all_visible_windows()
    if not first:
        print("[SKIP] 当前环境无可见窗口，跳过深拷贝验证")
        return
    # 修改返回结果
    first[0]["title"] = "HACKED"
    first.append({"hwnd": 999999, "title": "FAKE"})
    second = di.get_all_visible_windows()
    assert second[0]["title"] != "HACKED", "缓存被调用方污染"
    assert len(second) == len(first) - 1 or all(w.get("hwnd") != 999999 for w in second), "缓存被追加污染"
    print("[PASS] 返回深拷贝，调用方修改不污染缓存")


def test_ttl_expiry_and_bypass():
    di = _new_di()
    calls = {"n": 0}
    real_enum = di_mod.win32gui.EnumWindows

    def counting_enum(callback, param):
        calls["n"] += 1
        return real_enum(callback, param)

    di_mod.win32gui.EnumWindows = counting_enum
    try:
        di.get_all_visible_windows()
        # 强制让缓存过期（把缓存时间戳往前拨）
        if getattr(di, '_visible_windows_cache', None):
            di._visible_windows_cache = (di._visible_windows_cache[0] - 2.0, di._visible_windows_cache[1])
        di.get_all_visible_windows()
        # use_cache=False 必然重新枚举
        di.get_all_visible_windows(use_cache=False)
    finally:
        di_mod.win32gui.EnumWindows = real_enum
    assert calls["n"] == 3, f"过期1次 + 绕过1次 + 首次 = 3 次，实际 {calls['n']}"
    print("[PASS] TTL 过期与 use_cache=False 均正确重新枚举")


def test_window_info_has_class_name():
    di = _new_di()
    windows = di.get_all_visible_windows()
    for w in windows:
        assert "class_name" in w, f"window_info 缺 class_name: {w.get('title')}"
    print(f"[PASS] window_info 已含 class_name（floor_manager 可直接复用）")


if __name__ == "__main__":
    test_cache_hit_avoids_repeat_enum()
    test_deepcopy_isolation()
    test_ttl_expiry_and_bypass()
    test_window_info_has_class_name()
    print("\n全部通过 ✔")
