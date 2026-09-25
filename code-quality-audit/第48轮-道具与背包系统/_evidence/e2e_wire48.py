# -*- coding: utf-8 -*-
"""第48轮 · 真 App **离屏**端到端接线验证（入库版；原脚本在 `E:\\Download\\_tmp`，按约定已蒸馏进仓库）。

验证的是**接线**（#60），不是纯函数 —— 本项目最贵的坑是"函数写对了但产品用不上"：
  ① App 起得来，道具系统就绪
  ② 当前场景 desktop ⇒ 光世界（来自 `_worlds.json` 的 overrides）
  ③ 切到 `ch1.castle_town.castle_town` ⇒ 暗世界（原作房间 45）
  ④ 在暗世界拿到的道具，切回 desktop（光世界）⇒ 全部变成垃圾团里的东西
  ⑤ S 键菜单能开、能看到道具、能收到"神秘力量"文案
  ⑥ 场景可交互物（存档点）能真的交互

⚠️ 与 `verify_items48.py` 的分工：
    套件守**纯逻辑**（零 Qt、可离线、进 G2 基线）；
    本脚本守**接线**（要真起 App、真切场景），所以**不进 G2 基线**
    （它会实例化窗口、依赖离屏平台，比套件脆）。

用法::

    C:\\Python311\\python.exe "code-quality-audit/第48轮-道具与背包系统/_evidence/e2e_wire48.py"
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROUND))
PET = os.path.join(REPO, 'ralsei_pet')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.join(PET, 'modules'))
sys.path.insert(0, os.path.join(PET, 'src'))
os.chdir(PET)

from PyQt5.QtWidgets import QApplication          # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import main as M                                   # noqa: E402

FAIL = []


def check(name, cond, extra=''):
    print('%-46s %s %s' % (name, 'PASS' if cond else 'FAIL', extra))
    if not cond:
        FAIL.append(name)


pet = M.RalseiPet()
check('① App 起来了', pet is not None)
check('① 道具表就绪', pet.item_catalog is not None and not pet.item_catalog.load_errors,
      getattr(pet.item_catalog, 'load_errors', None))
check('① 两个袋子就绪', pet.inventory is not None, pet.inventory and pet.inventory.describe())
check('① 菜单 UI 就绪', pet.item_menu_ui is not None)
check('① 全局热键有结果记录', isinstance(pet._item_hotkey_done, tuple),
      'done=%s bad=%s' % (pet._item_hotkey_done, pet._item_hotkey_bad))
check('① 场景切换钩子挂上了', len(pet._scene_switch_hooks) == 1)

check('② 初始场景 = desktop', pet.current_scene == 'desktop', pet.current_scene)
check('② desktop ⇒ 光世界（overrides）', pet.inventory.world == 'light', pet.inventory.world)

# ---- 切到暗世界 ----
ok = pet.scene.switch('ch1.castle_town.castle_town')
check('③ 切到城堡镇成功', ok)
check('③ 城堡镇 ⇒ 暗世界', pet.inventory.world == 'dark', pet.inventory.world)
check('③ 章节 = ch1', pet.inventory.chapter == 'ch1', pet.inventory.chapter)
check('③ 原作房间 = 45', pet.inventory.original_room_id == 45, pet.inventory.original_room_id)

# ---- 暗世界捡东西 ----
a, i1 = pet.inventory.pick_up(1)          # 黑暗糖果
b, i2 = pet.inventory.pick_up(6)          # 顶尖蛋糕
check('④ 暗世界捡起 2 件', a and b and len(pet.inventory.bags['dark']) == 2)

# ---- 回桌面（光世界）⇒ 变垃圾团 ----
ok2 = pet.scene.switch('desktop')
check('④ 切回桌面成功', ok2)
check('④ 桌面 ⇒ 光世界', pet.inventory.world == 'light', pet.inventory.world)
check('★④ 暗世界道具全变垃圾团', len(pet.inventory.junk) == 2,
      pet.inventory.junk.names())
check('★④ 效果被掏空', pet.inventory.bags['dark'].slots[0].item.kind == 'none')

# ---- S 键菜单 ----
pet._item_menu_toggle_at = 0.0     # 模拟时间已过（去抖只挡重复投递）
pet.toggle_item_menu()
check('⑤ 菜单打开', pet.item_menu_ui.is_open())
check('⑤ 菜单标题 = 菜单', pet.item_menu_ui._title.text() == '菜单',
      pet.item_menu_ui._title.text())
check('⑤ 根菜单含垃圾团入口',
      any('垃圾团' in r[1].text() for r in pet.item_menu_ui._rows),
      [r[1].text() for r in pet.item_menu_ui._rows])
pet._item_menu_toggle_at = 0.0
pet.toggle_item_menu()
check('⑤ 菜单关上', not pet.item_menu_ui.is_open())

# ---- 回暗世界：垃圾件用不出效果 ----
pet.scene.switch('ch1.castle_town.castle_town')
check('④ 回暗世界仍是暗世界', pet.inventory.world == 'dark', pet.inventory.world)
seen = []
pet._item_menu_message = lambda t: seen.append(t)     # 换成本次验证的捕获器
pet.item_menu_ui.on_message = pet._item_menu_message
pet._item_menu_toggle_at = 0.0
pet.toggle_item_menu()
pet.item_menu_key('confirm')          # 根→道具
pet.item_menu_key('confirm')          # 道具→动作
pet.item_menu_key('confirm')          # 使用（垃圾件）
check('★④ 垃圾件用不出效果（走 UI 路径）',
      seen and seen[-1] == '它已经变成垃圾团里的东西了，什么也不会发生。', seen)
pet._item_menu_toggle_at = 0.0
pet.toggle_item_menu()

# ---- 场景可交互物 ----
check('⑥ 城堡镇有可交互物（存档点）', len(pet.item_props) >= 1,
      [p.describe() for p in pet.item_props])
got = []
for p in pet.item_props:
    p.present = lambda t, actor=None: (got.append(t), t)[1]
ok3 = pet.interact_scene_prop()
check('⑥ 交互发生了', bool(ok3))
check('⑥ 存档点台词出来了', bool(got), got)

# ---- 异世界使用 ⇒ 神秘力量（真实路径）----
# ⚠️ 第48轮实测教训：先把暗袋清空再验 —— 因为**垃圾判定优先于异章节/异世界**
#    （item_system 的判定顺序 = 垃圾 > 章节 > 世界 > 场景门控）。
#    上一版这里直接拿"已垃圾化的暗袋道具"去验异章节，拿到的自然是垃圾文案，
#    而这恰好**证实**了优先级是对的。要验神秘力量，必须用一件**没垃圾化**的道具。
import item_system as IS                            # noqa: E402

inv = pet.inventory
inv.bags['dark'].clear()                      # 清掉垃圾件，换一件干净的
inv.enter('ch2', 'dark', 'ch2.x', 10)         # 当前章节 = ch2
inv.pick_up(1, world='dark', chapter='ch2')   # 在 ch2 拿一件（出身 ch2）
inv.enter('ch3', 'dark', 'ch3.y', 20)         # 切到 ch3 ⇒ 那件道具成了"非当前场景"
# ⚠️ 开菜单**只能**走 toggle（`item_menu_key` 在关闭态刻意不响应 —— 单一入口）
pet._item_menu_toggle_at = 0.0
pet.toggle_item_menu()                        # → 打开，落在根菜单
pet.item_menu_key('confirm')                  # 根 → 道具
pet.item_menu_key('confirm')                  # 道具 → 动作
pet.item_menu_key('confirm')                  # 使用
check('★⑤ 神秘力量（异章节）', seen[-1] == IS.MSG_MYSTERY, seen[-1])

pet.close()
app.processEvents()
print()
print('FAIL =', FAIL)
print('hotkey done=%s bad=%s' % (pet._item_hotkey_done, pet._item_hotkey_bad))
