"""诊断脚本：启动 Ralsei 并截屏 + 打印关键状态。"""
import sys, os, time, json
sys.path.insert(0, r'c:\Users\23002\Desktop\项目文件夹\try - 副本')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)

# --- 1. 先检查 sprite_loader 的动画有效性 ---
from ralsei_pet.modules.sprite_loader import SpriteLoader
sl = SpriteLoader()
sl.load_sprites()

print("=" * 60)
print("【1】animation_mapping 有效性检查")
print("=" * 60)

missing_in_sprites = []
present_in_sprites = []
for key, files in sl.animation_mapping.items():
    if key in sl.sprites and len(sl.sprites[key]) > 0:
        present_in_sprites.append(key)
    else:
        missing_in_sprites.append(key)

print(f"animation_mapping 总数: {len(sl.animation_mapping)}")
print(f"有效（sprites 中有帧）: {len(present_in_sprites)}")
print(f"无效（sprites 中无帧）: {len(missing_in_sprites)}")
if missing_in_sprites:
    print(f"缺失列表: {missing_in_sprites[:20]}")

# --- 2. 检查带 suffix 的组合名是否存在 ---
print("\n" + "=" * 60)
print("【2】update_animation 拼接名有效性检查")
print("=" * 60)

# 模拟 update_animation 里的逻辑
directions = ['down', 'up', 'left', 'right']
bases = ['walk', 'run']
suffixes = ['', '_blush', '_unhappy', '_sleep', '_butler', '_tea', '_cotton_candy']

all_combo_missing = []
all_combo_present = []
for base in bases:
    for d in directions:
        for suf in suffixes:
            name = f'{base}_{d}{suf}'
            if name in sl.sprites and len(sl.sprites[name]) > 0:
                all_combo_present.append(name)
            else:
                # 只记录非空 suffix 的缺失（空 suffix 一定会有）
                if suf:
                    all_combo_missing.append(name)

print(f"基础组合（walk/run × 4方向）存在数: {len(all_combo_present)}")
print(f"带情绪后缀的缺失（正常，说明没有对应素材）: {len(all_combo_missing)}")
if all_combo_missing:
    print(f"缺失后缀: {all_combo_missing[:15]}")

# --- 3. 启动 Ralsei ---
print("\n" + "=" * 60)
print("【3】启动 Ralsei ...")
print("=" * 60)

from ralsei_pet.src.main import RalseiPet
pet = RalseiPet()
pet.show()

# 等 5 秒让它跑起来
def snapshot_state():
    print("\n" + "=" * 60)
    print("【4】运行时状态快照")
    print("=" * 60)
    print(f"窗口位置: {pet.pos()}")
    print(f"窗口尺寸: {pet.width()}x{pet.height()}")
    print(f"current_animation: {pet.current_animation}")
    print(f"current_direction: {pet.current_direction}")
    print(f"previous_direction: {pet.previous_direction}")
    print(f"current_frame: {pet.current_frame}")
    print(f"is_moving: {pet.is_moving}")
    print(f"is_falling: {pet.is_falling}")
    print(f"is_following_mouse: {pet.is_following_mouse}")
    print(f"speed: {pet.speed}, min/max: {pet.min_speed}/{pet.max_speed}")
    print(f"current_speed_x/y: {pet.current_speed_x:.2f}/{pet.current_speed_y:.2f}")
    print(f"target_pos: {pet.target_pos}")
    print(f"_container_w/h: {pet._container_w}/{pet._container_h}")
    print(f"对话显示中: {pet.dialogue_ui.isVisible() if hasattr(pet, 'dialogue_ui') else 'N/A'}")

    # 当前帧的像素尺寸
    frames = sl.sprites.get(pet.current_animation, [])
    if frames and pet.current_frame < len(frames):
        f = frames[pet.current_frame]
        print(f"当前帧像素: {f.width()}x{f.height()}")
    else:
        print(f"⚠️ 当前动画 '{pet.current_animation}' 无帧可用！")

    # 截屏
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        out_path = r'c:\Users\23002\Desktop\项目文件夹\try - 副本\screenshot.png'
        img.save(out_path)
        print(f"\n📸 屏幕截图已保存: {out_path}  (尺寸: {img.size})")
    except Exception as e:
        print(f"截屏失败: {e}")

    # 打印 floor 信息
    print(f"\ncurrent_floor: {pet.current_floor}")

    # 退出
    print("\n诊断完成，退出。")
    QTimer.singleShot(500, app.quit)

QTimer.singleShot(5000, snapshot_state)
app.exec_()
