# -*- coding: utf-8 -*-
u"""第169轮 · 变异测试：把 `check169` 的每条判据都拉出来遛一遍。

## 做法
每个变异只改**产品表的一份临时副本**（`CQ_ROUTES169` 指向它），判据文件一行不改。
跑完核验原表 sha1 不变，并用真表复跑一次 17/0。

## 为什么要有「无害变异」
如果连"只改一句中文说明"都报红，说明判据在扫文本而不是判行为 —— 那是误报。
反之，如果什么都报不红，判据就是恒真。两头都要有一个锚点。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import hashlib

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
ROUTES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')
CHECK = os.path.join(HERE, 'check169.py')
PY = sys.executable
TMP = os.path.join(os.environ.get('TEMP') or u'D:\\_tmp', '_mut169')
BATCH = 169


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', newline='').read())


def save(p, d):
    text = json.dumps(d, ensure_ascii=False, indent=2)
    io.open(p, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))


def sha1(p):
    return hashlib.sha1(io.open(p, 'rb').read()).hexdigest()


def run(patcher):
    os.makedirs(TMP, exist_ok=True)
    dst = os.path.join(TMP, 'routes.json')
    d = jl(ROUTES)
    patcher(d)
    save(dst, d)
    env = dict(os.environ)
    env['CQ_ROUTES169'] = dst
    p = subprocess.run([PY, CHECK], capture_output=True, env=env)
    out = p.stdout.decode('utf-8', 'replace')
    fails = []
    for ln in out.split('\n'):
        if ln.startswith('[FAIL] '):
            fails.append(ln[7:].split(' ')[0])
    return fails, out


def _mine(d):
    return [r for r in d['routes']
            if (r.get('_original') or {}).get('batch') == BATCH]


# ---------------------------------------------------------------- 变异定义
def m1(d):                      # priority 挪出本轮段
    _mine(d)[0]['priority'] = 7999


def m2(d):                      # 落点对象名写成大写（第125轮那把错尺）
    _mine(d)[0]['_original']['marker'] = 'obj_markerW'


def m3(d):                      # when_door 改成别的门
    _mine(d)[0]['when_door'] = 'X'


def m4(d):                      # 来源门对象改成另一个
    #: ★ 必须挑 `via=obj_doorW` 的那条改 —— 若拿第一条（`cc_elevator`，它本来就是
    #:   `obj_doorw_musfade`）来改，改成 "musfade" 等于**没改**，变异是空操作。
    #:   「夹具不保真 = 报假问题」，所以这里先断言真的改动了。
    r = next(x for x in _mine(d)
             if x['_original'].get('via') == 'obj_doorW')
    r['_original']['table'] = 'gml_Object_obj_doorw_musfade_Alarm_2'


def m5(d):                      # 目标换成另一间房
    tgt = _mine(d)[0]['to']
    alt = next(r['to'] for r in d['routes']
               if r['to'] != tgt and r['to'].startswith('ch2.'))
    _mine(d)[0]['to'] = alt


def m6(d):                      # 复制一条（同 when_scene / to）
    m = _mine(d)[0]
    dup = json.loads(json.dumps(m, ensure_ascii=False))
    dup['priority'] = 9999
    d['routes'].append(dup)


def m7(d):                      # 抹掉一条的 batch 标记（会被算成第168轮的老条）
    _mine(d)[0]['_original'].pop('batch')


def m8(d):                      # 把有落点的一条改成 None
    for r in _mine(d):
        if r['_original'].get('marker'):
            r['_original']['marker'] = None
            break


def m9(d):                      # 【无害】只改一句中文说明
    _mine(d)[0]['reason'] = u'这是一句被改过的说明，不影响任何数据。'


def m10(d):                     # 交换两条的 priority（段位仍连续，只有顺序错）
    m = _mine(d)
    m[0]['priority'], m[1]['priority'] = m[1]['priority'], m[0]['priority']


def m11(d):                     # 把源房号改成别的（规则与分支对不上）
    _mine(d)[0]['_original']['src_room_id'] = 999


PLAN = [
    (u'M1  priority 挪出 7088 段', m1, ['A1', 'A1b']),
    (u'M2  marker 写成大写 obj_markerW', m2, ['A4', 'C2', 'C3']),
    (u'M3  when_door 改成 X', m3, ['A3']),
    (u'M4  table 换成另一个门对象（via 不动）', m4, ['A7', 'B2']),
    (u'M5  目标换成另一间房', m5, ['B1', 'B2']),
    (u'M6  复制一条（同门同目标）', m6, ['A0', 'A1', 'A1b', 'A4', 'A5']),
    (u'M7  抹掉一条的 batch 标记', m7, ['A1', 'A4', 'B0', 'C1', 'D1', 'D2', 'D3']),
    (u'M8  把有落点的改成 None', m8, ['A4']),
    (u'M9  无害：只改一句中文说明', m9, []),
    (u'M10 交换两条 priority（段位仍连续）', m10, ['A1b']),
    (u'M11 源房号改成 999', m11, ['A1b', 'B2']),
]


def main():
    before = sha1(ROUTES)
    npass = nfail = 0
    print('=' * 78)
    for desc, fn, want in PLAN:
        fails, out = run(fn)
        ok = (sorted(set(fails)) == sorted(set(want)))
        tag = 'OK  ' if ok else 'BAD '
        if ok:
            npass += 1
        else:
            nfail += 1
        print(u'[%s] %-34s 期望红=%-14r 实得红=%r' % (tag, desc, want, sorted(set(fails))))
        if not ok:
            for ln in out.split('\n'):
                if ln.startswith('[FAIL] '):
                    print(u'        %s' % ln[:120])

    # ---- 字节级还原 ----
    after = sha1(ROUTES)
    print('=' * 78)
    print(u'原表 sha1 未变 = %s（%s）' % (before == after, before[:12]))
    p = subprocess.run([PY, CHECK], capture_output=True)
    tail = p.stdout.decode('utf-8', 'replace').strip().split('\n')[-2]
    print(u'真表复跑：%s  rc=%d' % (tail.strip(), p.returncode))
    print(u'变异 %d/%d 符合预期' % (npass, len(PLAN)))
    print('=' * 78)
    if os.path.isdir(TMP):
        shutil.rmtree(TMP, ignore_errors=True)
    return 0 if (nfail == 0 and before == after and p.returncode == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
