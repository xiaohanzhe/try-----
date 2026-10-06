# -*- coding: utf-8 -*-
u"""第88轮**鉴别力体检**（变异测试）：把产品改坏 ⇒ `check88` 必须报红。

★ 铁律「判据必须有鉴别力」：只证明"当前 PASS"不够，还要证明"改坏会 FAIL"。
★ 每个变异都**先备份原文件、跑 check88、再还原**（不留痕 —— 临时区在 E 盘，
  绝不落工作区）。
★ 判据用「check88 的退出码 + FAIL 行数」，不猜。

✗ 变异保真（第87轮教训）：变异若把文件弄成**语法错**，报的是「编译不过」而不是
  我们想测的那件事 ⇒ 每个变异跑完后做一次 `ast.parse` 自检（`BADMUT` 直接判不合格）。
"""
import ast
import io
import os
import re
import shutil
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PKG = os.path.join(ROOT, 'ralsei_pet')
TOOLS = os.path.join(ROOT, 'code-quality-audit', '第88轮-NPC交互链', '_tools')
CHECK = os.path.join(TOOLS, 'check88.py')
BAK = r'E:\_tmp88\mutbak'
PY = r'C:\Python311\python.exe'

MAIN = os.path.join(PKG, 'src', 'main.py')
MODULE = os.path.join(PKG, 'modules', 'npc_interact.py')

os.makedirs(BAK, exist_ok=True)


def read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(s)


def run_check():
    r = subprocess.run([PY, CHECK], cwd=TOOLS, capture_output=True)
    out = (r.stdout or b'').decode('utf-8', 'replace')
    n_fail = len(re.findall(r'\[FAIL\]', out))
    return r.returncode, n_fail, out


def backup(p):
    dst = os.path.join(BAK, os.path.basename(p))
    shutil.copyfile(p, dst)
    return dst


def restore(p):
    dst = os.path.join(BAK, os.path.basename(p))
    shutil.copyfile(dst, p)


print('=== 基线（未变异）===')
rc0, nf0, _ = run_check()
print('exit=%s FAIL=%s' % (rc0, nf0))
if nf0 != 0:
    print('!! 基线不干净，体检无意义，退出')
    sys.exit(2)


# --- M1: 射线系数改一个（下段 28 ⇒ 27）⇒ A1 必须报红 ---
def m1():
    s = read(MODULE)
    b = s
    s = s.replace('y1 = top + 28.0 * d', 'y1 = top + 27.0 * d')
    write(MODULE, s)
    return s != b


# --- M2: 去掉归一化（逆序矩形不摆正）⇒ A1/B 段会因形状错而红 ---
def m2():
    s = read(MODULE)
    b = s
    s = s.replace('    if x1 > x2:\n        x1, x2 = x2, x1\n', '')
    write(MODULE, s)
    return s != b


# --- M3: 让"背对着也命中"（把射线矩形放大成整屏）⇒ C2 必须报红 ---
#   ★ 保真：改的是 ray_rect 尾部 return 的**第一个** `(x1, y1, x2, y2)`
#     （即 ray_rect 的收尾行），不是让它语法错。
def m3():
    s = read(MODULE)
    b = s
    s = s.replace(
        '    if y2 - y1 < MIN_RAY_THICK:\n'
        '        y2 = y1 + MIN_RAY_THICK\n'
        '    return (x1, y1, x2, y2)',
        '    if y2 - y1 < MIN_RAY_THICK:\n'
        '        y2 = y1 + MIN_RAY_THICK\n'
        '    return (-1e9, -1e9, 1e9, 1e9)')
    write(MODULE, s)
    return s != b


# --- M4: 转向反了（facing_toward 的 dx/dy 判据反）⇒ D2 必须报红 ---
def m4():
    s = read(MODULE)
    b = s
    s = s.replace(
        "    if abs(dx) >= abs(dy):\n"
        "        return FACE_RIGHT if dx > 0 else FACE_LEFT\n"
        "    return FACE_DOWN if dy > 0 else FACE_UP",
        "    if abs(dx) >= abs(dy):\n"
        "        return FACE_LEFT if dx > 0 else FACE_RIGHT\n"
        "    return FACE_UP if dy > 0 else FACE_DOWN")
    write(MODULE, s)
    return s != b


