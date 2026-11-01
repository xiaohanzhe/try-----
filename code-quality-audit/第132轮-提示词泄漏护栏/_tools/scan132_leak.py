# -*- coding: utf-8 -*-
"""第132轮 · 取证：回复到底有多像"在念 system"（零网络，只读已冻结的 42 条）。

问题：第131轮真机里出现过一条之前没注意的毛病 —— 回复把人设里的**编号规则段**
念了出来（"你说的是坏消息的时候我不该用亮起来的开头，先就着那件具体的事问一句"）。
那段原文在 `ralsei_persona.md` 的「语气示范」里：

    一、你说的是坏消息（被骂、累了、难过、出了事）：这种时候不许用亮起来的开头。
    先就着他那件具体的事问一句（是哪一件事、怎么弄成这样的、严不严重），

要判"这是不是照抄"，就得有**可复核的数字**，不能凭我说像。本脚本算三个量：

  1. `lcs`   —— 回复与 system 的**最长公共子串**长度（逐字，含标点）
  2. `lcs_flat` —— 去掉标点/空白后的最长公共子串长度（防"标点不同就判不像"）
  3. `n6`    —— 去掉标点后，回复里**与 system 共有的 6 字连续片段**个数
               （6-gram 对"改一两个字"的改写仍然敏感，是判断复述的主力）

★ 为什么要三个：只看 1 会被标点差异骗（模型会把"，"改成"。"），
  只看 3 会因为常用短语（"你今天的"）虚高 ⇒ 三个一起看，并且**先把分布打出来**，
  再决定阈值，而不是先定阈值再挑例子。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测', '_evidence')
EV = os.path.join(ROUND, '_evidence')
if not os.path.isdir(EV):
    os.makedirs(EV)

PERSONA = os.path.join(ROOT, 'ralsei_pet', 'assets', 'ralsei_persona.md')
SNAP = os.path.join(EV131, 'persona_before130.md')
JSONL = os.path.join(EV131, 'live7_131.jsonl')

PUNCT = u'，。！？、；：“”‘’（）《》…—～ .,!?;:()[]"\'`~-*#\n\r\t'


def flat(s):
    return u''.join(ch for ch in s if ch not in PUNCT)


def lcs_len(a, b):
    """最长公共子串长度（经典 DP，只留两行）。a/b 长度都在几千级，够用。"""
    if not a or not b:
        return 0
    best = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def grams(s, n=6):
    return set(s[i:i + n] for i in range(0, max(0, len(s) - n + 1)))


def main():
    for p in (PERSONA, SNAP, JSONL):
        if not os.path.isfile(p):
            print('[FAIL] 缺文件：%s' % p)
            return 2

    persona_after = io.open(PERSONA, encoding='utf-8', newline='').read()
    persona_before = io.open(SNAP, encoding='utf-8', newline='').read()
    rows = [json.loads(l) for l in io.open(JSONL, encoding='utf-8') if l.strip()]
    print('[数据] 42 条里读到 %d 条' % len(rows))

    # 两臂各自面对的人设正文（尾部 534 字符三条题都一样，这里只比人设段）
    sys_map = {'before': persona_before, 'after': persona_after}

    out = []
    for r in rows:
        sys_text = sys_map[r['arm']]
        rep = r['reply'] or ''
        d = {
            'arm': r['arm'], 'qid': r['qid'], 'sample': r['sample'],
            'chars': len(rep),
            'lcs': lcs_len(rep, sys_text),
            'lcs_flat': lcs_len(flat(rep), flat(sys_text)),
            'n6': len(grams(flat(rep), 6) & grams(flat(sys_text), 6)),
            'reply': rep,
        }
        out.append(d)

    print('')
    print('%-8s %-4s %-4s %5s %5s %6s %4s  %s'
          % ('arm', 'qid', '#', 'chars', 'lcs', 'lcsfl', 'n6', '首 40 字'))
    for d in out:
        print('%-8s %-4s %-4d %5d %5d %6d %4d  %s'
              % (d['arm'], d['qid'], d['sample'], d['chars'], d['lcs'],
                 d['lcs_flat'], d['n6'], d['reply'][:40].replace('\n', ' ')))

    for key in ('lcs', 'lcs_flat', 'n6'):
        v = sorted(d[key] for d in out)
        n = len(v)
        print('')
        print('[分布] %-8s min=%d p50=%d p90=%d max=%d'
              % (key, v[0], v[n // 2], v[int(n * 0.9)], v[-1]))

    # 把最像"念规则"的 5 条按 lcs_flat 排出来，供人工确认
    print('')
    print('[最像念规则的 5 条]')
    for d in sorted(out, key=lambda x: -x['lcs_flat'])[:5]:
        print('  lcs_flat=%-3d n6=%-3d %s/%s#%d  %s'
              % (d['lcs_flat'], d['n6'], d['arm'], d['qid'], d['sample'],
                 d['reply'][:90].replace('\n', ' ')))

    with io.open(os.path.join(EV, 'leak_scan_132.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps({'rows': out}, ensure_ascii=False, indent=1))
    print('')
    print('[落盘] %s' % os.path.join(EV, 'leak_scan_132.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
