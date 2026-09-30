# -*- coding: utf-8 -*-
"""第68轮 · 记忆压缩的逐令牌回验（自动 diff，不手列）。

★ 铁律（详版 §三.2）：`被删令牌 = toks(改前) - toks(改后)`，**让 diff 决定测什么**。
★ 改前版本**不能**用 `git show HEAD:`（一提交就成"改后" ⇒ diff 变空 ⇒ 判据静默失效）
  ⇒ 先**快照入库**（`_evidence/mem_quick_before68.md`），复检永远拿"快照 vs 现盘"比。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND68 = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND68, '..', '..'))
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
DETAIL = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
SNAP = os.path.join(ROUND68, '_evidence', 'mem_quick_before68.md')
OUT = os.path.join(ROUND68, '_evidence', '逐令牌回验68.txt')

LINES = []


def say(s=''):
    LINES.append(s)
    print(s)


def tokenize(t):
    toks = set()
    toks |= set(re.findall(r'`([^`\n]{2,60})`', t))          # 反引号片段
    toks |= set(re.findall(r'[A-Za-z_][A-Za-z0-9_.\-]{3,60}', t))  # 标识符
    toks |= set(re.findall(r'\d{3,}', t))                     # 多位数
    toks |= set(re.findall(r'\d+→\d+', t))                    # 13→50 这种
    for run in re.findall(r'[\u4e00-\u9fff]{4,}', t):         # 连续中文，切到 12 字以内
        if len(run) <= 12:
            toks.add(run)
    return toks


def squash(s):
    return re.sub(r'[\s`;=,.()（）_\-/／|｜·：:""]+', '', s)


def main():
    # 1) 快照改前版本（只在快照不存在时抓 —— 复跑要拿同一份快照）
    if not os.path.isfile(SNAP):
        r = subprocess.run(['git', 'show', 'HEAD:.workbuddy/memory/MEMORY.md'],
                           cwd=ROOT, capture_output=True)
        assert r.returncode == 0, r.stderr[:300]
        io.open(SNAP, 'wb').write(r.stdout)
        say('已快照改前速查本 -> %s（%d B）' % (os.path.basename(SNAP), len(r.stdout)))
    before = io.open(SNAP, 'r', encoding='utf-8').read()
    after = io.open(MEM, 'r', encoding='utf-8').read()
    detail = io.open(DETAIL, 'r', encoding='utf-8').read()
    d_sq = squash(detail)

    # 2) 自动 diff（★ 不手列）
    removed = sorted(tokenize(before) - tokenize(after))
    # 只看"像内容"的：长度 >= 4
    removed = [t for t in removed if len(t) >= 4]
    say('')
    say('== 被删令牌（toks(before) - toks(after)，%d 个）==' % len(removed))

    # 3) 三级宽式匹配：raw -> squashed -> subphrase(中文>=4 连续子串)
    raw_hit, sq_hit, sub_hit, whitelist = [], [], [], []

    # 白名单：每条给"为什么可以不在详版原样出现" + 一个**锚点**（锚点必须真在详版里）
    WL = {
        '按章对象表': ('详版 §64.2/64.4 用的是「按章取表」这一表述', '按章取表'),
        'inst68五章': ('详版 §64.2 写作「ch2~5→chapter2~5_objmap43」/「按章取表」', '按章取表'),
    }

    for t in removed:
        if t in detail:
            raw_hit.append(t)
        elif squash(t) in d_sq:
            sq_hit.append(t)
        else:
            subs = [t[i:i + 4] for i in range(0, len(t) - 3)]
            if any(len(s) == 4 and re.fullmatch(r'[\u4e00-\u9fff]{4}', s) and s in detail
                   for s in subs):
                sub_hit.append(t)
            else:
                whitelist.append(t)

    say('  ① raw 命中 %d：%s' % (len(raw_hit), raw_hit))
    say('  ② squashed 命中 %d：%s' % (len(sq_hit), sq_hit))
    say('  ③ subphrase 命中 %d：%s' % (len(sub_hit), sub_hit))
    say('  ④ 未命中 -> 白名单 %d：%s' % (len(whitelist), whitelist))

    # 4) 白名单复核：理由 + 锚点必须真在详版
    bad_wl = []
    for t in whitelist:
        rec = WL.get(t)
        if not rec:
            bad_wl.append('%s（无白名单条目）' % t)
            continue
        why, anchor = rec
        if anchor not in detail:
            bad_wl.append('%s（锚点 %r 不在详版）' % (t, anchor))
    say('  白名单复核：%s' % ('全部通过（理由 + 锚点在位）' if not bad_wl else bad_wl))

    # 5) 控制
    n_noop = len(raw_hit) + len(sq_hit) + len(sub_hit)
    fake = '彘鬻鱻麤龘靐齉爩虪黐'
    fake_hit = fake in detail
    say('')
    say('== 控制 ==')
    say('  no-op 控制：自动命中数 = %d（必须 > 0，否则判据没在干活）' % n_noop)
    say('  负控制：生僻字串 %r 是否命中详版 = %s（必须 False）' % (fake, fake_hit))
    # 夹具自证：负控制串的所有连续 4 字子串都必须阴性
    subs = set(fake[i:i + 4] for i in range(0, len(fake) - 3))
    leak = [s for s in subs if s in detail]
    say('  夹具自证：负控制串的 4 字子串阳性数 = %d（必须 0）' % len(leak))

    ok = (not bad_wl) and n_noop > 0 and (not fake_hit) and (not leak)
    say('')
    say('================ 逐令牌回验：%s ================' % ('PASS' if ok else 'FAIL'))
    io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(LINES) + '\n')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