# --- M5: 退化阈值改回"宽容带"⇒ D1 等价性必须报红（本轮的原始 bug）---
def m5():
    s = read(MODULE)
    b = s
    s = s.replace('    if dx == 0.0 and dy == 0.0:\n        return None',
                  '    if abs(dx) < 1e-9 and abs(dy) < 1e-9:\n        return None')
    write(MODULE, s)
    return s != b


# --- M6: Z 键不分流（未附身也去 toggle_possession）⇒ E5 必须报红 ---
def m6():
    s = read(MAIN)
    b = s
    s = s.replace(
        '                else:\n'
        '                    self.interact_scene_prop()\n'
        '                event.accept()\n'
        '                return\n'
        '            if key == _Qt.Key_G:',
        '                else:\n'
        '                    self.toggle_possession()  # MUTATED\n'
        '                event.accept()\n'
        '                return\n'
        '            if key == _Qt.Key_G:')
    write(MAIN, s)
    return s != b


# --- M7: 说话不走 npc_speak（改成直调 dialogue_ui）⇒ E6 必须报红 ---
def m7():
    s = read(MAIN)
    b = s
    s = s.replace('self.npc_speak(npc_id, \'\', _on_reply)',
                  'self._npc_say_line(npc_id, \'\')')
    write(MAIN, s)
    return s != b


# --- M8: 交互不再调射线选人（删掉 _npc_interact_pick 调用）⇒ E4 必须报红 ---
def m8():
    s = read(MAIN)
    b = s
    s = s.replace('            hit = self._npc_interact_pick()',
                  '            hit = None  # MUTATED')
    write(MAIN, s)
    return s != b


# --- M9: 明暗世界另判一遍（不走 world_of_scene）⇒ E10 必须报红 ---
def m9():
    s = read(MAIN)
    b = s
    s = s.replace(
        '    def _npc_interact_darkzone(self):',
        '    def _npc_interact_darkzone(self):  # MUTATED\n'
        '        return npc_interact_mod.DARKZONE_LIGHT  # noqa\n\n'
        '    def _npc_interact_darkzone_orig(self):')
    write(MAIN, s)
    return s != b


MUTS = [
    ('M1 射线系数 28→27', MODULE, m1),
    ('M2 去掉矩形归一化', MODULE, m2),
    ('M3 射线放大成整屏（背对也命中）', MODULE, m3),
    ('M4 转向方向反', MODULE, m4),
    ('M5 退化阈值改宽容带', MODULE, m5),
    ('M6 Z 键不分流', MAIN, m6),
    ('M7 说话不经 npc_speak', MAIN, m7),
    ('M8 不调射线选人', MAIN, m8),
    ('M9 明暗世界另判一遍', MAIN, m9),
]

results = []
for name, target, fn in MUTS:
    backup(target)
    applied = False
    fails = []
    try:
        applied = fn()
        if not applied:
            results.append((name, 'SKIP(变异没应用上)', 0, []))
            continue
        # ★ 变异保真自检：必须仍是**可解析的 Python**（否则报的是"语法错"）
        try:
            ast.parse(read(target))
        except Exception as e:
            results.append((name, 'BADMUT(语法被弄坏:%s)' % e, 0, []))
            continue
        rc, nf, out = run_check()
        fails = [l.strip() for l in out.splitlines() if '[FAIL]' in l]
        results.append((name, 'exit=%s' % rc, nf, fails))
    finally:
        restore(target)

print()
print('=== 鉴别力体检结果 ===')
allok = True
for name, st, nf, fails in results:
    ok = nf > 0
    if not ok:
        allok = False
    print('%-38s %-12s FAIL=%-3s %s' % (name, st, nf, 'OK' if ok else '!! 无鉴别力'))
    for l in fails[:2]:
        print('        ', l)

print()
print('结论：', '全部变异都被抓到' if allok else '有变异未被抓到（判据鉴别力不足）')
sys.exit(0 if allok else 1)
