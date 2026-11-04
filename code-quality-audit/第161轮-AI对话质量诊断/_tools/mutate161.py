# -*- coding: utf-8 -*-
u"""第161轮负控制：把新判据**逐条拆掉**，断言 `check161` 恰好变红。

## 负控制的两半（第159/160轮的教训）

1. **破坏**：一处改动 = 一个单一破坏，且断言"红的正是那几条"（多红少红都算失败）。
2. **无害变异**（`M6`）：语义**完全等价**的改写（字符类换序），断言**一条都不许红**。
   只考"破坏会不会红"是不够的 —— 还要考"没破坏时会不会假红"。
   （第159轮 `mutate159 M9` 就是这么抓到 `H5g` 绑 if 形状的。）

用法：
    python mutate161.py          # 按 EXPECT 断言
    python mutate161.py --dry    # 只打印实际红了哪些（用于写 EXPECT）
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
TARGET = os.path.join(ROOT, 'ralsei_pet', 'modules', 'event_speech.py')
CHECK = os.path.join(HERE, 'check161.py')
PY = sys.executable


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


def _sha(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


#: (编号, 说明, 原文片段, 替代片段, 期望变红的判据)
MUTATIONS = [
    ('M1', u'删掉 ⑤「分类标题 + 冒号」',
     u"    re.compile(u'^\\\\s*你说的是(?:坏消息|好消息)\\\\s*[：:]'),\n",
     u"",
     ('A5', 'B1')),

    ('M2', u'删掉 ⑥「先就着…问一句」（抄指令原句）',
     u"    re.compile(u'先就着.{0,10}问一句'),\n",
     u"",
     ('A1', 'A11', 'A7', 'B1', 'C1', 'C2', 'C3')),

    ('M3', u'把 ⑥ 的间隔从 0~10 字收窄到 0~2 字（够不着真机那句）',
     u"    re.compile(u'先就着.{0,10}问一句'),",
     u"    re.compile(u'先就着.{0,2}问一句'),",
     ('A1', 'A11', 'A7', 'C1', 'C2', 'C3')),

    ('M4', u'把 ⑤ 的冒号要求去掉（分类标题退化成"只要这个开头"）',
     u"    re.compile(u'^\\\\s*你说的是(?:坏消息|好消息)\\\\s*[：:]'),",
     u"    re.compile(u'^\\\\s*你说的是(?:坏消息|好消息)'),",
     ('A12', 'A3', 'A6')),

    ('M5', u'删掉 ⑦「你在和我对话时 / 确认一下…设定」',
     u"    re.compile(u'你在和我对话时|确认一下我们(?:的)?设定'),\n",
     u"",
     ('A11', 'A2', 'A9', 'B1', 'C1', 'C2', 'C3')),

    # ---- 无害变异：语义等价，一条都不许红 ----
    ('M6', u'（**无害**）把 ⑦ 两个分支的先后调换 —— 语义完全等价',
     u"你在和我对话时|确认一下我们(?:的)?设定",
     u"确认一下我们(?:的)?设定|你在和我对话时",
     ()),
]


def run_check():
    p = subprocess.Popen([PY, CHECK], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode('utf-8', 'replace')
    reds = []
    for line in out.splitlines():
        if line.startswith('[FAIL] '):
            reds.append(line[7:].split()[0])
    return p.returncode, sorted(set(reds)), out


def main():
    dry = '--dry' in sys.argv
    base = _read(TARGET)
    base_sha = _sha(base)
    print(u'基线 sha1: event_speech=%s' % (base_sha[:12],))

    n_bad = 0
    for name, desc, old, new, expect in MUTATIONS:
        if base.count(old) != 1:
            print(u'[FAIL] %s 定位失败：原文片段出现 %d 次（要求恰好 1 次）'
                  % (name, base.count(old)))
            n_bad += 1
            continue
        _write(TARGET, base.replace(old, new, 1))
        try:
            rc, reds, out = run_check()
        finally:
            _write(TARGET, base)
        restored = _sha(_read(TARGET)) == base_sha
        if dry:
            print(u'[DRY ] %s %s -> rc=%s reds=%r 还原=%s'
                  % (name, desc, rc, reds, restored))
            continue
        if not expect:
            ok = (rc == 0) and not reds
            print(u'[%s] %s %s  （无害变异：一条都不许红；实得 %r）'
                  % ('PASS' if ok else 'FAIL', name, desc, reds))
        else:
            ok = (rc != 0) and reds == sorted(expect)
            print(u'[%s] %s %s  期望=%r 实得=%r'
                  % ('PASS' if ok else 'FAIL', name, desc, sorted(expect), reds))
        if not ok:
            n_bad += 1
            print(out[-1200:])
        if not restored:
            print(u'[FAIL] %s 还原后 sha1 不一致！' % (name,))
            n_bad += 1

    # ---- Z1：收口必须仍然全绿
    rc, reds, _out = run_check()
    z1 = (rc == 0) and not reds
    print(u'[%s] Z1 收口：还原后 `check161` 全绿（实得 reds=%r）'
          % ('PASS' if z1 else 'FAIL', reds))
    n_bad += 0 if z1 else 1
    # ---- Z2：指纹不变
    z2 = _sha(_read(TARGET)) == base_sha
    print(u'[%s] Z2 收口：`event_speech.py` sha1 与开工前一致' % ('PASS' if z2 else 'FAIL'))
    n_bad += 0 if z2 else 1

    print(u'\n合计：%d 处破坏 / %d 处失败' % (len(MUTATIONS), n_bad))
    return 1 if n_bad else 0


if __name__ == '__main__':
    sys.exit(main())
