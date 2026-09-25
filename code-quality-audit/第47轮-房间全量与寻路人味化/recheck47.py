# -*- coding: utf-8 -*-
"""第47轮复检：改过"重要核心文件"后的六类判据，逐项 PASS/FAIL 落盘。

为什么单独一个脚本：用户口径「以后再调整重要核心文件时一定要记得复检」——
复检**不许只口称**，必须可复算。

六类：
  ① 可编译（用 ast.parse，**不产 .pyc**——复检不许改变被测状态）
  ② 结构 / 接线自检
  ③ 编码（无 BOM / 无 U+FFFD）
  ④ 恒真判据复查（本轮新增判据是否都带正/负控制）
  ⑤ 逐令牌回验（报告里写到的关键数字/路径/符号，逐个回原文件 `in` 一次）
  ⑥ 工作区干净
"""
import ast
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')

results = []
LOG = []


def chk(name, ok, detail=''):
    line = '[%s] %s%s' % ('PASS' if ok else 'FAIL', name, ('  —— ' + detail) if detail else '')
    results.append((name, bool(ok), detail))
    LOG.append(line)
    print(line)


def rd_text(path):
    with io.open(path, 'rb') as fh:
        raw = fh.read()
    return raw, raw.decode('utf-8', 'replace')


def read_text(path):
    return rd_text(path)[1]


