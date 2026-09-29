# -*- coding: utf-8 -*-
u"""第64轮 · 段1（定稿）：解析《其余人物设定.txt》（30 万字），出全量角色清单。

**只读**用户文件。产出 `_evidence/personas64.json`。

★ 关键教训（本轮踩到）：**不能按 `---` 切块**。
   实测 `---` 分隔符在文件中途**错位一行** ⇒ 每块 = 【上一角色的「回应要点」】+【下一角色的完整人设】。
   唯一可靠切法 = 按**长块开头**切：
       你是一个角色扮演 AI，你将完全以《<作品>》中的 <角色> 的身份进行对话
   ⇒ 切出的每一段 = 【长块(完整人设)】+【短块(回应要点，可能没有)】。

判据（可证伪）：
  A1 长块数 == 提取到的角色数
  A2 每个角色名非空且不含「一个角色扮演 AI」
  A3 长块 + 短块 的字数之和 ≈ 源文件字数（误差 < 5%，扣掉文件头）
  A4 负控制：不存在的角色名搜索必须 0 命中
"""
from __future__ import print_function

import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

SRC = u'C:\\Users\\23002\\Desktop\\其余人物设定.txt'
REPO = u'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')
CUR_DIR = os.path.join(REPO, u'ralsei_pet', u'assets', u'npc', u'persona')

OPENER = re.compile(u'你是一个角色扮演 AI，你将完全以《([^》]+)》中的\\s*'
                    u'(.{1,24}?)\\s*的身份进行对话')
SHORT_OPEN = re.compile(u'请始终以\\s*(.{1,24}?)\\s*的身份回应')
NEXT_HEADER = re.compile(u'以下是一段可直接用于 AI 角色扮演的 system prompt')
SEC_RE = re.compile(u'【([^】]{2,14})】')


def norm(s):
    s = re.sub(u'[（(][^）)]*[）)]', u'', s or u'')      # 去中文/英文括号注释：King（黑桃国王）→ King
    return re.sub(u'[\\s·、．.,\\-—]', u'', s).lower()


def same(a, b):
    na, nb = norm(a), norm(b)
    return bool(na) and bool(nb) and (na == nb or na.startswith(nb) or nb.startswith(na))


def main():
    raw = io.open(SRC, 'rb').read()
    txt = raw.decode('utf-8', 'replace').replace(u'\r\n', u'\n')
    cur = sorted(f[:-4] for f in os.listdir(CUR_DIR) if f.endswith(u'.txt'))

    ops = list(OPENER.finditer(txt))
    print(u'源：%s' % SRC)
    print(u'  %d 字节 / %d 字符 / 长块开头命中 %d 处' % (len(raw), len(txt), len(ops)))
    print()

    recs = []
    for i, m in enumerate(ops):
        end = ops[i + 1].start() if i + 1 < len(ops) else len(txt)
        seg = txt[m.start():end]
        # 去掉尾部的"下一份开场白"（它属于下一个角色）
        seg = NEXT_HEADER.split(seg)[0]
        # 切长/短
        sm = SHORT_OPEN.search(seg)
        if sm:
            longp, shortp = seg[:sm.start()], seg[sm.start():]
        else:
            longp, shortp = seg, u''
        recs.append({
            'work': m.group(1).strip(),
            'name': m.group(2).strip(),
            'long_chars': len(longp.strip()),
            'short_chars': len(shortp.strip()),
            'sections': SEC_RE.findall(longp),
            'short_said_as': (SHORT_OPEN.search(seg).group(1).strip() if sm else u''),
        })

    print(u'%-4s %-12s %-22s %7s %7s  %s' % (u'#', u'作品', u'角色名', u'正文字数', u'要点', u'段落'))
    print(u'-' * 92)
    for i, r in enumerate(recs, 1):
        print(u'%-4d %-12s %-22s %7d %7d  %s' % (
            i, r['work'], r['name'], r['long_chars'], r['short_chars'],
            u'/'.join(r['sections'][:3]) + (u'…' if len(r['sections']) > 3 else u'')))

    # ---- 判据
    total = sum(r['long_chars'] + r['short_chars'] for r in recs)
    header = len(txt) - total
    shorts = [m.group(1).strip() for m in SHORT_OPEN.finditer(txt)]
    print()
    print(u'[判据 A1] 长块（完整人设）= %d' % len(recs))
    bad_name = [r['name'] for r in recs if (not r['name']) or u'角色扮演' in r['name']]
    print(u'[判据 A2] 角色名异常 = %r' % (bad_name,))
    print(u'[判据 A3] 长+短合计 %d 字，源 %d 字 ⇒ 未覆盖 %d 字（%.1f%%，应≈文件头+---分隔线）'
          % (total, len(txt), header, 100.0 * header / len(txt)))
    print(u'[判据 A4] 短块（回应要点）= %d  ⇒ %s'
          % (len(shorts), u'配对完整' if len(shorts) == len(recs) else u'★ 不配对，见下'))
    if len(shorts) != len(recs):
        longn = [r['name'] for r in recs]
        orphan = [s for s in shorts if not any(same(s, n) for n in longn)]
        mult = {}
        for s in shorts:
            mult[s] = mult.get(s, 0) + 1
        print(u'      ★ 有短块但没有长块的角色名 = %r' % (orphan,))
        print(u'      ★ 短块里出现多次的名字 = %r'
              % ([k for k, v in mult.items() if v > 1],))
    print(u'[判据 A5 负控制] 替掉关键词后再搜长块开头 -> %d 命中（应为 0）'
          % len(OPENER.findall(txt.replace(u'你将完全以', u'ZZZ'))))
    print(u'[判据 A6 负控制] 搜不存在的角色名「ZZZ不存在」 -> %d 命中（应为 0）'
          % txt.count(u'ZZZ不存在'))

    # ---- 按作品分组
    byw = {}
    for r in recs:
        byw.setdefault(r['work'], []).append(r['name'])
    print()
    print(u'=== 按作品分组 ===')
    for w in sorted(byw):
        print(u'  《%s》 %d 人：%s' % (w, len(byw[w]), u', '.join(byw[w])))

    # ---- 与仓库 diff（按归一化 + 前缀匹配）
    cur = sorted(f[:-4] for f in os.listdir(CUR_DIR) if f.endswith(u'.txt'))
    used = set()
    miss = []
    for r in recs:
        hit = next((c for c in cur if same(r['name'], c)), None)
        if hit:
            used.add(hit)
        else:
            miss.append(r['name'])
    extra = [c for c in cur if c not in used]
    print()
    print(u'=== diff vs 仓库 %d 份 persona ===' % len(cur))
    print(u'  仓库已有（%d）：%s' % (len(used), u', '.join(sorted(used))))
    print(u'  ★ 源里有、仓库【没有】（%d）：%s' % (len(miss), u', '.join(miss)))
    print(u'  仓库里有、源里没有（%d）：%s' % (len(extra), u', '.join(extra)))

    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    art = {'source': SRC, 'source_bytes': len(raw), 'source_chars': len(txt),
           'opener_hits': len(ops), 'characters': recs,
           'by_work': {k: v for k, v in byw.items()},
           'existing_personas': cur, 'missing_in_repo': miss, 'extra_in_repo': extra,
           'uncovered_chars': header}
    p = os.path.join(EVID, u'personas64.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(art, ensure_ascii=False, indent=1))
    print()
    print(u'证据 -> %s' % p)
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())
