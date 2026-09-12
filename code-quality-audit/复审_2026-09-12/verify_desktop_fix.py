# -*- coding: utf-8 -*-
"""desktop_interaction.py 修复验证（第3区块）"""
import os
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

import ctypes
from desktop_interaction import DesktopInteraction, kernel32, user32


class FakeParent:
    def __init__(self):
        from PyQt5.QtCore import QObject
        self._o = QObject()

    # QTimer(parent) 需要真实 QObject
    def _get_qobject(self):
        return self._o


def test_ctypes_declarations():
    # 关键句柄/指针函数必须显式声明 64 位 restype
    assert kernel32.OpenProcess.restype == ctypes.c_void_p, kernel32.OpenProcess.restype
    assert kernel32.VirtualAllocEx.restype == ctypes.c_void_p, kernel32.VirtualAllocEx.restype
    assert kernel32.OpenProcess.argtypes is not None
    print("[PASS] ctypes 64位句柄声明就位")


def _new_di():
    from PyQt5.QtCore import QObject
    parent = QObject()
    di = DesktopInteraction(parent)
    # 停掉定时器，避免测试进程被 Qt 事件循环挂住
    di.update_timer.stop()
    return di


def test_privacy_file_types_narrowed():
    di = _new_di()
    types = di.privacy_file_types
    assert '.txt' not in types and '.py' not in types and '.docx' not in types, types
    assert '.key' in types and '.env' in types, types
    # 行为：普通文档不再被判为隐私文件
    assert di.is_privacy_app("C:/tmp/notes.txt") is False
    # 隐私应用窗口标题判定保持不变
    assert di.is_privacy_app("微信 - 聊天") is True
    # 真实存在的密钥文件仍受保护
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".key", delete=False) as kf:
        kpath = kf.name
    try:
        assert di.is_privacy_app(kpath) is True
    finally:
        os.unlink(kpath)
    print("[PASS] 隐私文件类型收窄，普通文档可预览、密钥仍受保护")


def test_get_file_content_preview_works():
    import tempfile
    di = _new_di()
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write("hello ralsei\nline2\nline3\n")
        path = f.name
    try:
        preview = di.get_file_content_preview(path, max_lines=2)
        assert "hello ralsei" in preview, preview
        assert "隐私文件" not in preview
        print("[PASS] get_file_content_preview 对 .txt 正常返回内容")
    finally:
        os.unlink(path)


if __name__ == "__main__":
    test_ctypes_declarations()
    test_privacy_file_types_narrowed()
    test_get_file_content_preview_works()
    print("\n全部通过 ✔")