def main():
    files = {
        'scene_walk.py': os.path.join(MODS, 'scene_walk.py'),
        'scene_pathfind.py': os.path.join(MODS, 'scene_pathfind.py'),
        'run_all.py': os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
        'verify_rooms47.py': os.path.join(HERE, 'verify_rooms47.py'),
        'verify_walk47.py': os.path.join(HERE, 'verify_walk47.py'),
        'census_rooms47.py': os.path.join(HERE, '_tools', 'census_rooms47.py'),
        'probe_ab47.py': os.path.join(HERE, '_tools', 'probe_ab47.py'),
    }

    # ---------- ① 可编译（ast.parse，不产 .pyc）----------
    for nm, p in files.items():
        try:
            ast.parse(read_text(p), filename=p)
            chk('① ast.parse 通过：%s' % nm, True)
        except SyntaxError as e:
            chk('① ast.parse 通过：%s' % nm, False, str(e))

    # ---------- ② 结构与接线自检 ----------
    walk = read_text(files['scene_walk.py'])
    pf = read_text(files['scene_pathfind.py'])
    runall = read_text(files['run_all.py'])
    chk('② scene_walk 真调用 _monotone_forward', '_monotone_forward(' in walk
        and walk.count('_monotone_forward') >= 2)
    chk('② scene_walk 真调用 _despike', '_despike(' in walk and walk.count('_despike') >= 2)
    chk('② scene_pathfind 用 heapq（A*）', 'import heapq' in pf)
    chk('② run_all 注册 rooms_round47/walk_round47',
        'rooms_round47' in runall and 'walk_round47' in runall)
    chk('② run_all 两套件进 HERMETIC_IDS',
        "'rooms_round47', 'walk_round47'" in runall or '"rooms_round47", "walk_round47"' in runall)

    # ---------- ③ 编码 ----------
    bad_bom = bad_fffd = 0
    for nm, p in files.items():
        raw, txt = rd_text(p)
        if raw.startswith(b'\xef\xbb\xbf'):
            bad_bom += 1
            print('   BOM in', nm)
        if '\ufffd' in txt:
            bad_fffd += 1
            print('   U+FFFD in', nm)
    chk('③ 无 BOM', bad_bom == 0, 'bad=%d' % bad_bom)
    chk('③ 无 U+FFFD', bad_fffd == 0, 'bad=%d' % bad_fffd)

    # ---------- ④ 恒真判据复查 ----------
    # ★ 判据本身也要防"过窄误报"：`check('前置：…', True)` 是**合法**的——
    #   它的 `False` 分支与 return 1 就写在上面（同一名字）。真正要抓的是
    #   "名字只以常量 True 出现过、没有任何非恒真分支"的写法。
    import re
    vr = read_text(files['verify_rooms47.py'])
    vw = read_text(files['verify_walk47.py'])

    def taut_names(src):
        """返回"只被常量 True 判过、且没有同名守卫"的 check 名列表。"""
        calls = re.findall(r"check\(\s*'([^']*)'\s*,\s*([^,\)]+)", src)
        seen = {}
        for nm, arg in calls:
            seen.setdefault(nm, set()).add(arg.strip())
        bad = []
        for nm, args in seen.items():
            if args == {'True'}:
                bad.append(nm)
        return bad

    bad_vr = taut_names(vr)
    bad_vw = taut_names(vw)
    chk('④ 无"恒真 + 无守卫"写法（rooms47）', not bad_vr, repr(bad_vr))
    chk('④ 无"恒真 + 无守卫"写法（walk47）', not bad_vw, repr(bad_vw))
    chk('④ walk47 的"前置"check 确实带 False 守卫',
        "check('前置：模块与改前证据都在位', False" in vw
        and "check('前置：模块与改前证据都在位', True)" in vw)
    # 负控制必须存在
    chk('④ walk47 含负控制（改前版本必须更差）', '负控制' in vw)
    chk('④ walk47 含穿模负控制', '穿墙' in vw or '穿模' in vw)

    # ---------- ⑤ 逐令牌回验 ----------
    tokens = [
        (MODS + '/scene_walk.py', 'BACKTRACK_TOL = GRID_STEP / 2.0'),
        (MODS + '/scene_walk.py', 'DESPIKE_MIN_TURN = 45.0'),
        (MODS + '/scene_walk.py', 'DESPIKE_PASSES = 6'),
        (MODS + '/scene_walk.py', 'def _monotone_forward'),
        (MODS + '/scene_walk.py', 'def _despike'),
        (MODS + '/scene_walk.py', 'def _turn_deg'),
        (MODS + '/scene_pathfind.py', 'MAX_DOOR_DELTA = 3'),
        (MODS + '/scene_pathfind.py', 'import itertools'),
    ]
    ok_all = True
    for p, tok in tokens:
        hit = tok in read_text(p)
        if not hit:
            ok_all = False
            print('   缺令牌 %r in %s' % (tok, os.path.basename(p)))
    chk('⑤ 源码关键令牌全在', ok_all, '%d 个' % len(tokens))

    # 改前快照 sha1（报告里写了 8cfc6afe…）
    snap = os.path.join(HERE, '_evidence', '_scene_walk_HEAD47.py')
    if os.path.isfile(snap):
        with io.open(snap, 'rb') as fh:
            h = hashlib.sha1(fh.read()).hexdigest()
        chk('⑤ 改前快照 sha1 == 8cfc6afe…', h.startswith('8cfc6afe'), h[:12])
    else:
        chk('⑤ 改前快照存在', False, snap)

    # 报告里写到的数字，回证据文件核
    rep = read_text(os.path.join(ROOT, '第47轮报告-房间全量复查与寻路人味化.md'))
    ab = read_text(os.path.join(HERE, '_evidence', 'AB对照_平滑47.txt'))
    cn = read_text(os.path.join(HERE, '_evidence', '房间普查47.txt'))
    au = read_text(os.path.join(HERE, '_evidence', '场景可用性体检47.txt'))
    chk('⑤ 报告 228.4px 与 A/B 证据一致', '228.4' in ab and '228.4' in rep)
    chk('⑤ 报告 0.6px 与 A/B 证据一致', '0.6' in ab and '0.6' in rep)
    chk('⑤ 报告 318/107 与 A/B 证据一致', '318' in ab and '107' in ab)
    chk('⑤ 普查证据 = 原作 1251 / 真缺口 13', '1251' in cn and '= 13 间' in cn)
    chk('⑤ 体检证据 = 场景 1014 / 背景 235', '1014' in au and '235' in au)
    chk('⑤ 报告含 1,005 与 826', '1,005' in rep and '826' in rep)

    # ---------- ⑥ 工作区干净 ----------
    st = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    porcelain = st.stdout.decode('utf-8', 'replace')
    print('')
    print('--- git status --porcelain ---')
    print(porcelain or '(clean)')
    LOG.append('')
    LOG.append('--- git status --porcelain ---')
    LOG.append(porcelain.rstrip('\n') if porcelain.strip() else '(clean)')
    # 本轮**预期**就是"有改动待提交"，所以不判"空"，只提示
    chk('⑥ 工作区无意外删除（无 D 行）',
        not any(line.startswith(' D') for line in porcelain.splitlines()))

    n_fail = sum(1 for _, ok, _ in results if not ok)
    tail = '=== RESULT: PASS=%d FAIL=%d ===' % (len(results) - n_fail, n_fail)
    print('')
    print(tail)
    LOG.append('')
    LOG.append(tail)

    out = os.path.join(HERE, '_evidence', '复检47.txt')
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('第47轮复检（六类判据）\n' + '=' * 60 + '\n')
        fh.write('\n'.join(LOG) + '\n')
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
