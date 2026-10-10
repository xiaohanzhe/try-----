# -*- coding: utf-8 -*-
u"""mutate104.py —— `check104` 的**变异测试**：把产品弄坏，看锁会不会报红。

为什么必须做：一条锁"全绿"有两种可能 ——
  ① 产品真的对；② 判据恒真（写错了、量错了东西、或根本没走到那条分支）。
只看绿是分不出 ①② 的。本脚本对每个"守点"造一次**保真**的破坏，
要求**指定判据由绿变红**；跑完立刻还原并**逐字节核验还原成功**。

本轮有**两类**破坏目标（这是与第103轮不同的地方）：
  · **数据/证据**（分片 JSON、`material104.json`）—— 改数据面；
  · **产品源码**（`scene_render.py` / `scene_canvas.py`）—— 本轮的核心价值在
    "把材质**画出来**"，只改数据是测不出渲染接线的。
    ⇒ 源码变异必须**先备份 + 逐字节核验还原**，否则一次失败就会把产品留在
       半坏状态（这里用 `shutil.copy2` + sha256 双边核对）。

铁律（第85~96轮反复踩过）：
  * 破坏必须**真的破坏**（改产品，不是改判据）；
  * 判据报红之后要**先怀疑判据**；
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
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
BAK = os.path.join(os.environ.get('TEMP') or '/tmp', 'bak104_mutate')
PY = sys.executable


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
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return json.load(f)


ZONE = [os.path.join(SCENES, f) for f in sorted(os.listdir(SCENES))
        if f.startswith('_zone.oneshot.')]
SRC = [os.path.join(MOD, 'scene_render.py'), os.path.join(MOD, 'scene_canvas.py')]
TARGETS = ZONE + SRC + [os.path.join(EV, 'material104.json')]

os.makedirs(BAK, exist_ok=True)
orig = {}
for p in TARGETS:
    b = os.path.join(BAK, os.path.basename(p).replace(os.sep, '_'))
    shutil.copy2(p, b)
    orig[p] = sha(p)
print('备份 %d 个文件 -> %s' % (len(TARGETS), BAK))


def run_check():
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    pr = subprocess.run([PY, os.path.join(HERE, 'check104.py')], env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = pr.stdout.decode('utf-8', 'replace')
    fails = re.findall(r'^\[FAIL\] (\S+)', out, re.M)
    return pr.returncode, fails


def restore():
    bad = []
    for p in TARGETS:
        b = os.path.join(BAK, os.path.basename(p).replace(os.sep, '_'))
        shutil.copy2(b, p)
        if sha(p) != orig[p]:
            bad.append(p)
    return bad


def _obj_with(key, idx=0):
    u"""在分片里找第 idx 个**带 `key` 键**的物件，返回 (路径, 物件, 它的紧凑串)。"""
    n = 0
    for f in sorted(os.listdir(SCENES)):
        if not f.startswith('_zone.oneshot.'):
            continue
        p = os.path.join(SCENES, f)
        d = jload(p)
        for sid, ent in (d.get('scenes') or {}).items():
            if not isinstance(ent, dict):
                continue
            for o in (ent.get('objects') or []):
                if key in o:
                    if n == idx:
                        return p, o, json.dumps(o, ensure_ascii=False,
                                                separators=(',', ':'))
                    n += 1
    return None, None, None


def _clean_obj():
    u"""找一个**没有任何材质键**的物件（用来测"干净条数"那条负控制）。"""
    for f in sorted(os.listdir(SCENES)):
        if not f.startswith('_zone.oneshot.'):
            continue
        p = os.path.join(SCENES, f)
        d = jload(p)
        for sid, ent in (d.get('scenes') or {}).items():
            if not isinstance(ent, dict):
                continue
            for o in (ent.get('objects') or []):
                if 'alpha' not in o and 'blend' not in o:
                    return p, o, json.dumps(o, ensure_ascii=False,
                                            separators=(',', ':'))
    return None, None, None


def _replace_obj(path, old, new):
    t = read_raw(path)
    assert t.count(old) >= 1, u'锚点不在文件里：%s' % old[:80]
    write_raw(path, t.replace(old, new, 1))


def _edit_src(path, old, new):
    u"""源码变异：**锚点按 LF 写，落地时还原 CRLF**。

    ★ 本项目这两个模块是**纯 CRLF**（实测 `bareLF == 0`）⇒ 直接用含 `\\n` 的锚点
      **匹配不到**（记忆里的老坑：「CRLF 锚点必先 `_lf()`」）。这里在 LF 空间里
      匹配与替换，写回时若原文件是 CRLF 就整体还原 —— 保证**除了那一处改动，
      字节完全不变**（还原核验用的是 sha256，掺进 EOL 变化会立刻暴露）。
    """
    t = read_raw(path)
    crlf = t.count('\r\n') > 0 and (t.count('\n') - t.count('\r\n')) == 0
    tt = t.replace('\r\n', '\n')
    assert old in tt, u'%s 找不到锚点：%s' % (os.path.basename(path), old[:80])
    tt = tt.replace(old, new, 1)
    if crlf:
        tt = tt.replace('\n', '\r\n')
    write_raw(path, tt)


# ---------------------------------------------------------------- M1 删 alpha 键
def m1():
    p, o, s = _obj_with('alpha')
    d = {k: v for k, v in o.items() if k != 'alpha'}
    _replace_obj(p, s, json.dumps(d, ensure_ascii=False, separators=(',', ':')))
    return 'A2', u'把一个物件的 `alpha` 键删掉（带 alpha 的计数 34→33 必须被抓到）'


# ---------------------------------------------------------------- M2 alpha 非 n/255
def m2():
    p, o, s = _obj_with('alpha')
    d = dict(o)
    d['alpha'] = 0.5                      # 127.5/255 ⇒ 不是整数份
    _replace_obj(p, s, json.dumps(d, ensure_ascii=False, separators=(',', ':')))
    return 'A5', u'把一个 `alpha` 从 `n/255` 改成 **0.5**（"必须来自原作 opacity"必须抓到）'


# ---------------------------------------------------------------- M3 blend=2
def m3():
    p, o, s = _obj_with('blend')
    d = dict(o)
    d['blend'] = 2                        # 减色：本轮明确不做
    _replace_obj(p, s, json.dumps(d, ensure_ascii=False, separators=(',', ':')))
    return 'A6', u'把一个物件的 `blend` 改成 **2**（减色，本轮不做 ⇒ 值域判据必须抓到）'


# ---------------------------------------------------------------- M4 干净物件被污染
def m4():
    p, o, s = _clean_obj()
    d = dict(o)
    d['alpha'] = 1.0                      # 信息量为零，但**不该写**
    _replace_obj(p, s, json.dumps(d, ensure_ascii=False, separators=(',', ':')))
    return 'A8', (u'给一个 `opacity==255` 的干净物件加上 `alpha: 1.0`'
                  u'（正负成对那条必须抓到"干净条数掉了 1"）')


# ---------------------------------------------------------------- M5 篡改证据
def m5():
    p = os.path.join(EV, 'material104.json')
    t = read_raw(p)
    old = '"blend1": 389'
    assert old in t, u'证据里找不到 %s' % old
    write_raw(p, t.replace(old, '"blend1": 388', 1))
    return 'A10', u'把 `material104.json` 的 `counts.blend1` 篡改成 388（对账必须抓到）'


# ---------------------------------------------------------------- M6 删渲染层透传
def m6():
    p = os.path.join(MOD, 'scene_render.py')
    old = "        if blend:\n            item['blend'] = blend\n"
    _edit_src(p, old, '')
    return 'B1', (u'把 `scene_render` 的 `item["blend"]` 透传**删掉**'
                  u'（"材质真的进了绘制指令"必须抓到）')


# ---------------------------------------------------------------- M7 合成模式换掉
def m7():
    p = os.path.join(MOD, 'scene_canvas.py')
    old = 'fn(QPainter.CompositionMode_Plus if on'
    _edit_src(p, old, 'fn(QPainter.CompositionMode_SourceOver if on')
    return 'B3', (u'把加色合成换成 `SourceOver`（"加色像素 == RMXP 公式、'
                  u'且与 SourceOver 可分"必须抓到）')


# ---------------------------------------------------------------- M8 不还原合成模式
def m8():
    p = os.path.join(MOD, 'scene_canvas.py')
    old = '            _set_plus(painter, False)\n'
    _edit_src(p, old, '')
    return 'B4', (u'把画完后的**还原**删掉（"合成模式必须还原"必须抓到 —— '
                  u'否则加色会污染它之后的所有物件）')


CASES = [('M1', m1), ('M2', m2), ('M3', m3), ('M4', m4),
         ('M5', m5), ('M6', m6), ('M7', m7), ('M8', m8)]

ok_all = True
print()
print('=' * 96)
print(u'变异测试（每个变异：破坏 → 跑锁 → 要求**指定判据报红** → 还原 → 逐字节核验）')
print('=' * 96)
rc0, f0 = run_check()
print(u'变异前基线：exit=%d FAIL=%s' % (rc0, f0[:3] or u'(无)'))
if rc0 != 0 or f0:
    print(u'⚠️ 基线就是红的 —— 先修基线，别拿红基线做变异测试')
    sys.exit(1)

for name, fn in CASES:
    where, desc = fn()
    rc, fails = run_check()
    hit = any(f.startswith(where) for f in fails)
    print(u'%-4s %s' % (name, desc))
    print(u'     期望判据 %-4s 报红 -> %s ｜ 实际红：%s'
          % (where, hit, fails[:6] or u'(无)'))
    if not hit:
        ok_all = False
    bad = restore()
    if bad:
        print(u'     ❌ 还原失败：%s' % bad)
        ok_all = False
    else:
        rc2, f2 = run_check()
        print(u'     还原后锁：exit=%d FAIL=%s' % (rc2, f2[:2] or u'(无)'))
        if f2:
            ok_all = False

print()
bad = restore()
if bad:
    print(u'❌ 最终还原核验失败：%s' % bad)
    sys.exit(1)
print(u'★ 终态：所有被改文件与备份**逐字节相同**（%d 个）' % len(TARGETS))
rc, fails = run_check()
print(u'★ 终态锁：exit=%d FAIL=%d' % (rc, len(fails)))
print()
if ok_all and rc == 0 and not fails:
    print(u'变异测试通过：%d 个变异**全部**被对应判据抓到，锁有鉴别力' % len(CASES))
    sys.exit(0)
print(u'变异测试未通过（见上）')
sys.exit(1)
