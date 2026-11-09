# -*- coding: utf-8 -*-
u"""第181轮 · 变异测试：把 `check181.py` 逐条证伪。

铁律：**判据必须能被破坏**。所以这里对 `_routes.json` 做 N 种定向破坏，
每一种都必须让**指定的那条判据**报红；有一条不红 ⇒ 那条判据形同虚设。

## 做法

· 全程**不碰**工作区里的真文件：先 `shutil.copyfile` 到 `--work` 指定的临时目录，
  破坏副本，再用 `CQ_ROUTES_181=<副本>` 喂给 `check181.py`（判据本身一行不改）。
· 每次跑都从源文件重新生成副本 ⇒ **幂等**（同一条命令跑两次结果一样）。
· 不改 `_index.json` / 证据目录：本轮 9 种破坏都只动 `_routes.json`。

## 用法

    python mutate181.py                 # 用默认临时目录（D:\\_tmp181\\mut）
    python mutate181.py --work E:/x     # 换临时区
    python mutate181.py --keep          # 留下变异副本以便手工比对
"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SRC = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')
CHECK = os.path.join(HERE, 'check181.py')
PY = sys.executable

FAIL_RE = re.compile(u'^\\[FAIL\\] ([A-Z]\\d+)\\b')


def load(p):
    return json.load(io.open(p, encoding='utf-8'))


def dump(doc, p):
    u"""与原文件同格式写回（`ensure_ascii=False, indent=2`，UTF-8 无 BOM，CRLF）。"""
    txt = json.dumps(doc, ensure_ascii=False, indent=2)
    with io.open(p, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(txt)
        f.write(u'\n')


def run_check(routes_path):
    env = dict(os.environ)
    env['CQ_ROUTES_181'] = routes_path
    pr = subprocess.run([PY, CHECK], cwd=HERE, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = pr.stdout.decode('utf-8', 'replace')
    reds = [m.group(1) for m in (FAIL_RE.match(ln) for ln in out.splitlines()) if m]
    return pr.returncode, reds, out


def mine_of(doc):
    return [r for r in doc['routes'] if (r.get('_original') or {}).get('batch') == 181]


# ---------------------------------------------------------------------------
#  九种破坏
# ---------------------------------------------------------------------------
def m_drop_edge(doc):
    u"""删掉一条本轮边 ⇒ 条数 62、priority 断档、有实例没人接。"""
    ms = mine_of(doc)
    doc['routes'].remove(ms[0])
    return [ms[0]['when_scene'], ms[0]['to']]


def m_dup_edge(doc):
    u"""把一条边改成与另一条同 (源,目标) ⇒ batch 内部不再唯一。"""
    ms = mine_of(doc)
    ms[1]['when_scene'] = ms[0]['when_scene']
    ms[1]['to'] = ms[0]['to']
    return [ms[0]['when_scene'], ms[0]['to']]


def m_shift_wrong(doc):
    u"""把 shift 改错（3 → 2）⇒ 下标算术与证据重推都对不上。"""
    for r in mine_of(doc):
        o = r['_original']
        if o.get('kind') == 'delta_door_shift' and o.get('shift') == 3 and not o.get('override'):
            o['shift'] = 2
            return [r['when_scene'], 3]
    raise AssertionError('找不到 shift=3 的样本')


def m_door_letter(doc):
    u"""把 `when_door` 从名字字母换成 `entrance` 数值（'E' → '6'）⇒ 混口径。"""
    for r in mine_of(doc):
        if r.get('when_door') == 'E':
            r['when_door'] = '6'
            return [r['when_scene'], '6']
    raise AssertionError('找不到 when_door=E 的样本')


def m_override_target(doc):
    u"""把 ch3 那唯一一处覆盖的目标改掉（28 → 30）。"""
    for r in mine_of(doc):
        o = r['_original']
        if o.get('override'):
            o['dst_room_id'] = 30
            o['dst_room_name'] = 'room_not_28'
            r['to'] = 'ch3.system.dw_ch3_man'
            return [r['when_scene'], 30]
    raise AssertionError('找不到 override 样本')


def m_dangling_to(doc):
    u"""把 `to` 指向不存在的场景 ⇒ 往虚空里加边。"""
    ms = mine_of(doc)
    ms[2]['to'] = 'ch9.nowhere.void'
    return [ms[2]['when_scene'], 'ch9.nowhere.void']


def m_hidden_prob(doc):
    u"""抹掉隐藏房的 `probability` ⇒ 概率登记名存实亡。"""
    for h in doc.get('_hidden_rooms') or []:
        if h.get('probability') == 0.02 and h.get('scene'):
            h.pop('probability', None)
            return [h.get('scene'), 'no_probability']
    raise AssertionError('找不到 probability=0.02 的样本')


def m_legacy_newkey(doc):
    u"""给老账塞一个本轮才有的新键 ⇒ 动了老账结构。"""
    for r in doc['routes']:
        if (r.get('_original') or {}).get('batch') != 181:
            r['_batch181_probe'] = True
            return [r['when_scene'], '_batch181_probe']
    raise AssertionError('找不到老账样本')


def m_miss_one(doc):
    u"""把一条边改挂到别的目标（条数/priority/唯一性都不变）⇒ 原实例变成"漏加"。"""
    for r in mine_of(doc):
        o = r['_original']
        if o.get('via') == 'obj_doorE':
            old = r['to']
            r['to'] = 'ch1.hometown.town' if r['to'] != 'ch1.hometown.town' else 'ch1.card_castle.cc_4f'
            return [r['when_scene'], old, r['to']]
    raise AssertionError('找不到 obj_doorE 样本')


#: (名字, 函数, 必须报红的判据 id)
#:
#: ★★ 01（删边）**不期望 D2** —— 这是刻意记下的口径：
#:    D2 断言 `_backed == _mine_set`。删掉一条边时两边**同时缩水**，依然相等，
#:    所以 D2 抓不到"少了边"，它只抓"凭空多边"（见 09 的实测红）。
#:    "少了边"由 D1 的**漏加**计数抓（原实例找不到归属 ⇒ 漏加 +1）。
#:    若把 01 也写成必须红 D2，就会逼我去改 D2 去迎合测试 —— 那才是判据失真的开始。
MUTS = [
    ('01_drop_edge', m_drop_edge, ['A2', 'A3', 'D1']),
    ('02_dup_edge', m_dup_edge, ['A4']),
    ('03_shift_wrong', m_shift_wrong, ['B3', 'B4']),
    ('04_door_letter', m_door_letter, ['B8']),
    ('05_override_target', m_override_target, ['B5']),
    ('06_dangling_to', m_dangling_to, ['C5']),
    ('07_hidden_prob', m_hidden_prob, ['E3']),
    ('08_legacy_newkey', m_legacy_newkey, ['C2']),
    ('09_miss_one', m_miss_one, ['D1', 'D2']),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default=os.path.join('D:\\', '_tmp181', 'mut'))
    ap.add_argument('--keep', action='store_true')
    a = ap.parse_args()
    if not os.path.isdir(a.work):
        os.makedirs(a.work)

    print('=' * 78)
    print(u'第181轮 · 变异测试（判据必须能被破坏）')
    print('  源文件 : %s' % SRC)
    print('  临时区 : %s' % a.work)
    print('=' * 78)

    # 0) 基座：未变异副本必须先全绿，否则后面所有的"红"都不可信
    base = os.path.join(a.work, '00_base.json')
    shutil.copyfile(SRC, base)
    rc, reds, out = run_check(base)
    n_pass = out.count(u'[PASS] ')
    n_fail = out.count(u'[FAIL] ')
    print('')
    print(u'[基座] 未变异副本：PASS=%d FAIL=%d rc=%d' % (n_pass, n_fail, rc))
    if rc != 0 or reds:
        print(out)
        print(u'!! 基座就报红了，变异测试没有意义 —— 先修判据')
        return 2

    bad = []
    print('')
    for idx, (name, fn, want) in enumerate(MUTS, 1):
        dst = os.path.join(a.work, 'mut_%s.json' % name)
        doc = load(SRC)
        info = fn(doc)
        dump(doc, dst)
        rc, reds, out = run_check(dst)
        hit = [w for w in want if w in reds]
        ok = rc != 0 and len(hit) == len(want)
        tag = u'红' if ok else u'★没红★'
        print(u'[%02d] %-22s 破坏=%-56s'
              % (idx, name, json.dumps(info, ensure_ascii=False)[:56]))
        print(u'     %s 期望红 %r → 实测红 %r（rc=%d）'
              % (tag, want, reds, rc))
        if not ok:
            bad.append((name, want, reds))

    # 幂等：同一条破坏连做两次，产物必须逐字节相同
    p1 = os.path.join(a.work, 'mut_01_drop_edge.json')
    h1 = open(p1, 'rb').read()
    doc = load(SRC)
    m_drop_edge(doc)
    dump(doc, p1)
    h2 = open(p1, 'rb').read()
    idem = (h1 == h2)
    print('')
    print(u'[幂等] 01_drop_edge 连做两次，副本逐字节相同：%s' % idem)
    if not idem:
        bad.append(('idempotent', ['byte-equal'], []))

    print('')
    print('=' * 78)
    if bad:
        print(u'变异测试未通过 %d 条：' % len(bad))
        for b in bad:
            print(u'  - %-22s 期望 %r，实测 %r' % b)
        print('=' * 78)
        return 1
    print(u'全部 %d 种破坏都被对应判据抓到（判据不是恒真）' % len(MUTS))
    print('=' * 78)

    if not a.keep:
        for f in os.listdir(a.work):
            if f.startswith('mut_') and f != '00_base.json':
                try:
                    os.remove(os.path.join(a.work, f))
                except OSError:
                    pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
