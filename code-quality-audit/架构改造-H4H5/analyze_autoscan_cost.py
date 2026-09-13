# -*- coding: utf-8 -*-
"""H5 S1 附带发现：自动扫描带来的"加载膨胀"量化

load_sprites 会把 scan_and_group_assets 的结果并入 sprites（以"文件名前缀"为键），
于是同一批 PNG 会被加载两份：一份挂在 mapping 的**语义名**下（main.py 实际请求的名字），
一份挂在**文件名前缀**下（几乎无人请求）。本脚本量化这份冗余——只读，
用于评估 H5 S3 的收益面，不属于 S1 的改动范围。

运行：QT_QPA_PLATFORM=offscreen python analyze_autoscan_cost.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication  # noqa: E402
_app = QApplication.instance() or QApplication([])

from sprite_loader import SpriteLoader  # noqa: E402

loader = SpriteLoader()
loader.load_sprites(debug=False)

sprites = loader.sprites
mapping = loader.animation_mapping
auto = loader.auto_scanned_animations

mapping_keys = set(mapping)
auto_only_keys = set(auto) - mapping_keys
extra_keys = set(sprites) - mapping_keys - auto_only_keys

mapping_files = {f for files in mapping.values() for f in files}
auto_files = {f for files in auto.values() for f in files}
# 口径：只出现在自动扫描组、mapping 一个都没引用的帧文件
auto_files_only = auto_files - mapping_files

mapping_frames = sum(len(sprites.get(k, [])) for k in mapping_keys)
auto_only_frames = sum(len(sprites.get(k, [])) for k in auto_only_keys)

disk = {f for f in os.listdir(loader.sprite_dir) if f.lower().endswith('.png')}

# 自动扫描组里，文件全部已被 mapping 覆盖的组 = 100% 纯重复加载
pure_dup_groups = [
    k for k in auto_only_keys
    if auto.get(k) and all(f in mapping_files for f in auto[k])
]

L = []
L.append('=== 运行时 sprites 规模 ===')
L.append('动画组总数（sprites）       : %d' % len(sprites))
L.append('  ├ mapping 的语义名        : %d 组 / %d 帧对象' % (len(mapping_keys), mapping_frames))
L.append('  ├ 仅自动扫描（文件名前缀）  : %d 组 / %d 帧对象' % (len(auto_only_keys), auto_only_frames))
L.append('  └ 其他                    : %d 组' % len(extra_keys))
L.append('')
L.append('=== 帧文件引用 ===')
L.append('磁盘 PNG                    : %d' % len(disk))
L.append('自动扫描建组数              : %d 组' % len(auto))
L.append('mapping 引用（去重）        : %d' % len(mapping_files))
L.append('自动扫描引用（去重）        : %d' % len(auto_files))
L.append('  两者交集                  : %d' % len(mapping_files & auto_files))
L.append('  仅自动扫描引用（mapping 未引用）: %d' % len(auto_files_only))
L.append('  未被任何组引用的磁盘文件    : %d' % len(disk - mapping_files - auto_files))
L.append('')
L.append('=== 冗余 ===')
L.append('自动扫描多建了 %d 个"文件名前缀"组（mapping 里没有对应语义名），' % len(auto_only_keys))
L.append('其中 %d 个组的帧文件**全部**已被 mapping 覆盖 → 100%% 重复加载。' % len(pure_dup_groups))
L.append('例：%s' % ', '.join(sorted(pure_dup_groups)[:12]))
L.append('')
L.append('结论：main.py 真正请求的只有 mapping 的 %d 个语义名（外加 9 种 f-string 拼接），' % len(mapping_keys))
L.append('另外 %d 组本次运行中从未被任何代码按名字请求——纯启动加载开销 + 内存占用。' % len(auto_only_keys))

txt = '\n'.join(L)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_evidence', 'autoscan_cost.txt')
open(out, 'w', encoding='utf-8').write(txt)
print(txt)
