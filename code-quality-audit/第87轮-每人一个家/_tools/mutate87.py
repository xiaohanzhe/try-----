# -*- coding: utf-8 -*-
u"""第87轮**鉴别力体检**（变异测试）：把产品改坏 ⇒ `check87` 必须报红。

★ 铁律「判据必须有鉴别力」：只证明"当前 PASS"不够，还要证明"改坏会 FAIL"。
★ 每个变异都**先备份原文件、跑 check87、再还原**（不留痕 —— 用后即删的临时区
  在 E 盘，绝不落工作区）。
★ 判据用「check87 的退出码 + FAIL 行数」，不猜。
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PKG = os.path.join(ROOT, 'ralsei_pet')
TOOLS = os.path.join(ROOT, 'code-quality-audit', '第87轮-每人一个家', '_tools')
CHECK = os.path.join(TOOLS, 'check87.py')
BAK = r'E:\_tmp87\mutbak'
PY = r'C:\Python311\python.exe'

PLACEMENT = os.path.join(PKG, 'assets', 'npc', '_placement.json')
MAIN = os.path.join(PKG, 'src', 'main.py')
NPCP = os.path.join(PKG, 'modules', 'npc_placement.py')

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

MUTS = []


# --- M1: main.py 的 home_of 退回单参（复现第79轮那个真 bug）---
def m1():
    s = read(MAIN)
    b = s
    s = s.replace('home_of=lambda nid, _d=None: book.home_of(nid),',
                  'home_of=lambda nid: book.home_of(nid),')
    write(MAIN, s)
    return s != b


# --- M2: 三个取值器方法退回单参 ---
def m2():
    s = read(MAIN)
    b = s
    s = s.replace('def _npc_roam_traits(self, npc_id, _default=None):',
                  'def _npc_roam_traits(self, npc_id):')
    write(MAIN, s)
    return s != b


# --- M3: 候选池退回不过滤（跨作品又进自主移动池）---
def m3():
    s = read(MAIN)
    b = s
    s = s.replace('roster=self._npc_roam_roster(),', 'roster=book.ids(),')
    write(MAIN, s)
    return s != b


# --- M4: 给某个跨作品角色硬安一个 Deltarune 场景的家（B6 负控制应被抓不到，
#          但 A8/A 段该有反应；这里改 home 值去撞 C4/F 段的核验）---
def m4():
    s = read(PLACEMENT)
    b = s
    s = s.replace('"home": "ut.rooms.room_torhouse1"',
                  '"home": "ch1.unknown.unknown"')
    write(PLACEMENT, s)
    return s != b


# --- M5: 抹掉一条家的 evidence（A4 应报红）---
# ★ 变异必须**保真**：上一版把 JSON 拼坏了（`"" + "…"` 非法），结果报的是
#   "JSON 解析失败"（FAIL=9），测的不是"缺 evidence"。改成把值真清空。
def m5():
    s = read(PLACEMENT)
    b = s
    old = '"home_evidence": "房间名 room_torhouse1/2/3（Toriel 家）+ 实例 obj_torgen_house1(84,24) / obj_housemusic(260,20)"'
    new = '"home_evidence": ""'
    s = s.replace(old, new, 1)
    write(PLACEMENT, s)
    return s != b


# --- M6: 把 home_of 的回落逻辑去掉（A6 应报红）---
def m6():
    s = read(NPCP)
    b = s
    s = s.replace('return p.home or p.scene', 'return p.home')
    write(NPCP, s)
    return s != b


# --- M7: 把 by_source() 改回"数全部条目"（第87轮实测暴露的静默缺陷）---
#   A9 应报红（`authored` 会被 50 条家条目冲成 59，与 counts.by_source 不再相等）。
def m7():
    s = read(NPCP)
    b = s
    s = s.replace(
        "c = collections.Counter(p.source for p in self._by_id.values() if p.scene)",
        "c = collections.Counter(p.source for p in self._by_id.values())")
    write(NPCP, s)
    return s != b


MUTS = [
    ('M1 main.home_of 退回单参', MAIN, m1),
    ('M2 取值器方法退回单参', MAIN, m2),
    ('M3 候选池退回不过滤', MAIN, m3),
    ('M4 跨作品家改成 Deltarune 场景', PLACEMENT, m4),
    ('M5 抹掉一条 home_evidence', PLACEMENT, m5),
    ('M6 home_of 去掉回落', NPCP, m6),
    ('M7 by_source 数全部条目（不再只数站位）', NPCP, m7),
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
        # ★ 变异保真自检：改了 JSON 的话，必须仍是**合法 JSON**
        #   （否则报的是"JSON 坏了"，测的不是我们想测的那件事 —— 实测踩过）
        if target.endswith('.json'):
            try:
                json.load(io.open(target, encoding='utf-8'))
            except Exception as e:
                results.append((name, 'BADMUT(JSON 被弄坏:%s)' % e, 0, []))
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
