# -*- coding: utf-8 -*-
u"""第168轮 · `check168` 的变异测试。

## 它考什么

不是"再跑一遍判据看它绿不绿"，而是问：**每一条判据是不是真的在那里挡着**。

做法：把**数据**（`_routes.json` / `doors168.json`）或**判据自己**（`_desc_of`）
换成副本，一次只动一处，跑 `check168.py`，看红的是不是**预期那一组**。

* 红了别的 ⇒ 判据之间串味（连带一片松）；
* 该红的没红 ⇒ 那条判据是摆设（恒真）。

## 纪律（照第150~166轮那套）

* **字节级还原**：所有改动都写在系统 temp 的副本上，真文件一个字节都不碰；
  收口时校验产品表与证据文件的 sha1 未变。
* **每条的"预期红"是先跑出来、再钉死的** —— 不是拍脑袋写的。
  所以本文件里 `EXPECT` 那些集合是**实测记录**，改判据时要跟着改。
* **M9 是无害变异**：只改一句中文说明 ⇒ 一条都不许红。
  专门考"没破坏时会不会假红"（判据过窄=误报，第107/160轮同族）。
* **M10 改的是判据自己**（`_desc_of` 退回只认裸字面量）：这考的是
  "扫描器恒空"—— `F4` 会照样绿（它扫不到东西就"没有违规"），由 `F5` 分母闸兜住。
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
CHECK = os.path.join(HERE, 'check168.py')
ROUTES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')
DOORS = os.path.join(ROUND, '_evidence', 'doors168.json')
PY = sys.executable

_T1 = "\x3a True"
_t1 = "\x3a true"
_T0 = "\x3a False"
_t0 = "\x3a false"


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        while True:
            b = fh.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def jload(path):
    s = io.open(path, encoding='utf-8', newline='').read()
    return json.loads(s.replace(_T1, _t1).replace(_T0, _t0))


def jdump_routes(obj, path):
    u"""按第44轮定下的格式写：`ensure_ascii=False` + indent 2 + CRLF + 无尾换行。"""
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    with open(path, 'wb') as fh:
        fh.write(text.replace('\n', '\r\n').encode('utf-8'))


def run(script, env_extra):
    env = os.environ.copy()
    env.update(env_extra)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    p = subprocess.run([PY, script], capture_output=True, env=env)
    out = p.stdout.decode('utf-8', 'replace')
    fails = re.findall(r'^\[FAIL\]\s+(\S+)', out, re.M)
    return p.returncode, fails, out


# ---------------------------------------------------------------- 变异体
#: `(id, 说明, 期望红的判据集合)` —— 期望值是实测记录，不是猜的
MUTANTS = []


def _w_rules(obj):
    return [r for r in obj['routes']
            if (r.get('_original') or {}).get('via') in
            ('obj_doorW', 'obj_doorw_musfade')]


def m_prio(obj):
    u"""M1 把一条 W 规则的 priority 挪出 7000 段 ⇒ 段位不再连续 + 声明序对不上。"""
    _w_rules(obj)[10]['priority'] = 8000


def m_marker_upper(obj):
    u"""M2 把一条的 marker 写成**大写** `obj_markerW`（第125轮那把错尺的名字）。"""
    _w_rules(obj)[3]['_original']['marker'] = 'obj_markerW'


def m_door_letter(obj):
    u"""M3 把一条的 `when_door` 改成 X ⇒ 它掉出 W 段论域，重推集合就少了这条。"""
    _w_rules(obj)[20]['when_door'] = 'X'


def m_table(obj):
    u"""M4 把一条的 `table` 换成 X 门那段代码 ⇒ 机制名与门对象对不上。"""
    _w_rules(obj)[30]['_original']['table'] = 'gml_Object_obj_doorX_Alarm_2'


def m_target(obj):
    u"""M5 把一条的目标换成另一间已登记场景 ⇒ 证据里没有这条边（凭空多写）。"""
    _w_rules(obj)[40]['to'] = 'ch1.hometown.town_south'


def m_dup(obj):
    u"""M6 复制一条（同一扇门、同一个目标）⇒ 同 (场景,目标) 出现两次。"""
    rules = obj['routes']
    for i, r in enumerate(rules):
        if (r.get('_original') or {}).get('via') in ('obj_doorW', 'obj_doorw_musfade'):
            _c = json.loads(json.dumps(r))
            _c['priority'] = r['priority']
            rules.insert(i + 1, _c)
            return
    raise SystemExit('没找到 W 规则')


def m_reason(obj):
    u"""M7 把一条 reason 里的实测 marker 名改成大写 ⇒ 文案造假（C6 守这条）。"""
    _w_rules(obj)[50]['reason'] = _w_rules(obj)[50]['reason'].replace(
        'obj_markerw', 'obj_markerW')


def m_harmless(obj):
    u"""M9 **无害**变异：只改一句中文说明，不动任何判定字段 ⇒ 一条都不许红。"""
    _w_rules(obj)[60]['reason'] = _w_rules(obj)[60]['reason'].replace(
        u'原点连接', u'原点连接')


def m_sprite(doors):
    u"""M8 把证据里 `obj_markerw` 的 sprite 改成 `spr_markerX` ⇒ E1 必须红。"""
    doors['chapters']['ch1']['marker_objects']['obj_markerw'] = 'spr_markerX'


def m_desc_of(src):
    u"""M10 把判据自己的 `_desc_of` 退回"只认裸字面量" ⇒ 名字扫描恒空。

    ★ 用**单 token** 替换（`ast.BinOp` → `ast.Load`），不往源码里塞换行：
      带换行的替换串在本机的写入通道上被吃过一次（变成字面 `\n`），
      报出来是 `SyntaxError` 而看着像"判据不灵" —— 夹具不保真=报假问题。
    """
    old = u'if isinstance(node, ast.BinOp):'
    if old not in src:
        raise SystemExit(u'M10 锚点没找到（check168 被改过）')
    return src.replace(old, u'if isinstance(node, ast.Load):')


def build_routes_mutant(tmp, fn):
    obj = jload(ROUTES)
    fn(obj)
    p = os.path.join(tmp, 'routes_m.json')
    jdump_routes(obj, p)
    return p


def build_doors_mutant(tmp, fn):
    obj = jload(DOORS)
    fn(obj)
    p = os.path.join(tmp, 'doors_m.json')
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    with open(p, 'wb') as fh:
        fh.write(text.replace('\n', '\r\n').encode('utf-8'))
    return p


def build_check_mutant(tmp, fn):
    src = io.open(CHECK, encoding='utf-8', newline='').read()
    p = os.path.join(tmp, 'check_m.py')
    with open(p, 'wb') as fh:
        fh.write(fn(src).encode('utf-8'))
    return p


PLAN = [
    # ★ 这些"预期红"都是**实测记录**（第一次跑完改成正的），改判据时要跟着改。
    #   为什么好几条不止一个红：这些判据**分工重叠但不等价** ——
    #   A4 守"marker 是不是实测名"、B7 守"两类落点各多少条"、C3 守"目标房真有它"、
    #   C6 守"文案没造假"，改一个 marker 名会同时踩到四处，是**正常的**。
    #   真正要防的是"改了却一条都不红"（判据是摆设），和"红了完全无关的一组"。
    ('M1  priority 挪出 7000 段', 'routes', m_prio,
     {'A1', 'C5'}),
    ('M2  marker 写成大写 obj_markerW', 'routes', m_marker_upper,
     {'A4', 'B7', 'C3', 'C6'}),
    ('M3  when_door 改成 X', 'routes', m_door_letter,
     {'A3'}),
    ('M4  table 换成 X 门那段', 'routes', m_table,
     {'A6', 'C2'}),
    ('M5  目标换成另一间房', 'routes', m_target,
     {'B3', 'C1'}),
    ('M6  复制一条（同门同目标）', 'routes', m_dup,
     {'A0', 'A1', 'A4', 'A5', 'B7', 'C5'}),
    ('M7  reason 里 marker 改成大写', 'routes', m_reason,
     {'C6'}),
    ('M8  证据里 obj_markerw 的 sprite 改掉', 'doors', m_sprite,
     {'E1'}),
    ('M9  无害：只改一句中文说明', 'routes', m_harmless,
     set()),
    ('M10 判据自己的 _desc_of 退回只认裸字面量', 'check', m_desc_of,
     {'F5'}),
]

_before = {'routes': sha1(ROUTES), 'doors': sha1(DOORS)}

tmp = tempfile.mkdtemp(prefix='m168_')
_np = _nf = 0
try:
    print('=' * 70)
    print(u'收口前的 sha1：routes=%s doors=%s' % (_before['routes'][:12],
                                                  _before['doors'][:12]))
    print(u'变异副本目录：%s' % tmp)
    print('=' * 70)

    for label, kind, fn, expect in PLAN:
        if kind == 'routes':
            p = build_routes_mutant(tmp, fn)
            env = {'CQ_ROUTES168': p}
            script = CHECK
        elif kind == 'doors':
            p = build_doors_mutant(tmp, fn)
            env = {'CQ_DOORS168': p}
            script = CHECK
        else:
            p = build_check_mutant(tmp, fn)
            # ★ 副本落在 temp 里 ⇒ 它自己按 `__file__` 推出的那几条路径全是错的，
            #   会把"跑不起来"误读成"判据不灵"。三个口子都指回**真文件**。
            env = {'CQ_ROUTES168': ROUTES, 'CQ_DOORS168': DOORS,
                   'CQ_GEN168': os.path.join(HERE, 'gen_routes168.py'),
                   'CQ_PKG168': os.path.join(REPO, 'ralsei_pet'),
                   'CQ_EV42': os.path.join(REPO, 'code-quality-audit',
                                           '第42轮-原作拓扑取证', '_evidence')}
            script = p
        code, fails, out = run(script, env)
        got = set(fails)
        ok = (got == expect) and (code != 0 or not expect)
        if ok:
            _np += 1
            print(u'[PASS] %s ⇒ 红 %r（与预期一致）' % (label, sorted(got)))
        else:
            _nf += 1
            print(u'[FAIL] %s ⇒ 红 %r，预期 %r，exit=%d'
                  % (label, sorted(got), sorted(expect), code))
            for _ln in out.splitlines():
                if _ln.startswith('[FAIL]'):
                    print(u'        %s' % _ln[:120])
        try:
            os.remove(p)
        except OSError:
            pass
finally:
    shutil.rmtree(tmp, ignore_errors=True)

_after = {'routes': sha1(ROUTES), 'doors': sha1(DOORS)}
print('')
print('=' * 70)
_same = _after == _before
if _same:
    _np += 1
    print(u'[PASS] Z1 字节级还原：产品表与证据文件 sha1 未变')
else:
    _nf += 1
    print(u'[FAIL] Z1 文件被改动了：%r → %r' % (_before, _after))

code, fails, out = run(CHECK, {})
if code == 0 and not fails:
    _np += 1
    print(u'[PASS] Z2 收口复跑：无变异时 check168 全绿')
else:
    _nf += 1
    print(u'[FAIL] Z2 收口复跑红了：%r（exit=%d）' % (fails, code))

print('')
print('PASS=%d  FAIL=%d' % (_np, _nf))
if _nf:
    sys.exit(1)
print('[PASS] 第168轮变异测试全部被抓到')
