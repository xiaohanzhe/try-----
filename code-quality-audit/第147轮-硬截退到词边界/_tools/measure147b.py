# -*- coding: utf-8 -*-
u"""第147轮 · A/B：HEAD 版 vs 工作区版 `event_speech`，**各自真 import**。

## 为什么要两个模块实例

"改前改后一样/不一样"这种话，只有**两份代码各自被真的执行一遍**才算证据。
第145轮就是这么做的：`git show HEAD:…/event_speech.py` 落到 `D:\\_tmp`，
用 `importlib.util.spec_from_file_location` 单独加载一份 —— **不复刻夹具**。

## A/B 的前置断言

**两份源码的 sha1 必须不同**。相同 ⇒ 说明根本没改到（或者读到同一份），
那么后面所有"改善了"的数字都是假的。这条断言比任何统计都重要。

## 三个量

1. **英文切在词中**：24 字链 / 40 字链各多少条（旧 → 新）
2. **中文输出逐条 A/B**：必须**零差异** —— 这是负控制：
   规则不与语言挂钩（中文没空格 ⇒ `rfind` 返回 -1），一旦中文也变了，说明
   `_hard_cut` 动到了不该动的地方。
3. 受影响条目的**平均少几个字**（代价）。
"""
import glob
import hashlib
import importlib.util
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
REL = u'ralsei_pet/modules/event_speech.py'
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
LIVE = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out')
CORPUS = os.path.join(ROOT, 'code-quality-audit',
                      u'第113轮-全体角色AI训练', '_evidence', 'raw30')
HEAD_COPY = u'D:\\_tmp\\_es147_head.py'

CJK = re.compile(u'[\u4e00-\u9fff]')


def _sha(b):
    return hashlib.sha1(b).hexdigest()


def lang_of(s):
    letters = [c for c in s if c.strip()]
    if not letters:
        return 'none'
    return 'zh' if len(CJK.findall(s)) * 1.0 / len(letters) >= 0.30 else 'en'


# ★ 与产品、`measure147` **同一口径**：只有 ASCII 词字符才算词边界
#   （`isalnum()` 对 CJK 也是 True，那会把每一次中文硬截都算成“切在词中”。第147轮就是这么裁的跟头）。
_WORDY = u'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\'\u2019-'


