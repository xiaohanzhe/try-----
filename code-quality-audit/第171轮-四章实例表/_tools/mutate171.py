# -*- coding: utf-8 -*-
"""第171轮 · 变异测试：证明 `check171` 的判据**真的有鉴别力**。

★★ 第一版的做法（拷整个 `ralsei_pet` 到 `D:\\_tmp`）被**清理守卫**拦了：
   1714 个文件一次 `rmtree`，超过 50 的阈值 ⇒ 报 SAFE_DELETE_BULK_CONFIRM_REQUIRED。
   改成只拷**一个文件**：`_routes.json`（本轮所有变异都是**数据面**的），
   产品代码仍用真包（不设 `CQ_PKG171`）；只有 M9 需要拷证据目录（13 个 json，不含 gml）。

★ 变异一律改 **JSON 对象**，不写字符串锚点 ⇒ 天然绕开 `core.autocrlf`
  那个"锚点命中 0 次"的坑（第164/170轮踩过两次）。
用法: python mutate171.py
"""
import collections
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
CHECK = os.path.join(HERE, 'check171.py')
EV = os.path.join(ROUND, '_evidence')
ROUTES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')
PY = sys.executable
WORK = os.environ.get('MUT171_ROOT', r'D:\_tmp\mut171run')


def load(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def dump(p, d):
    with io.open(p, 'w', encoding='utf-8') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
        fh.write('\n')


def pick(d, prio):
    RL = d['routes'] if isinstance(d, dict) else d
    for r in RL:
        if r.get('priority') == prio:
            return r
    raise KeyError(prio)


def run_check(routes_p, ev):
    env = dict(os.environ)
    env.pop('CQ_PKG171', None)          # 产品代码用真包（变异只在数据面）
    env['CQ_EV171'] = ev
    env['CQ_ROUTES171'] = routes_p
    p = subprocess.run([PY, CHECK], env=env, capture_output=True)
    out = p.stdout.decode('utf-8', 'replace')
    fails = [ln[7:].split(u'    ')[0].strip() for ln in out.splitlines()
             if ln.startswith('[FAIL] ')]
    return p.returncode, fails, out


# ---------------------------------------------------------------- 变异体
def m1(d, ev):
    o = pick(d, 7200)['_original']
    o['door_x'] = (o['door_x'] or 0) + 7


def m2(d, ev):
    pick(d, 7200)['_original']['x_range'] = [0, 99999]


def m3(d, ev):
    RL = d['routes']
    RL[:] = [r for r in RL if r.get('priority') != 7200]


def m4(d, ev):
    pick(d, 7201)['_original']['marker'] = 'obj_markerzzz'


def m5(d, ev):
    pick(d, 7202)['_original']['branch_letter'] = 'A'


def m6(d, ev):
    o = pick(d, 7203)['_original']
    o['door_x_all'] = (o.get('door_x_all') or [None])[:1]


def m7(d, ev):
    o = pick(d, 7204)['_original']
    o['dst_room_id'] = (o['dst_room_id'] or 0) + 1


def m8(d, ev):
    pick(d, 7205)['when_door'] = 'X'


def m9(d, ev):
    u"""证据里抹掉一条 phantom 记录 —— 验证 E3/E4 不是恒真。"""
    p = os.path.join(ev, 'phantom171.json')
    d2 = load(p)
    d2['rows'] = d2['rows'][1:]
    d2['stat'] = dict(collections.Counter(x['kind'] for x in d2['rows']))
    dump(p, d2)


CASES = [
    (u'M1 改 door_x（+7）', u'B1', m1),
    (u'M2 区间放宽 0~99999', u'B3', m2),
    (u'M3 删一条新规则', u'A1', m3),
    (u'M4 marker 改成不存在', u'B4', m4),
    (u'M5 branch_letter 改错', u'B5', m5),
    (u'M6 door_x_all 少一个', u'B2', m6),
    (u'M7 dst_room_id 改错', u'C4', m7),
    (u'M8 when_door 改成 X', u'A1', m8),
    (u'M9 证据里抹一条 phantom', u'E3', m9),
]


def main():
    os.makedirs(WORK, exist_ok=True)
    base = load(ROUTES)
    ok = 0
    for i, (name, want, fn) in enumerate(CASES):
        d = json.loads(json.dumps(base))
        ev = EV
        if fn is m9:
            ev = os.path.join(WORK, 'ev_copy')
            if os.path.isdir(ev):
                shutil.rmtree(ev)
            shutil.copytree(EV, ev, ignore=shutil.ignore_patterns('gml', '*.pyc'))
        fn(d, ev)
        rp = os.path.join(WORK, 'routes_m%d.json' % (i + 1))
        dump(rp, d)
        rc, fails, out = run_check(rp, ev)
        hit = [f for f in fails if f.startswith(want)]
        flag = 'OK  ' if (rc != 0 and hit) else 'MISS'
        if rc != 0 and hit:
            ok += 1
        print('[%s] %-24s 期望红=%s  实际红 %d 条：%s' % (
            flag, name, want, len(fails),
            u' / '.join(f.split(u' ')[0] for f in fails[:5]) or u'（一条都没红）'))
        if rc == 0:
            print('        ★ 变异**没被抓到** ⇒ 判据有盲区')
        os.remove(rp)
        if ev != EV:
            shutil.rmtree(ev)
    print('')
    print('变异捕获 %d/%d' % (ok, len(CASES)))
    return 0 if ok == len(CASES) else 1


if __name__ == '__main__':
    sys.exit(main())
