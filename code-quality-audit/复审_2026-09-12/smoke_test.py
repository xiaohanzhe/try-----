# -*- coding: utf-8 -*-
"""集成冒烟测试：构造 RalseiPet 主窗口（offscreen），验证全部模块初始化链路，
随后立即停止所有定时器并退出（不污染任何真实数据文件）。"""
import os
import sys
import shutil

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "src"))
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 数据文件快照保护（测试前后对比，确保不被改动）
DATA_FILES = ["ralsei_pet/memory.json", "ralsei_pet/growth_data.json",
              "ralsei_pet/entertainment_data.json", "ralsei_pet/customization_config.json",
              "ralsei_pet/config.json"]
snapshots = {}
for df in DATA_FILES:
    p = os.path.join(ROOT, df)
    if os.path.exists(p):
        with open(p, "rb") as f:
            snapshots[df] = f.read()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)

from main import RalseiPet

try:
    window = RalseiPet()
    window.show()
    print("[SMOKE] RalseiPet 构造成功")
    print(f"[SMOKE] 等级={window.social_growth.get_level()} 经验={window.social_growth.get_experience()}")

    # 核心模块属性齐全性检查
    for attr in ("energy_hunger", "emotion_system", "memory_system", "social_growth",
                 "sprite_loader", "dialogue_ui", "dialogue_system", "pet_ai",
                 "desktop_interaction", "weather_system", "entertainment_system",
                 "customization_system", "autonomous_agent", "api_client",
                 "ai_driver", "sound_manager", "command_manager", "search_summarizer"):
        assert hasattr(window, attr), f"缺少模块属性 {attr}"
    print("[SMOKE] 18 个核心模块属性齐全")

    # 动画系统可用
    anims = window.sprite_loader.get_all_animations()
    print(f"[SMOKE] 可用动画 {len(anims)} 个: {sorted(anims)[:8]} ...")

    # 停掉所有定时器，避免后台链路写数据
    for timer_attr in dir(window):
        try:
            t = getattr(window, timer_attr)
            if isinstance(t, QTimer):
                t.stop()
        except Exception:
            pass
    print("[SMOKE] 定时器已全部停止")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("[SMOKE] 初始化失败")
    sys.exit(1)
finally:
    # 立即退出事件循环（不等待任何定时器触发）
    try:
        window.close()
    except Exception:
        pass
    app.processEvents()

# 数据文件一致性检查
dirty = []
for df, data in snapshots.items():
    p = os.path.join(ROOT, df)
    if os.path.exists(p):
        with open(p, "rb") as f:
            if f.read() != data:
                dirty.append(df)
if dirty:
    print(f"[SMOKE] 警告：以下数据文件被冒烟测试改动: {dirty}")
    sys.exit(1)
print("[SMOKE] 数据文件零改动 ✔")
print("\n冒烟测试全部通过 ✔")
