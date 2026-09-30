# -*- coding: utf-8 -*-
"""第68轮 · 按需搬运「可交互类」实例引用到的 sprite 进 `assets/scenes/objs/`。

判据来源 = **产品侧 `item_interact.classify()`**（单一真源）。
不在这里重写一份"哪些算可交互"的分类 —— 那会长出第二份真相。

搬哪些：只搬 `inst68*` 里**分类命中可交互 kind**的实例所引用的 sprite。
不搬全量（ch1 就 2941 张）—— 那是浪费仓库体积。
幂等：已存在且大小一致 → 跳过。
"""
import io
import importlib.util
import json
import os
import re
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
EV68 = os.path.join(ROOT, 'code-quality-audit', '第68轮-可交互道具实例补采', '_evidence')
E43 = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证', '_evidence')
DST = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
SRC_ROOT = r'E:\Download\_tmp\dr_out'
CHDIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows', 'ch3': 'chapter3_windows',
         'ch4': 'chapter4_windows', 'ch5': 'chapter5_windows'}
OBMAP = {'ch1': 'objmap43.txt', 'ch2': 'chapter2_objmap43.txt', 'ch3': 'chapter3_objmap43.txt',
         'ch4': 'chapter4_objmap43.txt', 'ch5': 'chapter5_objmap43.txt'}
INST = {'ch1': 'inst68.json', 'ch2': 'ch2_inst68.json', 'ch3': 'ch3_inst68.json',
        'ch4': 'ch4_inst68.json', 'ch5': 'ch5_inst68.json'}

#: ★ 本轮要补的 kind —— 覆盖 `item_interact.PROP_CLASSES` 里**声明 in_data=True**
#: 但产物里 0 条的类（实测：`obj_dw_church*_savepoint` 的 spr 是 `spr_eventsmall`、
#: `obj_dw_churchc_savepoint_judgmentbell` 是 `spr_bell_small`、
#: `obj_ch4_DCA12_darkfountain` 是 `spr_fountinedge_narrow`）⇒ 一并搬，
#: 否则"声明有数据、产物却 0 条"这条不实会一直挂着。
WANT_KINDS = frozenset({'readable', 'sign', 'chest', 'pickup', 'interactable', 'furniture',
                        'savepoint', 'fountain'})


def _load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def parse_objmap(path):
    out = {}
    if not os.path.isfile(path):
        return out
    with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            name = parts[1].strip()
            m = re.search(r'spr=([^\t]*)', line)
            if name:
                out[name] = m.group(1).strip() if m and m.group(1).strip() else None
    return out


def main():
    # ★ `item_interact` 顶部 `from companion import Interactable` ⇒ modules/ 必须在 path 上。
    mods = os.path.join(ROOT, 'ralsei_pet', 'modules')
    if mods not in sys.path:
        sys.path.insert(0, mods)
    ii = _load_mod(os.path.join(mods, 'item_interact.py'), 'ii68')

    need = {}       # spr -> set(obj)
    per_ch = {}     # (ch, spr) -> set(files)
    if not os.path.isdir(DST):
        os.makedirs(DST)

    for ch, fn in INST.items():
        p = os.path.join(EV68, fn)
        if not os.path.isfile(p):
            print('  !! 缺实例文件 %s' % fn)
            continue
        with io.open(p, 'r', encoding='utf-8') as fh:
            d = json.load(fh)
        objmap = parse_objmap(os.path.join(E43, OBMAP[ch]))
        objs = set()
        n_hit = 0
        for rec in (d.get('rooms') or []):
            for it in (rec.get('insts') or []):
                nm = it.get('obj')
                if not nm:
                    continue
                rec_kind = ii.classify(nm)
                if not rec_kind or rec_kind.get('kind') not in WANT_KINDS:
                    continue
                n_hit += 1
                objs.add(nm)
        print('%-4s 可交互类实例 %-5d 涉及 obj 名 %d' % (ch, n_hit, len(objs)))
        for nm in sorted(objs):
            spr = objmap.get(nm)
            if not spr:
                continue
            need.setdefault(spr, set()).add(nm)

    print('')
    print('需要 sprite 名 %d 个：%s' % (len(need), sorted(need)))
    for spr, srcs in sorted(need.items()):
        print('  %-24s <- %s' % (spr, sorted(srcs)))

    # ---- 逐章找文件（同 spr 可能多帧）----
    for ch, cd in CHDIR.items():
        sd = os.path.join(SRC_ROOT, cd, 'Sprites')
        if not os.path.isdir(sd):
            print('  [%s] Sprites 目录缺失' % ch)
            continue
        files = os.listdir(sd)
        for spr in need:
            for f in files:
                if re.match(r'^%s_\d+\.png$' % re.escape(spr), f):
                    per_ch.setdefault((ch, spr), set()).add(f)

    copied = skipped = 0
    seen = set()
    for (ch, spr), files in sorted(per_ch.items()):
        for f in sorted(files):
            if f in seen:
                continue
            seen.add(f)
            src = os.path.join(SRC_ROOT, CHDIR[ch], 'Sprites', f)
            dst = os.path.join(DST, f)
            if not os.path.isfile(src):
                print('  !! 源缺失 %s' % src)
                continue
            if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src):
                skipped += 1
                continue
            shutil.copy2(src, dst)
            copied += 1

    n = len(os.listdir(DST))
    total = sum(os.path.getsize(os.path.join(DST, f)) for f in os.listdir(DST))
    print('')
    print('copied=%d skipped=%d' % (copied, skipped))
    print('objs/ 现有文件 %d 个，共 %.2f MB' % (n, total / 1048576.0))
    # 校验：每个需要的 spr 是否真有素材落地
    got = set()
    for f in os.listdir(DST):
        m = re.match(r'^(.*)_\d+\.png$', f)
        if m:
            got.add(m.group(1))
    missing = sorted(s for s in need if s not in got)
    print('未落地 sprite = %s' % (missing or '(无)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
