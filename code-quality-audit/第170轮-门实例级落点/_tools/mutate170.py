# -*- coding: utf-8 -*-
u"""第170轮：**变异测试** —— 证明 `check170.py` 的判据不是恒真。

原则（历轮教训）
---------------
  · 每个变异都必须**真的让某条判据变红**；报绿＝判据没用，要改判据不是改变异；
  · 变异要**贴着被测机制**（改数据 → 数据判据红；改代码 → 行为判据红）；
  · 一次只破坏一处，且**只破坏一处**（多道同拆才复现 ⇒ 说明判据互相兜着，等于没测）。

变异清单
--------
  M1 把一条已修好的 `x_range` **改回反向**      → B2 必红
  M2 抹掉一条规则已补的 `entrance`               → B1 必红
  M3 删掉一条本轮新增规则                        → A1 必红
  M4 把 `town_mid` 一条规则的 `door_x` 改错      → C3 必红（可认领的门少一个）
  M5 `_pick_by_pos` 放宽成"命中多条就取第一条"   → C4 必红
  M6 `route_for_door` 把 `pos` 丢掉              → C7 必红（等于本轮白做）
  M7 把一条 y 轴规则的 `axis` 改成 `x`           → C3 必红（上下门被当左右门）

★ 变异包落在 `MUT170_ROOT`（默认 `D:\_tmp\mut170`），**不写进工作区** ——
  免得 `git add -A` 把它们当删除/新增记进去（历轮踩过）。跑完自动清理。
"""
import io
import json
import os
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
CHECK = os.path.join(HERE, 'check170.py')
WORK = os.environ.get('MUT170_ROOT') or r'D:\_tmp\mut170'
PY = sys.executable


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def jdump(obj, p):
    io.open(p, 'wb').write(json.dumps(obj, ensure_ascii=False, indent=2)
                           .replace('\n', '\r\n').encode('utf-8'))


def run_check(env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    q = subprocess.run([PY, CHECK], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL)
    out = q.stdout.decode('utf-8', 'replace')
    fails = [ln for ln in out.splitlines() if ln.startswith('[FAIL]')]
    codes = []
    for ln in fails:
        rest = ln[len('[FAIL] '):].strip()
        codes.append(rest.split(u' ')[0].split(u'★')[0].strip())
    return q.returncode, codes, out


def make_pkg_copy(dst):
    u"""只拷 `modules/` + `assets/scenes/*.json` —— 判据只读这两处，别把 100MB 贴图搬来。"""
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(PKG, 'modules'), os.path.join(dst, 'modules'))
    sc = os.path.join(dst, 'assets', 'scenes')
    os.makedirs(sc)
    for f in os.listdir(SCENES):
        if f.endswith('.json'):
            shutil.copy2(os.path.join(SCENES, f), os.path.join(sc, f))