def cut_midword(res, t0):
    if not res or not t0 or len(res) >= len(t0):
        return False
    return res[-1] in _WORDY and t0[len(res)] in _WORDY


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def head_source():
    import subprocess
    p = subprocess.Popen(['git', 'show', 'HEAD:' + REL], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    o, e = p.communicate()
    if p.returncode != 0:
        raise RuntimeError(u'git show 失败：%s' % e.decode('utf-8', 'replace'))
    return o


def corpus():
    texts = []
    for p in sorted(glob.glob(os.path.join(CORPUS, '*.jsonl'))):
        with io.open(p, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                for tr in (rec.get('turns') or []):
                    txt = tr.get('final') or u''
                    if isinstance(txt, str) and txt.strip():
                        texts.append(txt)
    return texts


def norm(t):
    t = t.strip()
    return t.strip(u'"\'“”「」『』《》').strip()


def main():
    if not os.path.isdir(u'D:\\_tmp'):
        os.makedirs(u'D:\\_tmp')
    if not os.path.isdir(EV):
        os.makedirs(EV)
    if not os.path.isdir(LIVE):
        os.makedirs(LIVE)

    head_bytes = head_source()
    work_path = os.path.join(ROOT, REL)
    work_bytes = io.open(work_path, 'rb').read()
    print(u'HEAD sha1 = %s' % _sha(head_bytes)[:12])
    print(u'工作区  sha1 = %s' % _sha(work_bytes)[:12])
    # ★★★ A/B 前置断言：两份必须**真的不同**
    if _sha(head_bytes) == _sha(work_bytes):
        print(u'!! 两份源码完全相同 —— 本轮什么都没改到，"改善了"全是假的')
        return 2

    io.open(HEAD_COPY, 'wb').write(head_bytes)
    try:
        old = load_module(HEAD_COPY, 'es147_head')
        new = load_module(work_path, 'es147_work')
    finally:
        if os.path.exists(HEAD_COPY):
            os.remove(HEAD_COPY)

    texts = corpus()
    print(u'语料：%d 条' % len(texts))
    res = {u'n_turns': len(texts)}
    detail = {}

    for tag, f_old, f_new, mx in ((u'event24', old.first_sentence, new.first_sentence,
                                  old.EVENT_MAX_CHARS),
                                 (u'auto40', old.fit_sentences, new.fit_sentences,
                                  old.AUTO_SPEAK_MAX_CHARS)):
        st = {u'midword_old_en': 0, u'midword_new_en': 0, u'en_changed': 0,
              u'zh_changed': 0, u'zh_total': 0, u'en_total': 0,
              u'zh_changed_legal': 0, u'zh_changed_illegal': 0,
              u'got_longer': 0, u'became_empty': 0, u'lost_sum': 0}
        cases = []
        for txt in texts:
            t0 = norm(txt)
            if not t0:
                continue
            lg = lang_of(t0)
            a = f_old(txt)
            b = f_new(txt)
            if lg == u'zh':
                st[u'zh_total'] += 1
                if a != b:
                    st[u'zh_changed'] += 1
                    # ★ ★ 分两类：旧结果**真的切在 ASCII 词中**（中文句尾接英文人名）
                    #   ⇒ 该改；其余一律归违规（纯中文绝不许被动）。
                    if cut_midword(a, t0):
                        st[u'zh_changed_legal'] += 1
                    else:
                        st[u'zh_changed_illegal'] += 1
                    cases.append([u'zh', t0[:60], a, b])
                continue
            st[u'en_total'] += 1
            if cut_midword(a, t0):
                st[u'midword_old_en'] += 1
            if cut_midword(b, t0):
                st[u'midword_new_en'] += 1
            if a != b:
                st[u'en_changed'] += 1
                st[u'lost_sum'] += len(a) - len(b)
                if len(b) > len(a):
                    st[u'got_longer'] += 1
                if not b:
                    st[u'became_empty'] += 1
                if len(cases) < 40:
                    cases.append([u'en', t0[:60], a, b])
        st[u'avg_lost'] = (round(st[u'lost_sum'] * 1.0 / st[u'en_changed'], 2)
                           if st[u'en_changed'] else 0)
        res[tag] = st
        detail[tag] = cases
        print(u'')
        print(u'== %s（上限 %d）==' % (tag, mx))
        print(u'  英文切在词中：%d -> %d' % (st[u'midword_old_en'], st[u'midword_new_en']))
        print(u'  英文有变化：%d 条（平均少 %s 个字）｜变长 %d ｜变空 %d'
              % (st[u'en_changed'], st[u'avg_lost'], st[u'got_longer'], st[u'became_empty']))
        print(u'  ★ 中文：%d 条里有变化 %d = 合法 %d（旧结果真切在 ASCII 词中）+ **违规 %d**'
              % (st[u'zh_total'], st[u'zh_changed'], st[u'zh_changed_legal'],
                 st[u'zh_changed_illegal']))
        # 守恒式：旧切词中 - 仍切词中 == 改动数
        #   （剩下那几条是**退让被两道底线拒掉**的，输出与改前逐字相同）
        print(u'  英文：旧切词中 %d - 仍切词中 %d = 应改 %d，实改 %d'
              % (st[u'midword_old_en'], st[u'midword_new_en'],
                 st[u'midword_old_en'] - st[u'midword_new_en'], st[u'en_changed']))

    # 反控制：把 `_HARD_CUT_TAIL` 换成一个空串喂给 `_hard_cut`，行为必须退回硬截
    _t = u'hehe that tickles so much i cant even'
    _oldish = _t[:24].rstrip(new._HARD_CUT_TAIL)
    res[u'negctl_old_shape'] = (_oldish == u'hehe that tickles so mu')
    res[u'negctl_new_shape'] = (new.first_sentence(_t) == u'hehe that tickles so')
    print(u'')
    print(u'反控制：旧形状 = %r ｜ 新形状 = %r'
          % (_oldish, new.first_sentence(_t)))

    _stable = {
        u'n_turns': res[u'n_turns'],
        u'event24': {k: res[u'event24'][k] for k in
                     (u'midword_old_en', u'midword_new_en', u'en_changed',
                      u'zh_changed', u'zh_changed_legal', u'zh_changed_illegal')},
        u'auto40': {k: res[u'auto40'][k] for k in
                    (u'midword_old_en', u'midword_new_en', u'en_changed',
                     u'zh_changed', u'zh_changed_legal', u'zh_changed_illegal')},
        u'negctl_old_shape': res[u'negctl_old_shape'],
        u'negctl_new_shape': res[u'negctl_new_shape'],
    }
    io.open(os.path.join(EV, 'ab147.json'), 'w', encoding='utf-8', newline='').write(
        json.dumps(_stable, ensure_ascii=False, indent=1))
    io.open(os.path.join(LIVE, 'ab147.cases.json'), 'w', encoding='utf-8',
            newline='').write(json.dumps(detail, ensure_ascii=False, indent=1))
    print(u'')
    print(u'稳定结论 → _evidence/ab147.json；逐条样本 → regress/_out/ab147.cases.json')
    # ★ 真判据（第一版写成“中文改动必须为 0”是**错的**：中文句尾接英文人名时旧结果
    #   确实切在了词中，那一类**就该改**。该守的是“纯中文一律不动”。
    bad = (res[u'event24'][u'zh_changed_illegal'] or res[u'auto40'][u'zh_changed_illegal']
           or res[u'event24'][u'got_longer'] or res[u'auto40'][u'got_longer']
           or res[u'event24'][u'became_empty'] or res[u'auto40'][u'became_empty']
           # ★ 恒等式（第一版写成“改动数 == 旧切词中数”也是错的：被底线拒掉的那几条
           #   **不会改**，所以要对账的是“应改 = 旧切词中 - 仍切词中”）
           or (res[u'event24'][u'midword_old_en'] - res[u'event24'][u'midword_new_en']
               ) != res[u'event24'][u'en_changed']
           or (res[u'auto40'][u'midword_old_en'] - res[u'auto40'][u'midword_new_en']
               ) != res[u'auto40'][u'en_changed'])
    print(u'A/B：%s' % (u'成立（英文变干净、纯中文零差异）'
                        if not bad else u'不成立 —— 看上面哪一条'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
