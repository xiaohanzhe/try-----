# -*- coding: utf-8 -*-
"""第48轮 · 补采器 v3（稳版）。

三处修正（都是本环境踩出来的）：
1. **对象名要展开成事件名**：`obj_overworldc` 不是 code 名，真名是
   `gml_Object_obj_overworldc_Step_0` 这种。⇒ 从同章 `names48.txt` 按前缀展开。
2. **`switch_asyncResume` 只有 `gml_Script_` 没有 `gml_GlobalScript_`** ⇒ 两个都试，MISS 不算错。
3. **E:\\Download\\_tmp 覆盖写会被拒**（Errno 13 / Errno 22）⇒ 写之前先 `os.remove`，
   输出目录固定用**新目录** `gml48b/`。

用法: C:\\Python311\\python.exe run_dump48c.py chapter1_windows [chapter2_windows ...]
"""
import io
import os
import shutil
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
CWD = r'E:\Download\UTMT_CLI_v0.9.2.0'
DRW = r'E:\Download\_tmp\drw'
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'dump_items48b.csx')
OUTDIR = 'gml48b'

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
    'switch_asyncPause', 'switch_asyncResume',
    'scr_84_load_ini', 'scr_change_language', 'scr_84_get_lang_string',
    'scr_84_init_localization', 'scr_84_get_subst_string', 'scr_84_lang_load',
    'scr_darkbox', 'scr_itemcomment', 'scr_healitem',
]
OBJS = [
    'obj_menuwriter', 'DEVICE_MENU', 'obj_savemenu', 'obj_shop1', 'obj_shop2',
    'obj_flowershop', 'obj_darkphone_event', 'obj_overworldc',
    'obj_mainchara', 'obj_savepoint', 'obj_readable',
    'obj_darkcontroller', 'obj_event_manager',
    'obj_dialoguer', 'obj_heartenemy',
]


def build_names(ch_dir):
    """CORE 脚本 + OBJS 的事件展开 + names48.txt 里其它关键命中。"""
    names = []

    def add(n):
        if n and n not in names:
            names.append(n)

    allnames = set()
    p = os.path.join(ch_dir, 'names48.txt')
    if os.path.isfile(p):
        for line in io.open(p, encoding='utf-8', errors='replace'):
            if '\t' in line:
                allnames.add(line.rstrip('\n').split('\t', 1)[1])

    for s in CORE:
        add('gml_GlobalScript_' + s)
        add('gml_Script_' + s)
    for o in OBJS:
        pref = 'gml_Object_' + o + '_'
        for n in sorted(allnames):
            if n.startswith(pref):
                add(n)
    return names, allnames


def safe_write(path, text):
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
    with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


for ch in (sys.argv[1:] or ['chapter1_windows']):
    W = os.path.join(DRW, ch)
    if not os.path.isfile(os.path.join(W, 'data.win')):
        print('缺少 data.win: %s' % W)
        continue
    names, allnames = build_names(W)
    safe_write(os.path.join(W, 'dump_names48.txt'), '\n'.join(names) + '\n')

    sdir = os.path.join(W, 'scripts')
    if not os.path.isdir(sdir):
        os.makedirs(sdir)
    dst = os.path.join(sdir, 'dump_items48b.csx')
    same = False
    if os.path.isfile(dst):
        try:
            with io.open(dst, 'rb') as a, io.open(SRC, 'rb') as b:
                same = a.read() == b.read()
        except OSError:
            same = False
    if not same:
        try:
            if os.path.isfile(dst):
                os.remove(dst)
            shutil.copyfile(SRC, dst)
        except OSError:
            print('   ⚠️ csx 复制被拒（已知间歇故障）；沿用旧副本继续')

    t0 = time.time()
    p = subprocess.Popen([EXE, 'load', os.path.join(W, 'data.win'), '-s', dst], cwd=CWD,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.read().decode('utf-8', 'replace')
    p.wait()
    print('[%s] 清单 %d 条  rc=%d  %.1fs' % (ch, len(names), p.returncode, time.time() - t0))
    if p.returncode != 0:
        print(out[-900:])
    lg = os.path.join(W, 'dump_log48b.txt')
    if os.path.isfile(lg):
        lines = io.open(lg, encoding='utf-8').read().splitlines()
        miss = [l for l in lines if l.startswith('MISS')]
        ok = [l for l in lines if l.startswith('OK')]
        print('  OK %d / MISS %d' % (len(ok), len(miss)))
        for l in miss[:20]:
            print('    ', l)
    print('  输出目录: %s' % os.path.join(W, OUTDIR))
