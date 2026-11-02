# -*- coding: utf-8 -*-
"""第145轮 · 量：事件链 / 主动开口链的 24 / 40 字上限，英文台词被切成半个单词了吗。

## 为什么问这个

第143轮修了**对话链**（`main._clean_ai_reply`，上限 200）不认 ASCII `.` 的毛病：
英文回复找不到切点 ⇒ `t[:200]` 硬截 ⇒ 切在半个单词上（166 条超限里 61 条）。

同一个病在**另外两条链**上还没查过：
  * `event_speech.first_sentence`  上限 **24**（用户点东西看到的事件反应）
  * `event_speech.fit_sentences`   上限 **40**（Ralsei 主动开口）
两条都靠 `_SENTENCE_ENDS = u'。！？!?\\n…'` 找切点 —— **不含 ASCII `.`**。
⇒ 英文回复在 24/40 字内**一个切点都没有**，只能走末尾那句
`t[:max_chars].rstrip('，,、。！？!?；;：: ')` ⇒ 切在单词中间。

而且 24 字对英文尤其狠：24 个字符大约 4 个单词。

## 怎么判"切在单词中间"

`res` 是被测函数的输出，`t0` 是它内部归一化后的原文（`strip` + 去引号）。
`res` 一定是 `t0` 的前缀（本函数的写法如此），于是：

    切在单词中间  ⇔  `t0[len(res)]` 是字母/数字

因为若切点是句末标点，那一位就是标点或空格；若是硬截，那一位正好是被切开的
那个单词的第二个字符。

★ 为什么不用"末字符是不是字母"：英文正常句子也以字母结尾（`...a tough` 之外的
  `Hello there` 也以字母结尾）⇒ 那样判会把干净结果全算成坏结果。
★ 为什么不用"res 的长度 == max_chars"：末尾 `rstrip` 会改长度，中文也可能正好
  停在 24 但切在标点上。

## 语言判定

CJK 字符（`\\u4e00-\\u9fff`）占比 ≥ 30% 记中文，否则记英文（与第143轮同口径）。
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
CORPUS = os.path.join(ROOT, 'code-quality-audit',
                      u'第113轮-全体角色AI训练', '_evidence', 'raw30')

sys.path.insert(0, PET)
from modules import event_speech as ES          # noqa: E402

CJK = re.compile(u'[\u4e00-\u9fff]')


def lang_of(s):
    letters = [c for c in s if c.strip()]
    if not letters:
        return 'none'
    n_cjk = len(CJK.findall(s))
    return 'zh' if n_cjk * 1.0 / len(letters) >= 0.30 else 'en'


def norm(t):
    """与 `first_sentence` / `fit_sentences` 开头那段归一化**同形**。"""
    t = t.strip()
    t = t.strip(u'"\'“”「」『』《》').strip()
    return t


def cut_midword(res, t0):
    """返回 True 表示切在单词中间（见模块头）。

    ★★ 必须**两侧都是字母/数字**才算：
      第一版只判 `t0[len(res)]` 是字母数字 ⇒ 中文全被误判 —— 中文没有词边界，
      切在 `。` 之后的下一位当然是汉字（`isalnum()` 对 CJK 也返回 True）
      ⇒ 中文 3639/5144「切在单词中间」全是假的。
      真正的判据是"**切点左边也是字母**"：左边是标点 ⇒ 切在句末；左边是字母、
      右边也是字母 ⇒ 那个词被劈开了。
    """
    if not res or not t0:
        return False
    if len(res) >= len(t0):
        return False
    if not res[-1].isalnum():
        return False
    return t0[len(res)].isalnum()


def main():
    files = sorted(glob.glob(os.path.join(CORPUS, '*.jsonl')))
    rows = []
    n_turn = 0
    for p in files:
        nid = os.path.splitext(os.path.basename(p))[0]
        with io.open(p, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                for tr in (rec.get('turns') or []):
                    txt = tr.get('final') or ''
                    if not isinstance(txt, str) or not txt.strip():
                        continue
                    n_turn += 1
                    t0 = norm(txt)
                    if not t0:
                        continue
                    r24 = ES.first_sentence(txt)
                    r40 = ES.fit_sentences(txt)
                    rows.append({
                        'id': nid,
                        'i': tr.get('i'),
                        'lang': lang_of(t0),
                        'len': len(t0),
                        'changed24': r24 != t0,
                        'changed40': r40 != t0,
                        'mid24': cut_midword(r24, t0),
                        'mid40': cut_midword(r40, t0),
                        'raw': t0[:160],
                        'r24': r24,
                        'r40': r40,
                    })

    def agg(sub):
        return {
            'turns': len(sub),
            'changed24': sum(1 for r in sub if r['changed24']),
            'changed40': sum(1 for r in sub if r['changed40']),
            'mid24': sum(1 for r in sub if r['mid24']),
            'mid40': sum(1 for r in sub if r['mid40']),
        }

    zh = [r for r in rows if r['lang'] == 'zh']
    en = [r for r in rows if r['lang'] == 'en']
    out = {
        'note': (u'第145轮：事件链 first_sentence(24) / 主动开口 fit_sentences(40) '
                 u'在英文回复上切在半个单词的次数。mid = t0[len(res)] 仍是字母/数字。'),
        'files': len(files),
        'turns': n_turn,
        'all': agg(rows),
        'zh': agg(zh),
        'en': agg(en),
        'en_dot_in_24': sum(1 for r in en if u'.' in r['raw'][:24]),
        'en_samples_mid24': [
            {'id': r['id'], 'i': r['i'], 'r24': r['r24'],
             'next': r['raw'][len(r['r24']):len(r['r24']) + 12],
             'raw': r['raw'][:90]}
            for r in en if r['mid24']][:10],
        'en_samples_mid40': [
            {'id': r['id'], 'i': r['i'], 'r40': r['r40'],
             'next': r['raw'][len(r['r40']):len(r['r40']) + 12],
             'raw': r['raw'][:90]}
            for r in en if r['mid40']][:10],
    }
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(os.path.join(EV, 'lead145.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))

    print(u'语料：%d 个文件 / %d 条回复' % (len(files), n_turn))
    for k in ('all', 'zh', 'en'):
        a = out[k]
        print(u'%-4s 共 %5d ｜ 24 字被切 %4d ｜ **切在单词中间 %4d** '
              u'｜ 40 字被切 %4d ｜ **切在单词中间 %4d**'
              % (k, a['turns'], a['changed24'], a['mid24'],
                 a['changed40'], a['mid40']))
    print(u'（英文里"24 字内含 ASCII `.`"的条数：%d）' % out['en_dot_in_24'])
    print(u'')
    print(u'英文 24 字切在单词中间的样例：')
    for s in out['en_samples_mid24']:
        print(u'  [%s#%s] r24=%r ｜ 紧跟 %r' % (s['id'], s['i'], s['r24'], s['next']))
    print(u'')
    print(u'英文 40 字切在单词中间的样例：')
    for s in out['en_samples_mid40']:
        print(u'  [%s#%s] r40=%r ｜ 紧跟 %r' % (s['id'], s['i'], s['r40'], s['next']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
