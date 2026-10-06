# -*- coding: utf-8 -*-
u"""第94轮变异测试：把本轮每一处修复**逐个打回原形**，`check94` 必须报红。

为什么必须有它（记忆铁律）
--------------------------
「**夹具不保真 = 报假问题**」（比报红更危险）与「**恒真判据比不写还危险**」：
一条判据只有在"破坏它就会红"时才叫守卫。本脚本对每一处修复做一次**定向变异**，
断言**指定的那条判据**（而不是"随便红一条"）变成 FAIL。

负控制
------
`M0 注释改写`：不改变任何语义的变异**必须** FAIL=0 —— 证明本夹具不是"一改就红"。

做法
----
把 `pet_ai.py` / `main.py` 复制成 `_mut94/pet_<id>.py` / `_mut94/main_<id>.py`，
用文本替换做定点变异，然后以
`CHECK94_PET_AI=<副本> CHECK94_MAIN=<副本>` 跑 `check94.py`，解析它的输出。
产品代码与仓库文件**全程只读**（副本写在临时区，跑完即删）。
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet', 'modules', 'pet_ai.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CHECK = os.path.join(HERE, 'check94.py')
PY = sys.executable or r'C:\Python311\python.exe'

TMP = os.environ.get('MUT94_TMP') or os.path.join(
    os.environ.get('TEMP', r'C:\Users\23002\AppData\Local\Temp'), '_mut94')
if os.path.isdir(TMP):
    shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)

with open(PET, encoding='utf-8') as _fh:
    PET_SRC = _fh.read()
with open(MAIN, encoding='utf-8') as _fh:
    MAIN_SRC = _fh.read()

# ------------------------------------------------------------------ 变异清单
# (id, 说明, 期望变成 FAIL 的判据子串, 目标文件, old, new, 替换次数[, 锚点应命中次数])
#
# ⚠️ 期望值一律用**带尾空格的编号**（如 'A1 '），因为 `B1` 是 `B1b` 的前缀 ——
#    用 'B1' 会被 `[FAIL] B1b …` 误当成命中（判据过宽 = 假达标）。
_SYNC = ("                        if (getattr(self, '_is_being_dragged', False)\n"
         "                                and getattr(self, 'drag_position', None) is not None):\n"
         "                            self.drag_position = QPoint(\n"
         "                                self.drag_position.x()\n"
         "                                + target_width // 2 - self.width() // 2,\n"
         "                                self.drag_position.y()\n"
         "                                + target_height // 2 - self.height() // 2)\n"
         "\n")

MUTS = [
    # ---- M0 负控制：无语义变化 ----
    ('M0', '负控制：只改注释（无语义变化）⇒ 必须 FAIL=0', None, 'pet',
     u'# ★ 第94轮修复：**睡眠**也必须算“关键过程”。',
     u'# ★ 第94轮修复：**睡眠**也必须算“关键过程”（注释改写）', 1),

    # ---- A 段：pet_ai 睡眠守卫 ----
    ('M1', 'A：`_skip_if_critical` 摘掉睡眠守卫（回到"漏 sleep"的原样）', 'A1 ', 'pet',
     "        if getattr(self.parent, 'is_sleeping', False):\n"
     "            return True\n"
     "        return False",
     "        return False", 1),
    ('M2', 'A：`trigger_action` 摘掉睡眠守卫（只守上层是不够的）', 'A2 ', 'pet',
     "        # ★ 第94轮修复：睡眠期间不允许 AI 动作改写动画（同 `_skip_if_critical`）。\n"
     "        if getattr(self.parent, 'is_sleeping', False):\n"
     "            return\n",
     "", 1),

    # ---- B 段：睡眠自愈 ----
    ('M3', 'B：`_use_force` 打回"只把 idle 当状态恢复"（sleep 再也回不来）', 'B2 ', 'main',
     "_use_force = is_same_category or (new_animation in ('idle', 'sleep'))",
     "_use_force = is_same_category or (new_animation == 'idle')", 1),
    ('M4', 'B1b：`_use_force` 算了但**不再被消费**（抽到的是个死变量）', 'B1b', 'main',
     "self.change_animation(new_animation, force=_use_force)",
     "self.change_animation(new_animation, force=False)", 1),
    ('M5', 'B5：删掉第91轮那条 `elif self.is_sleeping: new_animation = "sleep"`', 'B5 ', 'main',
     '        elif self.is_sleeping:\n            new_animation = "sleep"\n',
     "", 1),

    # ---- C 段：拖拽锚点同步 ----
    ('M6', 'C：把两个渲染分支的同步块**整段删掉**（= 回到"先窜后弹"）', 'C1 ', 'main',
     _SYNC, "", 2),
    ('M7', 'C：只把**第一处**同步挪到 `setGeometry` 之后（顺序被破坏）', 'C3 ', 'main',
     _SYNC + "                        # 批量更新大小和位置，减少重绘\n"
     "                        self.setGeometry(new_x, new_y, target_width, target_height)",
     "                        # 批量更新大小和位置，减少重绘\n"
     "                        self.setGeometry(new_x, new_y, target_width, target_height)\n" + _SYNC, 1, 2),
    ('M8', 'C：把守卫里的 `drag_position is not None` 那半句拿掉（只留拖拽条件）', 'C1 ', 'main',
     "if (getattr(self, '_is_being_dragged', False)\n"
     "                                and getattr(self, 'drag_position', None) is not None):",
     "if getattr(self, '_is_being_dragged', False):", 2),
    ('M9', 'C6：把 `QPoint` 从 import 里拿掉（只在拖拽时 NameError）', 'C6 ', 'main',
     "from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal",
     "from PyQt5.QtCore import Qt, QTimer, QRect, pyqtSignal", 1),
]

_passed = 0
_failed = []


def run_check(pet_path, main_path):
    env = dict(os.environ)
    env['CHECK94_PET_AI'] = pet_path
    env['CHECK94_MAIN'] = main_path
    env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run([PY, CHECK], capture_output=True, cwd=HERE, env=env, timeout=300)
    out = r.stdout.decode('utf-8', 'replace')
    return out, r.returncode


print('=' * 74)
print(u'第94轮变异测试：%d 个变异（负控制 1 个）' % len(MUTS))
print('=' * 74)

for _m in MUTS:
    mid, desc, expect, which, old, new, cnt = _m[:7]
    # ★ 第8个字段（可选）= "锚点**应该**出现几次"。默认与替换次数相同；
    #   M7 那类"两个同构分支里只动第一个"的变异，命中 2 次但只换 1 次。
    exp_cnt = _m[7] if len(_m) > 7 else cnt
    src = PET_SRC if which == 'pet' else MAIN_SRC
    if src.count(old) != exp_cnt:
        print('[SETUP-FAIL] %s %s —— 变异锚点命中 %d 次（期望 %d，产品代码已变？）'
              % (mid, desc, src.count(old), exp_cnt))
        _failed.append(mid)
        continue
    mutated = src.replace(old, new, cnt)

    pet_path, main_path = PET, MAIN
    if which == 'pet':
        pet_path = os.path.join(TMP, 'pet_%s.py' % mid)
        with open(pet_path, 'w', encoding='utf-8') as fh:
            fh.write(mutated)
    else:
        main_path = os.path.join(TMP, 'main_%s.py' % mid)
        with open(main_path, 'w', encoding='utf-8') as fh:
            fh.write(mutated)

    out, rc = run_check(pet_path, main_path)
    hits = re.findall(r'PASS=(\d+)\s+FAIL=(\d+)', out)
    n_fail = int(hits[-1][1]) if hits else -1
    fail_lines = [l for l in out.splitlines() if l.startswith('[FAIL]')]

    if expect is None:
        ok = (n_fail == 0 and rc == 0)
        detail = 'FAIL=%d rc=%d' % (n_fail, rc)
    else:
        hit = [l for l in fail_lines if expect in l]
        ok = bool(hit)
        detail = 'expect=%r hit=%s FAIL=%d' % (
            expect, (hit[0][:74] if hit else 'NONE'), n_fail)

    if ok:
        _passed += 1
        print('[OK]   %s %s    %s' % (mid, desc, detail))
    else:
        _failed.append(mid)
        print('[MISS] %s %s    %s' % (mid, desc, detail))
        for l in fail_lines[:6]:
            print('         %s' % l[:112])

shutil.rmtree(TMP, ignore_errors=True)

print('=' * 74)
print('变异测试：OK=%d MISS=%d' % (_passed, len(_failed)))
if _failed:
    print('未达成：%s' % _failed)
print('=' * 74)
sys.exit(0 if not _failed else 1)
