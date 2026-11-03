# -*- coding: utf-8 -*-
u"""第147轮 · 量：英文硬截在半个单词上，退到"最后一个空格"要付多少代价。

## 病（第145轮的遗留①）

第145轮给 `_SENTENCE_ENDS` 加了 ASCII `.`，把"英文有句号却被硬截"的那批治掉了
（事件 24 字：英文 203 → 135；开口 40 字：184 → 100）。剩下的 135 / 100 条是
**24/40 字里一个句末标点都没有**的（全大写自造拼写、`hehe that tickles` 这类连写）。
它们只能走兜底：

    t = t[:max_chars].rstrip('，,、。！？!?；;：: ')

⇒ `hehe that tickles so mu` —— **切在半个单词中间**。中文没有词边界，切在字中间是正常的；
英文切在词中间，用户看到的就是一个残词。

## 候选规则（本轮要选的是"退让底线"，不是我拍）

若切点两侧都是字母/数字（= 那个词被劈开），就退到 `t[:max]` 里**最后一个空格**。

代价 = 退让后长度变短。退让太多就不如硬截（`Hi there this is a very long ...`
若唯一空格在第 3 位，退让只剩 3 个字）。所以要一个下限 `ratio`：

    keep_len >= MIN_FIRST_CHARS 且 keep_len >= ratio * max_chars

这里扫 `ratio ∈ {0, .3, .4, .5, .6, .7}`，看每种各接受多少条、平均/最短剩多少 ——
**阈值由数据选**，不是我先定一个再去找理由。

## 判据口径（与 measure145 / 第143轮同）

`res` 必是 `t0` 的前缀；`cut_midword` ⇔ **两侧都是字母/数字**。
★ 只判右侧一位会把中文全算成"切在词中"（CJK 也是 `isalnum()`）—— 145 踩过，这里沿用修正版。
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
LIVE = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out')
CORPUS = os.path.join(ROOT, 'code-quality-audit',
                      u'第113轮-全体角色AI训练', '_evidence', 'raw30')

sys.path.insert(0, PET)
from modules import event_speech as ES          # noqa: E402

CJK = re.compile(u'[\u4e00-\u9fff]')
MAX_EVENT = ES.EVENT_MAX_CHARS                  # 24
MAX_AUTO = ES.AUTO_SPEAK_MAX_CHARS              # 40
MIN = ES.MIN_FIRST_CHARS                        # 6
# ★ 与英文"词"有关的那几个字符：弯引号/连字符也算词内（`don't` / `well-known`）
RATIOS = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7)


def lang_of(s):
    letters = [c for c in s if c.strip()]
    if not letters:
        return 'none'
    return 'zh' if len(CJK.findall(s)) * 1.0 / len(letters) >= 0.30 else 'en'


def norm(t):
    t = t.strip()
    return t.strip(u'"\'“”「」『』《》').strip()


_WORDY = u'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\'\u2019-'


def cut_midword(res, t0):
    u"""切在单词中间 ⇔ 切点**两侧**都是 **ASCII** 词字符。

    ★★ 第147轮第一版用 `isalnum()` —— 对 CJK 也返回 True，于是**每一次中文硬截**
       都被算成"切在词中"（中文 959 / 200 条），据此选阈值、写产品代码，直接把中文
       输出改坏了 151 / 57 条（A/B 当场抓住，见 §147.4）。只有空格分词的文字才有
       词边界，所以这里必须限定 ASCII。
    """
    if not res or not t0 or len(res) >= len(t0):
        return False
    return res[-1] in _WORDY and t0[len(res)] in _WORDY


def retire(t0, res, max_chars, ratio):
    u"""若切在词中，退到最后一个空格；返回 (新串, 是否退让, 退让后长度)。"""
    if not cut_midword(res, t0):
        return res, False, len(res)
    sp = t0.rfind(u' ', 0, len(res) + 1)
    if sp <= 0:
        return res, False, len(res)
    keep = t0[:sp].rstrip(u'，,、。！？!?；;: ')
    n = len(keep)
    if n >= MIN and n >= ratio * max_chars:
        return keep, True, n
    return res, False, len(res)


def load():
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


def main():
    if not os.path.isdir(EV):
        os.makedirs(EV)
    if not os.path.isdir(LIVE):
        os.makedirs(LIVE)
    texts = load()
    print(u'语料：%d 条回复（%d 个文件）' % (len(texts), len(
        glob.glob(os.path.join(CORPUS, '*.jsonl')))))

    out = {u'n_turns': len(texts), u'min_first_chars': MIN,
           u'max_event': MAX_EVENT, u'max_auto': MAX_AUTO}
    detail = {}

    for tag, fn, mx in ((u'event24', ES.first_sentence, MAX_EVENT),
                        (u'auto40', ES.fit_sentences, MAX_AUTO)):
        st = {u'midword': {u'en': 0, u'zh': 0}, u'hardcut': {u'en': 0, u'zh': 0},
              u'no_punct_en': 0}
        sweep = dict((r, {u'accepted': 0, u'lost': 0, u'min_keep': 10 ** 6,
                          u'min_gain': 10 ** 6}) for r in RATIOS)
        per_case = []
        for txt in texts:
            t0 = norm(txt)
            if not t0:
                continue
            res = fn(txt)
            if not res:
                continue
            lg = lang_of(t0)
            if cut_midword(res, t0):
                st[u'midword'][lg] += 1
                if lg == u'en':
                    for r in RATIOS:
                        new, moved, n = retire(t0, res, mx, r)
                        if not moved:
                            continue
                        d = sweep[r]
                        d[u'accepted'] += 1
                        d[u'lost'] += len(res) - n
                        d[u'min_keep'] = min(d[u'min_keep'], n)
                        d[u'min_gain'] = min(d[u'min_gain'], len(res) - n)
                        if r == 0.5:
                            per_case.append([t0[:64], res, new, len(res), n])
            elif len(t0) > mx:
                st[u'hardcut'][lg] += 1
            # "24/40 字里一个句末标点都没有"= 走了兜底分支
            if lg == u'en' and len(t0) > mx and not ES._sentence_ends(t0[:mx]):
                st[u'no_punct_en'] += 1
        out[tag] = dict((k, (v if not isinstance(v, dict) else dict(v)))
                        for k, v in st.items())
        _sw = {}
        for r in RATIOS:
            d = sweep[r]
            n_acc = d[u'accepted']
            _sw[u'%.1f' % r] = {
                u'accepted': n_acc,
                u'avg_lost': round(d[u'lost'] * 1.0 / n_acc, 2) if n_acc else 0,
                u'min_keep': d[u'min_keep'] if n_acc else 0,
                u'min_gain': d[u'min_gain'] if n_acc else 0,
            }
        out[tag][u'sweep'] = _sw
        detail[tag] = per_case

        print(u'')
        print(u'== %s（上限 %d）==' % (tag, mx))
        print(u'  切在词中：英文 %d ／ 中文 %d' % (st[u'midword'][u'en'], st[u'midword'][u'zh']))
        print(u'  硬截但没切在词中（末尾是标点/空格）：英文 %d ／ 中文 %d'
              % (st[u'hardcut'][u'en'], st[u'hardcut'][u'zh']))
        print(u'  英文"前 %d 字内无任何句末标点"：%d 条' % (mx, st[u'no_punct_en']))
        print(u'  阈值扫描（只在"切在词中"的英文上）')
        print(u'    ratio | 接受 | 平均少几个字 | 最短剩 | 最少省')
        for r in RATIOS:
            d = sweep[r]
            if not d[u'accepted']:
                print(u'    %5.1f |    0' % r)
                continue
            print(u'    %5.1f | %4d | %12.2f | %6d | %6d'
                  % (r, d[u'accepted'], d[u'lost'] * 1.0 / d[u'accepted'],
                     d[u'min_keep'], d[u'min_gain']))

    io.open(os.path.join(EV, 'measure147.json'), 'w', encoding='utf-8', newline='').write(
        json.dumps(out, ensure_ascii=False, indent=1))
    io.open(os.path.join(LIVE, 'measure147.cases.json'), 'w',
            encoding='utf-8', newline='').write(
        json.dumps(detail, ensure_ascii=False, indent=1))
    print(u'')
    print(u'稳定结论 → _evidence/measure147.json；逐条样本 → regress/_out/measure147.cases.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
