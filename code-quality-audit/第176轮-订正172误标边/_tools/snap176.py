# -*- coding: utf-8 -*-
u"""第176轮 · 把"改前副本"的指纹固化成证据（`_evidence/before176.json`）。

为什么要这一步
--------------
本轮的动作是**删 42 条边**。要证明"除了这 42 条，其余 2,768 条一字未改"，
就需要一份**不是自己产出的**改前副本 —— 否则就是拿自己和自己比。

来源：`git show HEAD:ralsei_pet/assets/scenes/_routes.json`
  · 本轮之前最后一次提交就是第175轮（没动过 `_routes.json`）⇒ 该 blob 即改前版
  · 实测：2,810 条 / 60,081 行（blob 以 LF 存储；工作区 CRLF，行数一致）
  · ★ 仓库 blob 存 LF ⇒ **不能比字节**，只能比**规范化 JSON**（`indent=2` + 排序无关）
    —— 这一点单独记在证据里，免得后人以为"字节数不等 = 被改过"

产出（`before176.json`）
----------------------
    before_routes / before_lines / before_sha1_blob   改前 blob 的三个量
    removed                                           留档条数（42）
    rest_n                                            改前去掉留档后剩下的条数
    rest_sha1                                         这 2,768 条的规范化 sha1
                                                      ⇒ 现在的 `_routes.json` 规范化后
                                                        必须与它**逐条相同**

用法：python snap176.py [--apply]
"""
import hashlib
import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
REL = 'ralsei_pet/assets/scenes/_routes.json'
APPLY = '--apply' in sys.argv


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', newline='').read())


def canon(rows):
    u"""规范化：与磁盘缩进无关、与 key 顺序无关的指纹。"""
    return hashlib.sha1(
        json.dumps(rows, ensure_ascii=False, sort_keys=True,
                   separators=(',', ':')).encode('utf-8')).hexdigest()


def main():
    blob = subprocess.run(['git', 'show', 'HEAD:' + REL], cwd=REPO,
                          stdout=subprocess.PIPE).stdout
    if not blob:
        print(u'!! 取不到 `HEAD:%s`' % REL)
        return 1
    txt = blob.decode('utf-8')
    data = json.loads(txt)
    rows = data['routes']
    removed = jl(os.path.join(EV, 'removed176.json'))['items']
    prios = set(r.get('priority') for r in removed)
    keep = [r for r in rows if r.get('priority') not in prios]
    gone = [r for r in rows if r.get('priority') in prios]

    print(u'改前 blob      : %d 条 / %d 行 / %d B（LF）'
          % (len(rows), txt.count(u'\n'), len(blob)))
    print(u'留档 priority  : %d 个' % len(prios))
    print(u'按 priority 命中: %d 条' % len(gone))
    print(u'剩下           : %d 条' % len(keep))
    if len(gone) != len(removed):
        print(u'!! 按 priority 只命中 %d 条（期望 %d）—— 留档对不上改前副本'
              % (len(gone), len(removed)))
        return 2
    # 逐条核对：改前副本里那 42 条的内容必须与留档**完全一致**（否则留档是伪造/漂移的）
    bad = []
    for a, b in zip(sorted(gone, key=lambda x: x['priority']),
                    sorted(removed, key=lambda x: x['priority'])):
        if json.dumps(a, ensure_ascii=False, sort_keys=True) != \
                json.dumps(b, ensure_ascii=False, sort_keys=True):
            bad.append(a.get('priority'))
    print(u'留档 vs 改前副本 逐条一致 : %r' % (not bad,))
    if bad:
        print(u'!! 不一致的 priority: %r' % (bad[:6],))
        return 3

    ev = {
        'note': (u'第176轮改前副本指纹。来源 `git show HEAD:%s`（本轮前最后一次提交='
                 u'第175轮，未动路由表）。★ blob 以 LF 存储、工作区 CRLF ⇒ 只比'
                 u'**规范化 JSON** 的 sha1，不比字节。' % REL),
        'before_routes': len(rows),
        'before_lines': txt.count(u'\n'),
        'before_bytes_lf': len(blob),
        'before_sha1_blob': hashlib.sha1(blob).hexdigest(),
        'removed': len(removed),
        'rest_n': len(keep),
        'rest_sha1': canon(keep),
    }
    print(u'\nrest_n   = %d' % ev['rest_n'])
    print(u'rest_sha1= %s' % ev['rest_sha1'])
    if not APPLY:
        print(u'\n[dry] 未写盘。加 --apply 落 `_evidence/before176.json`。')
        return 0
    with io.open(os.path.join(EV, 'before176.json'), 'w', encoding='utf-8',
                 newline='\n') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(u'\n[落盘] %s' % os.path.join(EV, 'before176.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
