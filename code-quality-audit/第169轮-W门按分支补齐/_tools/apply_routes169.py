# -*- coding: utf-8 -*-
u"""第169轮 · 把 `w_rules169.json` 的 102 条**文本插入** `_routes.json`。

## 为什么不整体重写
1,214,349 字节的表里有 1,828 条历史条目，`json.loads`→`json.dumps` 会重排
所有缩进/转义 —— 一旦与原生成器有细微差异，`git diff` 就是全表翻红，
「改了哪几条」再也看不出来。所以只在 `routes` 数组结尾
（`\\r\\n  ],\\r\\n  "_fallback"`）插入新条目，**原字节一个不动**。

## 格式必须与原表一致
- 无 BOM、纯 CRLF、无尾换行（文件以 `}` 结束）
- 条目缩进 4、字段 6、`_original` 子字段 8
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
ROUTES_P = os.path.join(SCENES, '_routes.json')
RULES_P = os.path.join(ROUND, '_evidence', 'w_rules169.json')

MARKER = b'\r\n  ],\r\n  "_fallback"'


def dumps_route(r):
    u"""按原表缩进（条目 4 空格）序列化一条规则。"""
    s = json.dumps(r, ensure_ascii=False, indent=2)
    return u'\r\n'.join((u'    ' + ln) if ln else ln for ln in s.split('\n'))


def main():
    raw = io.open(ROUTES_P, 'rb').read()
    rules = json.loads(io.open(RULES_P, encoding='utf-8', newline='').read())

    # ---- 前置：原表必须干净 ----
    assert raw.count(MARKER) == 1, u'锚点出现 %d 次（应恰好 1 次）' % raw.count(MARKER)
    cur = json.loads(raw.decode('utf-8'))
    before = len(cur['routes'])
    assert before == 1828, u'原表 %d 条（应为 1828）' % before
    assert not [r for r in cur['routes']
                if (r.get('_original') or {}).get('batch') == 169], \
        u'表里已存在 batch=169 的条目，拒绝重复写入'

    body = u',\r\n'.join(dumps_route(r) for r in rules)
    idx = raw.rindex(MARKER)
    head, tail = raw[:idx], raw[idx:]
    out = head + b',\r\n' + body.encode('utf-8') + tail
    io.open(ROUTES_P, 'wb').write(out)

    # ---- 后置：逐项核验 ----
    raw2 = io.open(ROUTES_P, 'rb').read()
    d2 = json.loads(raw2.decode('utf-8'))
    n2 = len(d2['routes'])
    mine = [r for r in d2['routes'] if (r.get('_original') or {}).get('batch') == 169]
    prios = sorted(r['priority'] for r in mine)
    print(u'条目 %d -> %d（新增 %d）' % (before, n2, n2 - before))
    print(u'batch=169 条数 %d，priority %d~%d 连续=%s'
          % (len(mine), prios[0], prios[-1],
             prios == list(range(prios[0], prios[-1] + 1))))
    print(u'字节 %d，BOM=%s，CRLF=%d，裸LF=%d，尾字节=%r'
          % (len(raw2), raw2[:3] == b'\xef\xbb\xbf',
             raw2.count(b'\r\n'), raw2.count(b'\n') - raw2.count(b'\r\n'),
             raw2[-3:]))
    print(u'顶层键 %r，_fallback 仍在=%s'
          % (list(d2.keys()), '_fallback' in d2))


if __name__ == '__main__':
    main()
