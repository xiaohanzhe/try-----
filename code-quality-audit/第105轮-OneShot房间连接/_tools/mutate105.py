# -*- coding: utf-8 -*-
"""mutate105.py —— `check105` 的**变异测试**：把产品/证据弄坏，看锁会不会报红。

为什么必须做：一条锁"全绿"有两种可能 ——
  ① 产品真的对；② 判据恒真（写错了、量错了东西、或根本没走到那条分支）。
只看绿是分不出 ①② 的。本脚本对每个"守点"造一次**保真**的破坏，
要求**指定判据由绿变红**；跑完立刻还原并**逐字节核验还原成功**。

本轮两类破坏目标：
  · **产品路由表** `ralsei_pet/assets/scenes/_routes.json` —— 改数据面；
  · **原作事实蒸馏** `_evidence/oneshot_transfers.json` —— 改证据面。
  两类都要覆盖：B 段（产品 == 证据）只在**两边不一致**时才红，
  只改一边就够；但"证据自己坏了"要由 A 段抓 —— 所以 M6 专门改证据。

铁律（第85~96轮反复踩过）：
  * 破坏必须**真的破坏**（改产品，不是改判据）；
  * 判据报红之后要**先怀疑判据**（本脚本每条都打印"期望哪条判据红"）；
  * 还原要**逐字节**核对哈希，不是"我改回来了"。
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
EVID = os.path.join(ROUND, '_evidence', 'oneshot_transfers.json')
BAK = os.path.join(os.environ.get('TEMP') or '/tmp', 'bak105_mutate')
PY = sys.executable
TARGETS = [ROUTES, EVID]


def sha(p):
    with open(p, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_raw(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_raw(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def jload(p):
    return json.loads(read_raw(p))


def save_json(p, obj):
    """按 `_routes.json` 既有形态写回（2 空格缩进 + CRLF + 无尾换行）。"""
    write_raw(p, json.dumps(obj, ensure_ascii=False, indent=2).replace('\n', '\r\n'))


os.makedirs(BAK, exist_ok=True)
_orig = {}
for _p in TARGETS:
    _b = os.path.join(BAK, os.path.basename(_p))
    shutil.copy2(_p, _b)
    _orig[_p] = sha(_p)
print('备份 %d 个文件 -> %s' % (len(TARGETS), BAK))


def run_check():
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    pr = subprocess.run([PY, os.path.join(HERE, 'check105.py')], env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = pr.stdout.decode('utf-8', 'replace')
    fails = re.findall(r'^\[FAIL\] (\S+)', out, re.M)
    return pr.returncode, fails


def restore():
    bad = []
    for p in TARGETS:
        shutil.copy2(os.path.join(BAK, os.path.basename(p)), p)
        if sha(p) != _orig[p]:
            bad.append(p)
    return bad


def _oneshot(d):
    return [r for r in d['routes']
            if str((r or {}).get('when_scene') or '').startswith('oneshot')]


def _multi_src(d):
    """找一个"同场景 >= 2 条 oneshot 规则"的 scene_id（C2/C3 的样本）。"""
    cnt = {}
    for r in _oneshot(d):
        cnt[r['when_scene']] = cnt.get(r['when_scene'], 0) + 1
    return sorted([k for k, v in cnt.items() if v >= 2])[0]


# --------------------------------------------------------------- M1 删一条边
def m1():
    d = jload(ROUTES)
    osr = _oneshot(d)
    victim = sorted(r['to'] for r in osr)[0]
    d['routes'] = [r for r in d['routes'] if not (
        str(r.get('when_scene', '')).startswith('oneshot') and r.get('to') == victim)]
    save_json(ROUTES, d)
    return 'B1', '删掉一条 oneshot 规则（产品边集合必须不再等于证据集合）'


# ------------------------------------------------- M2 同场景 when_door 撞名
def m2():
    d = jload(ROUTES)
    sid = _multi_src(d)
    rows = [r for r in _oneshot(d) if r['when_scene'] == sid]
    rows.sort(key=lambda r: r['priority'])
    rows[1]['when_door'] = rows[0]['when_door']
    save_json(ROUTES, d)
    return 'C2', '把 %s 的第二条出口的 when_door 改成与第一条同名（场景内必须唯一）' % sid


# --------------------------------------------- M3 priority 与门名反序
def m3():
    d = jload(ROUTES)
    sid = _multi_src(d)
    rows = [r for r in _oneshot(d) if r['when_scene'] == sid]
    rows.sort(key=lambda r: r['priority'])
    p0, p1 = rows[0]['priority'], rows[1]['priority']
    rows[0]['priority'], rows[1]['priority'] = p1, p0
    save_json(ROUTES, d)
    return 'C3', '把 %s 前两条出口的 priority 互换（门名序 != priority 序）' % sid


# ------------------------------------------------- M4 篡改既有段（D 指纹）
def m4():
    d = jload(ROUTES)
    old = [r for r in d['routes']
           if not str(r.get('when_scene', '')).startswith('oneshot')]
    old[0]['reason'] = (old[0].get('reason') or '') + '（第105轮变异测试）'
    save_json(ROUTES, d)
    return 'D2', '改掉一条**既有**（Deltarune）规则的 reason（既有段指纹必须变）'


# ------------------------------------------- M5 kind 被改坏（B3）
def m5():
    d = jload(ROUTES)
    _oneshot(d)[0]['_original']['kind'] = 'desktop_portal'
    save_json(ROUTES, d)
    return 'B3', '把一条 oneshot 规则的 _original.kind 改成 desktop_portal'


# ------------------------------------------------- M6 证据里删一条边
def m6():
    e = jload(EVID)
    e['edges'] = e['edges'][1:]
    save_json(EVID, e)
    return 'A2c', '从证据里删掉一条边（unique_edges 计数必须与实测条数不符）'


# ------------------------------------------- M7 目标指向未登记场景
def m7():
    d = jload(ROUTES)
    _oneshot(d)[0]['to'] = 'oneshot.__no_such_scene__'
    save_json(ROUTES, d)
    return 'B5', '把一条 oneshot 规则的 to 改成不存在的场景（孤儿目标必须被抓）'


# ------------------------------------------- M8 伪造一条多出来的边
def m8():
    d = jload(ROUTES)
    src = sorted(r['when_scene'] for r in _oneshot(d))[0]
    tgt = sorted(r['to'] for r in _oneshot(d))[-1]
    d['routes'].append({
        'to': tgt, 'priority': 3999, 'reason': '变异测试伪造的边',
        'when_scene': src, 'when_door': 'zzz_forged',
        '_original': {'chapter': 'oneshot', 'kind': 'oneshot_transfer',
                      'src_map': 1, 'dst_map': 2,
                      'src_room_name': 'x', 'dst_room_name': 'y',
                      'event': 'zzz_forged', 'event_xy': [0, 0],
                      'graphic': '', 'n_events': 1},
    })
    save_json(ROUTES, d)
    return 'B1', '伪造一条产品里多出来的 oneshot 边（"恰好相等"必须抓）'


# ------------------------------------------- M9 自环混进产品
def m9():
    d = jload(ROUTES)
    r = _oneshot(d)[0]
    d['routes'].append({
        'to': r['when_scene'], 'priority': 3998, 'reason': '变异测试：切到自己',
        'when_scene': r['when_scene'], 'when_door': 'zzz_self',
        '_original': {'chapter': 'oneshot', 'kind': 'oneshot_transfer',
                      'src_map': 1, 'dst_map': 1,
                      'src_room_name': 'x', 'dst_room_name': 'x',
                      'event': 'zzz_self', 'event_xy': [0, 0],
                      'graphic': '', 'n_events': 1},
    })
    save_json(ROUTES, d)
    return 'E1b', '把一条"切到自己"的自环塞进产品（自环必须只登记不生成）'


MUTS = [m1, m2, m3, m4, m5, m6, m7, m8, m9]

rc0, f0 = run_check()
print('基线（未变异）：rc=%d FAIL=%s' % (rc0, f0 or '无'))
if rc0 != 0 or f0:
    print('!! 基线本身不是全绿 —— 先修产品/锁，再谈变异测试')
    restore()
    raise SystemExit(2)

bad = 0
for fn in MUTS:
    want, desc = fn()
    rc, fails = run_check()
    hit = any(f.startswith(want) for f in fails)
    ok = (rc != 0) and hit
    print('[%s] %s → 期望判据 %s 报红；实得 rc=%d FAIL=%s'
          % ('OK' if ok else 'MISS', desc, want, rc, fails or '无'))
    bad += 0 if ok else 1
    back = restore()
    if back:
        print('!! 还原失败：%s' % back)
        raise SystemExit(3)

print()
print('变异测试：%d/%d 命中' % (len(MUTS) - bad, len(MUTS)))
print('全部文件已还原并逐字节核验：%s'
      % ('OK' if all(sha(p) == _orig[p] for p in TARGETS) else 'FAIL'))
raise SystemExit(1 if bad else 0)
