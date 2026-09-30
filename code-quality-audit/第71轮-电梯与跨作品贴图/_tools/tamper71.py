# -*- coding: utf-8 -*-
"""第71轮 · 鉴别力体检：**真的把破坏写进 `_link.json`**，看 check71 会不会报红。

为什么不能只用 check71 里的"内存负控制"
----------------------------------------
`check71` 的 G4n 是把 `_sh` 复制一份改字段，证明**内核函数**有鉴别力。
但那只证明"函数写对了"——**没有**证明"真文件被人改坏时，判据会亮"。
本项目铁律：**改断言/护栏 → 鉴别力体检必须改文件**（`A in rev[B]` 那类恒真判据
就是这么抓出来的）。所以这里对着**磁盘上的真文件**动手。

四种破坏（每种一条独立判据，互不代偿）
--------------------------------------
    T1 height_px +1        -> G4（几何自洽）必须报红
    T2 room_resource 改一字 -> G2/G3（落点两处对不上）必须报红
    T3 parts_cover 删一件   -> G6（零件覆盖）必须报红
    T4 wiring.status 改口   -> G8（诚实判据）必须报红

纪律：**每一步都恢复原状**；跑完再复检一次必须回到 0 FAIL。
落盘：`_evidence/tamper71_report.json`。
"""
from __future__ import print_function

import io
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
AUD = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LINK = os.path.join(ROOT, 'ralsei_pet', 'assets', 'elevator', '_link.json')
CHECK71 = os.path.join(HERE, 'check71.py')
PY = r'C:\Python311\python.exe'
EV = os.path.join(AUD, '_evidence')

#: (标签, 期望报红的判据前缀, 破坏函数)
CASES = []


def case(tag, expect, fn):
    CASES.append((tag, expect, fn))


def _t1(d):
    d['shaft']['height_px'] = float(d['shaft']['height_px']) + 1.0
    return 'height_px +1（几何不再自洽）'


def _t2(d):
    d['endpoints']['lower']['room_resource'] = 'room_area1_X71'
    return 'room_resource 改一字（与 _source.json / bigmap66 都对不上）'


def _t3(d):
    d['parts_cover']['cabin'].remove('spr_elevatorpanel')
    return 'parts_cover 删一件（15 件不再全覆盖）'


def _t4(d):
    d['wiring']['status'] = 'wired'
    return 'wiring.status 改成 wired（谎称已接线）'


case('T1', 'G4', _t1)
case('T2', 'G2', _t2)
case('T3', 'G6', _t3)
case('T4', 'G8', _t4)


def run_check():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([PY, CHECK71], capture_output=True, cwd=ROOT, env=env,
                       timeout=300)
    out = (p.stdout or b'').decode('utf-8', 'replace')
    fails = [ln.strip() for ln in out.splitlines() if ln.strip().startswith('[FAIL]')]
    return p.returncode, fails, out


def fail_names(fails):
    """从 `[FAIL] G4 井道几何…` 里取判据名（第 1 个空格前的 token）。

    ★ 必须**精确等于**期望名：`expect='G4'` 若用 `startswith` 会把 `G4n` 也算命中，
      那 T1 就可能在"G4n 报红、G4 其实没红"的假象下通过。
    """
    return [f.split(']', 1)[-1].strip().split(' ')[0] for f in fails]


def main():
    original = io.open(LINK, encoding='utf-8').read()
    report = {'round': 71, 'target': 'ralsei_pet/assets/elevator/_link.json',
              'why': '鉴别力体检必须改文件（内存负控制只证明"函数写对了"）',
              'cases': []}

    rc0, f0, _ = run_check()
    print('基线：rc=%d FAIL=%d' % (rc0, len(f0)))
    report['baseline'] = {'rc': rc0, 'fails': f0}

    ok_all = (rc0 == 0 and not f0)
    for tag, expect, fn in CASES:
        d = json.loads(original)
        what = fn(d)
        with io.open(LINK, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(d, ensure_ascii=False, indent=1))
        rc, fails, _ = run_check()
        names = fail_names(fails)
        hit = [f for f, n in zip(fails, names) if n == expect]
        good = bool(hit)
        ok_all = ok_all and good
        print('  %s %-42s -> rc=%d 报红=%s  %s'
              % (tag, what[:42], rc, ('是' if hit else '否'),
                 ('OK' if good else '!! 未报红')))
        if hit:
            print('       %s' % hit[0][:110])
        report['cases'].append({'tag': tag, 'tamper': what, 'expect': expect,
                                'rc': rc, 'detected': good,
                                'fail_line': hit[0][:200] if hit else None})
        # 立刻恢复
        with io.open(LINK, 'w', encoding='utf-8') as fh:
            fh.write(original)

    rc_f, f_f, _ = run_check()
    print('恢复后：rc=%d FAIL=%d' % (rc_f, len(f_f)))
    report['after_restore'] = {'rc': rc_f, 'fails': f_f,
                               'file_identical': io.open(LINK, encoding='utf-8').read()
                               == original}
    ok_all = ok_all and rc_f == 0 and not f_f and report['after_restore']['file_identical']
    report['verdict'] = 'ALL_DETECTED' if ok_all else 'SOMETHING_WRONG'
    print('== 结论 = %s ==' % report['verdict'])

    if not os.path.isdir(EV):
        os.makedirs(EV)
    dst = os.path.join(EV, 'tamper71_report.json')
    with io.open(dst, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=1))
    print('-> %s' % dst)
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
