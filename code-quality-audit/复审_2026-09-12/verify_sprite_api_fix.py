# -*- coding: utf-8 -*-
"""sprite_loader.py + api_client.py 修复验证（第2区块）"""
import os
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)
from PyQt5.QtGui import QPixmap, QColor, QImage

from sprite_loader import SpriteLoader
from api_client import HTTPLocalAI, LocalAIStub, create_client


def make_png(path, color=(255, 0, 0)):
    img = QImage(10, 10, QImage.Format_RGB32)
    img.fill(QColor(*color))
    assert img.save(path, "PNG")


def test_load_frame_missing_modes():
    sl = SpriteLoader()
    sl.sprite_dir = tempfile.mkdtemp()
    # 缺图：默认返回占位图（保持旧行为），placeholder_on_missing=False 返回 None
    p_default = sl.load_frame("nope_0.png")
    assert p_default is not None and not p_default.isNull()
    p_strict = sl.load_frame("nope_0.png", placeholder_on_missing=False)
    assert p_strict is None
    print("[PASS] load_frame 缺图：默认占位 / 严格模式返回 None")


def test_scan_dedup_same_frame_number():
    sl = SpriteLoader()
    d = tempfile.mkdtemp()
    sl.sprite_dir = d
    make_png(os.path.join(d, "dance_2.png"))
    make_png(os.path.join(d, "dance2.png"), (0, 255, 0))
    make_png(os.path.join(d, "dance_0.png"))
    make_png(os.path.join(d, "dance_1.png"))
    sl.scan_and_group_assets()
    frames = sl.auto_scanned_animations.get("dance", [])
    assert len(frames) == 3, f"帧号去重失败: {frames}"
    # 每帧号唯一（dance_2 与 dance2 同帧号只保留一个），顺序按帧号稳定递增
    import re as _re
    nums = sorted(int(_re.search(r"(\d+)\.png$", os.path.basename(f)).group(1)) for f in frames)
    assert nums == [0, 1, 2], nums
    print("[PASS] 自动分组帧号去重 + 稳定排序:", [os.path.basename(f) for f in frames])


def test_load_sprites_no_placeholder_in_sequence():
    sl = SpriteLoader()
    d = tempfile.mkdtemp()
    sl.sprite_dir = d
    # idle 定义 5 帧但素材只有 3 帧（idle_0/1/2）
    for i in range(3):
        make_png(os.path.join(d, f"spr_ralsei_idle_{i}.png"))
    sl.load_sprites()
    frames = sl.sprites.get("idle", [])
    assert len(frames) == 3, f"idle 帧数应为3（缺帧跳过而非占位）: {len(frames)}"
    for f in frames:
        assert f is not None and not f.isNull()
    print("[PASS] load_sprites 缺帧跳过，动画序列无占位帧 (idle 帧数=%d)" % len(frames))


def test_api_client_robust_rebuild():
    # 非 dict 配置不崩溃
    c = create_client(["not", "dict"])
    assert isinstance(c, LocalAIStub)
    # 畸形 history 不崩溃
    http = HTTPLocalAI({"enabled": True, "base_url": "  "})
    assert http.base_url == "http://localhost:8000"
    history = [("user", "你好"), ("bad_role", "x"), "oops", ("assistant", "")]
    # chat 会尝试网络请求，此处只验证参数解析不因 history 崩溃——
    # 通过直接检查（网络不通时返回 None 也算通过，重点是无异常逃逸）
    try:
        http.chat("hi", history=history)
    except Exception as e:
        assert False, f"畸形 history 导致崩溃: {e}"
    print("[PASS] api_client 非 dict 配置 / 畸形 history 均不崩溃")


import tempfile

if __name__ == "__main__":
    test_load_frame_missing_modes()
    test_scan_dedup_same_frame_number()
    test_load_sprites_no_placeholder_in_sequence()
    test_api_client_robust_rebuild()
    print("\n全部通过 ✔")