def main():
    base_code, base_fails, _ = run_check({})
    print(u'== 基线 ==')
    print(u'   exit=%d  FAIL 行=%d' % (base_code, len(base_fails)))
    if base_code != 0 or base_fails:
        print(u'[FATAL] 基线不是全绿，变异测试没有意义。先让 check170 全过。')
        return 2

    root = WORK
    if os.path.isdir(root):
        shutil.rmtree(root)
    os.makedirs(root)
    rows = []
    try:
        # ---------------- 数据类变异（用真包 + 副本表）----------------
        base = jl(ROUTES)

        def data_mut(tag, fn, expect):
            d = json.loads(json.dumps(base))
            hit = fn(d)
            p = os.path.join(root, 'routes_%s.json' % tag)
            jdump(d, p)
            code, codes, out = run_check({'CQ_ROUTES170': p})
            rows.append({'id': tag, 'expect': expect, 'got': codes,
                         'red': code != 0, 'hit': hit,
                         'pass': code != 0 and expect in codes})
            print(u'  %-18s 变异点=%-46r 红=%s 命中=%s'
                  % (tag, hit, u'是' if code != 0 else u'否',
                     expect in codes))

        W = [r for r in base['routes']
             if (r.get('_original') or {}).get('via') in ('obj_doorW', 'obj_doorw_musfade')]

        def m1(d):
            for r in d['routes']:
                o = r.get('_original') or {}
                if o.get('batch') == 169 and o.get('x_range') == [None, 10]:
                    o['x_range'] = [10, None]
                    return (r.get('priority'), u'x_range [None,10] -> [10,None]')
            return None

        def m2(d):
            for r in d['routes']:
                o = r.get('_original') or {}
                if o.get('batch') == 169 and isinstance(o.get('entrance'), int):
                    old = o['entrance']
                    o['entrance'] = None
                    return (r.get('priority'), u'entrance %r -> None' % old)
            return None

        def m3(d):
            for i, r in enumerate(d['routes']):
                if (r.get('_original') or {}).get('batch') == 170:
                    d['routes'].pop(i)
                    return (r.get('priority'), u'删掉这条新增规则')
            return None

        def m4(d):
            for r in d['routes']:
                if r.get('when_scene') == 'ch2.hometown.town_mid' and r.get('priority') == 7092:
                    old = r['_original'].get('door_x')
                    r['_original']['door_x'] = 999
                    return (r.get('priority'), u'door_x %r -> 999' % old)
            return None

        print()
        print(u'== 数据类变异 ==')
        data_mut('M1_range_flip_back', m1, 'B2')
        data_mut('M2_drop_entrance', m2, 'B1')
        data_mut('M3_drop_new_rule', m3, 'A1')
        data_mut('M4_wrong_door_x', m4, 'C7')

        # ---------------- 代码类变异（副本包 + 改源码）----------------
        print()
        print(u'== 代码类变异 ==')

        def code_mut(tag, old, new, expect):
            dst = os.path.join(root, 'pkg_%s' % tag)
            make_pkg_copy(dst)
            f = os.path.join(dst, 'modules', 'item_interact.py')
            raw = io.open(f, 'rb').read()
            txt = raw.decode('utf-8')
            #: ★ 产品文件是 **CRLF**，而锚点我按 `\n` 写（多行字符串里没法自然带 `\r`）。
            #:   直接在原串上 `count` 会恒为 0（第一版 M5 就这么被"跳过"了）。
            #:   做法：归一成 LF 再比，替换完把 EOL 还原回去 —— **保持原 EOL** 是硬要求。
            crlf = '\r\n' in txt
            norm = txt.replace('\r\n', '\n')
            if norm.count(old) != 1:
                rows.append({'id': tag, 'expect': expect, 'got': [],
                             'red': False, 'hit': u'锚点命中 %d 次' % norm.count(old),
                             'pass': False})
                print(u'  %-18s ★锚点命中 %d 次，跳过' % (tag, norm.count(old)))
                return
            out_txt = norm.replace(old, new)
            if crlf:
                out_txt = out_txt.replace('\n', '\r\n')
            io.open(f, 'wb').write(out_txt.encode('utf-8'))
            code, codes, out = run_check({'CQ_PKG170': dst})
            rows.append({'id': tag, 'expect': expect, 'got': codes,
                         'red': code != 0, 'hit': old.splitlines()[0][:44],
                         'pass': code != 0 and expect in codes})
            print(u'  %-18s 红=%s 命中=%s  红项=%r'
                  % (tag, u'是' if code != 0 else u'否', expect in codes, codes[:6]))

        # M5：放宽"恰好命中 1 条"这道闸
        code_mut('M5_lax_pick',
                 u'    if len(hits) != 1:\n        return None\n    return hits[0].get(\'to\')',
                 u'    if not hits:\n        return None\n    return hits[0].get(\'to\')',
                 'C4')

        # M6：把 pos 丢掉（等于本轮白做）
        code_mut('M6_drop_pos',
                 u'    got = _pick_by_pos(items, scene_id, _letter_ok, pos)',
                 u'    got = _pick_by_pos(items, scene_id, _letter_ok, None)',
                 'C3')

        # M7：y 轴规则当 x 轴用
        dst = os.path.join(root, 'pkg_M7_axis')
        make_pkg_copy(dst)
        rp = os.path.join(dst, 'assets', 'scenes', '_routes.json')
        dd = jl(rp)
        hit = None
        for r in dd['routes']:
            o = r.get('_original') or {}
            if o.get('axis') == 'y':
                o['axis'] = 'x'
                hit = (r.get('priority'), o.get('door_x'), o.get('door_y'))
                break
        jdump(dd, rp)
        code, codes, out = run_check({'CQ_PKG170': dst})
        rows.append({'id': 'M7_axis_y_as_x', 'expect': 'C3', 'got': codes,
                     'red': code != 0, 'hit': hit,
                     'pass': code != 0 and 'C3' in codes})
        print(u'  %-18s 变异点=%r 红=%s 命中=%s  红项=%r'
              % ('M7_axis_y_as_x', hit, u'是' if code != 0 else u'否',
                 'C3' in codes, codes[:6]))
    finally:
        pass

    print()
    n_ok = sum(1 for r in rows if r['pass'])
    print(u'== 结论：%d/%d 个变异被对应判据抓住 ==' % (n_ok, len(rows)))
    for r in rows:
        if not r['pass']:
            print(u'  ✗ %-18s 期望 %s，实际红项=%r' % (r['id'], r['expect'], r['got'][:8]))
    report = os.path.join(ROUND, '_evidence', 'mutate170.json')
    io.open(report, 'wb').write(json.dumps({'rows': rows, 'ok': n_ok,
                                            'total': len(rows)},
                                           ensure_ascii=False, indent=1)
                                .replace('\n', '\r\n').encode('utf-8'))
    print(u'落盘 %s' % report)
    try:
        shutil.rmtree(WORK)
    except OSError as e:
        print(u'（清理 %s 失败：%r —— 不影响结论）' % (WORK, e))
    return 0 if n_ok == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
