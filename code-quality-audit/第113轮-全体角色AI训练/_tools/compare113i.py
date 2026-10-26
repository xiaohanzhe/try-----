# -*- coding: utf-8 -*-
"""第113轮i · 同角色双版本对照：`ot_papyrus`(0.00) vs `ut_papyrus`(0.64) 的人设差在哪？

为什么值得单独查
----------------
两个是**同一个角色**（Papyrus）的两套世界观版本（Outertale / Undertale），
问的是同一句"你好，你在做什么？"，一个 0.00、一个 0.64。
排除了"角色设定本身有毒"——同一角色，另一个版本没问题。
⇒ 差别只能来自**人设文本的写法**。这份对照就是为了把"写法差在哪"量化出来，
   而不是我凭感觉改。

量什么（都是可数的，不猜）
  · 总字数 / 拉丁字母占比
  · 【示例反应】段的字数与拉丁占比
  · 「你会说“XXX”」这类**逐字台词引用**的条数（正则数，附命中样本）
  · 「桌宠运行口径」这类中文规范段有没有
"""
import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PDIR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')

LATIN = re.compile(r'[A-Za-z]')
#: 「你会说“…”」「你的经典台词包括：“…”」这类**逐字给出台词**的写法。
#: ★ 这才是记忆里 A12d 说的"可逐字搬走的固定例句"，也是语言跟随的直接来源。
SAY_RE = re.compile(r'(你会说|你的经典台词包括|你可以提到|你会喊|你的口头禅)[：:，,]?\s*[“"]([^”"]{4,})[”"]')


def stats(path):
    t = io.open(path, encoding='utf-8', newline='').read()
    lines = t.split('\n')
    n_ws = re.sub(r'\s', '', t)
    out = {
        'chars': len(t),
        'latin': len(LATIN.findall(n_ws)) / float(len(n_ws)) if n_ws else 0.0,
        'lines': len(lines),
    }
    # 示例反应段
    i = next((k for k, ln in enumerate(lines) if ln.strip() == '【示例反应】'), None)
    if i is not None:
        j = next((k for k in range(i + 1, len(lines)) if lines[k].strip() == '---'), None)
        seg = '\n'.join(lines[i + 1:j]) if j else ''
        sw = re.sub(r'\s', '', seg)
        out['ex_chars'] = len(seg)
        out['ex_latin'] = (len(LATIN.findall(sw)) / float(len(sw))) if sw else 0.0
    else:
        out['ex_chars'] = 0
        out['ex_latin'] = 0.0
    hits = SAY_RE.findall(t)
    out['say_n'] = len(hits)
    out['say_samples'] = [h[1][:40] for h in hits[:6]]
    out['has_runtime'] = ('桌宠运行口径' in t)
    return out


def main():
    ids = sys.argv[1:] or ['ot_papyrus', 'ut_papyrus', 'hy_guardener', 'os_rowbot',
                           'queen', 'hy_axis']
    print('%-14s %7s %7s %9s %9s %7s %6s %s'
          % ('id', '总字', '拉丁%', '示例字', '示例拉丁%', '你说条数', '口径段', '样本'))
    print('-' * 120)
    for nid in ids:
        p = os.path.join(PDIR, nid + '.txt')
        if not os.path.isfile(p):
            print('%-14s (缺)' % nid)
            continue
        s = stats(p)
        print('%-14s %7d %6.0f%% %9d %9.0f%% %7d %6s %s'
              % (nid, s['chars'], s['latin'] * 100, s['ex_chars'], s['ex_latin'] * 100,
                 s['say_n'], '有' if s['has_runtime'] else '无',
                 (s['say_samples'][0] if s['say_samples'] else '')))
    print()
    print('★ 「你说条数」= 「你会说“…”」这类逐字台词引用的条数（正则计数）')
    print('★ 对照目的是找"写法差"，不是为了把两个角色改成一样')
    return 0


if __name__ == '__main__':
    sys.exit(main())
