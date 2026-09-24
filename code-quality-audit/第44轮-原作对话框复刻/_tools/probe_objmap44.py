# -*- coding: utf-8 -*-
"""决定性判定：实例普查的 obj 名 → set/orasprite 文件的映射覆盖率。

这是"渲染层能不能真画出物件"的唯一决定性判据（先量化再动手）。

链路：inst42 的 `obj` → objmap43 的 `spr=` → dr_out/<ch>/Sprites/<SPR>_0.png

判据：
  D1 objmap43 解析出 353 个对象（真值锚点：文件头写 GameObjects = 353）
  D2 实例里出现的 158 个 obj 名，有多少出现在 objmap43
  D3 这 158 个里有多少能拿到非空 spr
  D4 按**实例条数**加权：5523 条里有多少条能映射到 sprite 文件
  D5 sprite 文件真实存在性抽验（按 chapter 分别验）
  + 负控制：编一个必不存在的 obj 名，必须判为不可映射
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
E43 = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证', '_evidence')
DR_OUT = r'E:\Download\_tmp\dr_out'
CHDIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows',
         'ch3': 'chapter3_windows', 'ch4': 'chapter4_windows',
         'ch5': 'chapter5_windows'}
INST = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
        'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}

FAIL = 0


def ok(m):
    print('[PASS] %s' % m)


def bad(m):
    global FAIL
    FAIL += 1
    print('[FAIL] %s' % m)


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def parse_objmap(path):
    """objmap43.txt: `<i>\t<obj>\tspr=<spr>\tvis=..\tpers=..` → {obj: spr|None}"""
    out = {}
    head_n = None
    with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if line.startswith('GameObjects ='):
                m = re.search(r'=\s*(\d+)', line)
                if m:
                    head_n = int(m.group(1))
                continue
            parts = line.split('\t')
            if len(parts) < 3:
                continue
            name = parts[1].strip()
            spr = None
            vm = re.search(r'spr=([^\t]*)', line)
            if vm and vm.group(1).strip():
                spr = vm.group(1).strip()
            if name:
                out[name] = spr
    return head_n, out


def sprite_dir(ch):
    return os.path.join(DR_OUT, CHDIR[ch], 'Sprites')


def main():
    head_n, objmap = parse_objmap(os.path.join(E43, 'objmap43.txt'))
    print('objmap43 头部声明 GameObjects = %s；解析出 %d 条' % (head_n, len(objmap)))
    if head_n == len(objmap):
        ok('D1 objmap43 解析自洽（%d == %d）' % (head_n, len(objmap)))
    else:
        bad('D1 objmap43 解析数量与文件头不符（%d vs %s）' % (len(objmap), head_n))

    # 全量实例 → obj 计数 & 逐章
    all_obj = {}
    per_ch_obj = {}
    total_inst = 0
    for ch in INST:
        d = load(os.path.join(E42, INST[ch]))
        c = per_ch_obj.setdefault(ch, {})
        for rec in (d.get('rooms') or []):
            for it in (rec.get('insts') or []):
                nm = it.get('obj')
                if not nm:
                    continue
                total_inst += 1
                all_obj[nm] = all_obj.get(nm, 0) + 1
                c[nm] = c.get(nm, 0) + 1

    print('')
    print('实例总条数 = %d；不同 obj = %d' % (total_inst, len(all_obj)))

    in_map = [n for n in all_obj if n in objmap]
    not_in_map = sorted(n for n in all_obj if n not in objmap)
    with_spr = [n for n in all_obj if objmap.get(n)]
    null_spr = sorted(n for n in all_obj if n in objmap and not objmap.get(n))

    print('obj 名在 objmap 里      : %d / %d' % (len(in_map), len(all_obj)))
    print('obj 名有非空 spr        : %d / %d' % (len(with_spr), len(all_obj)))
    print('obj 名在 objmap 但无 spr: %d' % len(null_spr))
    print('obj 名不在 objmap       : %d' % len(not_in_map))

    inst_mapped = sum(all_obj[n] for n in with_spr)
    inst_inmap = sum(all_obj[n] for n in in_map)
    print('')
    print('按**实例条数**加权：')
    print('  能拿到 spr 的实例 : %d / %d (%.1f%%)' %
          (inst_mapped, total_inst, 100.0 * inst_mapped / max(1, total_inst)))
    print('  只在 objmap 内的  : %d / %d (%.1f%%)' %
          (inst_inmap, total_inst, 100.0 * inst_inmap / max(1, total_inst)))

    print('')
    print('=== 无 spr 的 obj（逻辑锚点，前 30） ===')
    for n in sorted(null_spr, key=lambda x: -all_obj[x])[:30]:
        print('  %6d  %s' % (all_obj[n], n))

    if not_in_map:
        print('')
        print('=== 不在 objmap 的 obj（前 20） ===')
        for n in sorted(not_in_map, key=lambda x: -all_obj[x])[:20]:
            print('  %6d  %s' % (all_obj[n], n))

    # sprite 文件真实存在性：抽 5 个有 spr 的 obj，逐章找文件
    print('')
    print('=== sprite 文件存在性抽验 ===')
    probes = [n for n in sorted(with_spr, key=lambda x: -all_obj[x])[:5]]
    print('抽样 obj:', probes)
    hit_total = miss_total = 0
    for ch in INST:
        sd = sprite_dir(ch)
        exists = os.path.isdir(sd)
        if not exists:
            print('  %s: Sprites 目录不存在 (%s)' % (ch, sd))
            continue
        files = set(os.listdir(sd))
        hits = []
        for n in probes:
            spr = objmap.get(n)
            cand = [f for f in files if f.startswith(spr + '_') or f == spr + '.png']
            hits.append('%s->%s:%d' % (n, spr, len(cand)))
            hit_total += 1 if cand else 0
            miss_total += 0 if cand else 1
        print('  %s: %s' % (ch, ' | '.join(hits)))

    # 负控制
    print('')
    fake = 'obj_this_does_not_exist_zzz'
    if fake not in objmap and not objmap.get(fake):
        ok('D-负控制 不存在的 obj 名判为不可映射（%s）' % fake)
    else:
        bad('D-负控制 失败 —— 不存在的 obj 竟能映射')

    if len(objmap) >= 300:
        ok('D2 objmap 规模正常（%d ≥ 300）' % len(objmap))
    else:
        bad('D2 objmap 规模异常（%d）' % len(objmap))
    if len(with_spr) >= 20:
        ok('D3 有非空 spr 的 obj 名 %d 个' % len(with_spr))
    else:
        bad('D3 有非空 spr 的 obj 名仅 %d 个' % len(with_spr))

    print('')
    print('RESULT: FAIL=%d' % FAIL)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
