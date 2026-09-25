# -*- coding: utf-8 -*-
"""第48轮 · 跑 dump_items48.csx：按名字清单**非交互**反编译出真 GML。

名字来源：同章 probe_items48.json（名字普查）+ 本脚本内置的"必取名单"。

用法: C:\\Python311\\python.exe run_dump48.py chapter1_windows
"""
import io
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
CWD = r'E:\Download\UTMT_CLI_v0.9.2.0'
DRW = r'E:\Download\_tmp\drw'
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'dump_items48.csx')

# ★ 必取名单（脚本体在 gml_GlobalScript_*；对象在 gml_Object_<obj>_<event>）
CORE = [
    'scr_itemget', 'scr_itemremove', 'scr_itemshift', 'scr_itemcheck',
    'scr_itemname', 'scr_itemnamelist', 'scr_itemdesc', 'scr_itemdesc_b',
    'scr_itemdesc_oldtype', 'scr_itemuse', 'scr_iteminfo', 'scr_iteminfo_all',
    'scr_iteminfo_temp', 'scr_itemconsumeb', 'scr_itemcomment', 'scr_lrecoitem',
    'draw_item_icon',
    'scr_keyitemcheck', 'scr_keyitemget', 'scr_keyitemremove', 'scr_keyitemshift',
    'scr_keyiteminfo', 'scr_keyiteminfo_all',
    'scr_litemcheck', 'scr_litemdesc', 'scr_litemget', 'scr_litemname',
    'scr_litemremove', 'scr_litemshift', 'scr_litemuseb',
    'scr_healitem', 'scr_healitem_all', 'scr_healitemspell', 'scr_healallitemspell',
    'scr_weaponcheck_inventory', 'scr_armorcheck_inventory',
    'scr_dmenu_armor_selection_match',
    'scr_shopmenu', 'scr_shopmorearrow', 'scr_closemenu',
    'scr_84_add_menu_item', 'scr_84_draw_menu',
    'scr_setparty', 'scr_phonename', 'scr_phoneadd',
    # ★ 第48轮补采（场内菜单 = obj_overworldc + 暂停开关）
    'switch_asyncPause', 'switch_asyncResume',
    'scr_84_load_ini', 'scr_change_language', 'scr_84_get_lang_string',
]
OBJS = [
    'obj_menuwriter', 'DEVICE_MENU', 'obj_savemenu', 'obj_shop1', 'obj_shop2',
    'obj_flowershop', 'obj_darkphone_event',
    # ★ 第48轮补采：场内菜单控制器（global.menuno 真正被读写的地方）
    'obj_overworldc',
]

ch = sys.argv[1] if len(sys.argv) > 1 else 'chapter1_windows'
W = os.path.join(DRW, ch)
if not os.path.isfile(os.path.join(W, 'data.win')):
    print('缺少 data.win: %s' % W)
    sys.exit(1)

names = []


def add(n):
    if n and n not in names:
        names.append(n)


# 1) 内置必取（脚本双写：GlobalScript 真体 + Script 桩）
for s in CORE:
    add('gml_GlobalScript_' + s)
    add('gml_Script_' + s)
for o in OBJS:
    add(o)

# 2) 从同章普查里把**对象事件**也带上（gml_Object_*），
#    以及普查里出现的、不在 CORE 里的其它脚本
probe = os.path.join(W, 'probe_items48.json')
if os.path.isfile(probe):
    t = io.open(probe, encoding='utf-8').read()
    code_sec = t.split('"code_hits"')[1].split('"script_hits"')[0]
    for n in re.findall(r'^  "([^"]+)"\s*:', code_sec, re.M):
        if n.startswith('gml_Object_'):
            add(n)

# 写成清单
with io.open(os.path.join(W, 'dump_names48.txt'), 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(names) + '\n')

sdir = os.path.join(W, 'scripts')
if not os.path.isdir(sdir):
    os.makedirs(sdir)
dst = os.path.join(sdir, 'dump_items48.csx')
# ⚠️ E:\Download\_tmp 存在「已存在文件写/覆盖被拒（PermissionError 13）」的间歇故障
#    （本项目已知坑，见记忆 §1）。csx 内容没变时**别复制**，直接用旧副本跑。
_need_copy = True
if os.path.isfile(dst):
    try:
        with io.open(dst, 'rb') as a, io.open(SRC, 'rb') as b:
            _need_copy = a.read() != b.read()
    except OSError:
        _need_copy = True
if _need_copy:
    try:
        shutil.copyfile(SRC, dst)
    except PermissionError:
        print('   ⚠️ csx 复制被拒（已知间歇故障）；沿用旧副本继续')

t0 = time.time()
p = subprocess.Popen([EXE, 'load', os.path.join(W, 'data.win'), '-s', dst], cwd=CWD,
                     stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = p.stdout.read().decode('utf-8', 'replace')
p.wait()
print('[%s] rc=%d  %.1fs' % (ch, p.returncode, time.time() - t0))
print(out[-1200:])
lg = os.path.join(W, 'dump_log48.txt')
if os.path.isfile(lg):
    lines = io.open(lg, encoding='utf-8').read().splitlines()
    miss = [l for l in lines if l.startswith('MISS')]
    print('  清单 %d 条；MISS %d 条' % (len(names), len(miss)))
    for l in miss[:30]:
        print('    ', l)
