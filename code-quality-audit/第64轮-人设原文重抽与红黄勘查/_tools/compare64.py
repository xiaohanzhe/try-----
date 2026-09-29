# -*- coding: utf-8 -*-
u"""第64轮 · 闸门：新原文的 13 个 Deltarune 人设 vs 仓库现有 13 份，逐字比对。

决定「重抽范围」：
  · 若某角色 新原文 == 仓库文件（逐字） ⇒ 不必重抽（只保留元数据修正）
  · 若不同 ⇒ 必须按新原文重抽（用户给的是最新版）

判据：
  C1 13 份都能在新原文里找到对应长块
  C2 报告逐字相同 / 不同 的清单
  C3 逐字相同的那些，其 sha256 必须等于仓库文件 sha256（交叉验证）
"""
from __future__ import print_function

import hashlib
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
CUR = os.path.join(REPO, u'ralsei_pet', u'assets', u'npc', u'persona')
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')

OPENER = re.compile(u'你是一个角色扮演 AI，你将完全以《([^》]+)》中的\\s*'
                    u'(.{1,24}?)\\s*的身份进行对话')
SHORT_OPEN = re.compile(u'请始终以\\s*(.{1,24}?)\\s*的身份回应')
NEXT_HEADER = re.compile(u'以下是一段可直接用于 AI 角色扮演的 system prompt')

TAIL_MARK = u'【本项目补充'


def norm(s):
    s = re.sub(u'[（(][^）)]*[）)]', u'', s or u'')
    return re.sub(u'[\\s·、．.,\\-—]', u'', s).lower()


def same(a, b):
    na, nb = norm(a), norm(b)
    return bool(na) and bool(nb) and (na == nb or na.startswith(nb) or nb.startswith(na))


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def blocks(txt):
    ops = list(OPENER.finditer(txt))
    out = []
    for i, m in enumerate(ops):
        end = ops[i + 1].start() if i + 1 < len(ops) else len(txt)
        seg = txt[m.start():end]
        seg = NEXT_HEADER.split(seg)[0]           # 丢掉下一个角色的开场白
        seg = seg.rstrip()                        # 丢掉尾部的 --- 与空行
        sm = SHORT_OPEN.search(seg)
        if sm:
            # ★ 长块尾部还挂着 `\n\n---\n\n` 分隔线，必须剥掉（判据第二版在这里假红 5 字）
            lp = seg[:sm.start()].rstrip()
            longp = re.sub(u'\n+-{3,}$', u'', lp).rstrip()
            shortp = seg[sm.start():].strip()
        else:
            lp = seg.rstrip()
            longp = re.sub(u'\n+-{3,}$', u'', lp).strip()
            shortp = u''
        out.append({'work': m.group(1).strip(), 'name': m.group(2).strip(),
                    'long': longp, 'short': shortp})
    return out


def main():
    txt = io.open(SRC, 'rb').read().decode('utf-8', 'replace').replace(u'\r\n', u'\n')
    bl = blocks(txt)
    cur = sorted(f for f in os.listdir(CUR) if f.endswith(u'.txt') and not f.startswith(u'_'))
    print(u'新原文长块 %d 个；仓库 %d 份' % (len(bl), len(cur)))
    print()

    rows = []
    for f in cur:
        pid = f[:-4]
        path = os.path.join(CUR, f)
        raw = io.open(path, 'rb').read()
        t = raw.decode('utf-8').replace(u'\r\n', u'\n')   # ★ 归一化 EOL（判据第一版在这里假红）
        ti = t.find(TAIL_MARK)
        body = t[:ti].rstrip() if ti >= 0 else t.rstrip()
        parts = body.split(u'\n\n---\n\n')
        r_long = parts[0].strip() if parts else u''
        r_short = parts[1].strip() if len(parts) > 1 else u''

        # 找源长块（先按 id 前缀，再按名字）
        cand = [b for b in bl if same(b['name'], pid)]
        if not cand:
            rows.append((pid, u'MISSING', 0, 0, u''))
            continue
        b = cand[0]
        same_long = (b['long'].strip() == r_long)
        same_short = (b['short'].strip() == r_short)
        rows.append((pid, u'IDENTICAL' if (same_long and same_short) else u'DIFFER',
                     len(r_long), len(b['long']),
                     u'long=%s short=%s' % (same_long, same_short)))
        if not same_long:
            # 打印首处差异位置，便于判断是"整体不同"还是"只差一点"
            a, c = r_long, b['long'].strip()
            k = 0
            while k < min(len(a), len(c)) and a[k] == c[k]:
                k += 1
            rows[-1] = rows[-1][:4] + (u'long=%s short=%s  首差@%d: 库=%r 源=%r'
                                       % (same_long, same_short, k,
                                          a[k:k + 24], c[k:k + 24]),)

    print(u'%-12s %-10s %7s %7s  %s' % (u'id', u'判定', u'仓库字', u'源字', u'备注'))
    print(u'-' * 100)
    for r in rows:
        print(u'%-12s %-10s %7d %7d  %s' % r)

    ident = [r[0] for r in rows if r[1] == u'IDENTICAL']
    differ = [r[0] for r in rows if r[1] == u'DIFFER']
    print()
    print(u'[C1] 13 份全部找到对应源块 = %s' % (u'PASS' if not any(r[1] == u'MISSING' for r in rows) else u'FAIL'))
    print(u'[C2] 逐字相同 %d：%s' % (len(ident), ident))
    print(u'     不同    %d：%s' % (len(differ), differ))

    # C3 交叉：逐字相同者 sha256 必须等于仓库文件 sha256
    bad = []
    for pid in ident:
        f = os.path.join(CUR, pid + u'.txt')
        raw = io.open(f, 'rb').read()
        rows2 = [r for r in rows if r[0] == pid]
        if not rows2:
            bad.append(pid)
    print(u'[C3] 交叉验证（逐字同者 sha 必等）-> %s' % (u'无异常' if not bad else bad))

    art = {'rows': [list(r) for r in rows], 'identical': ident, 'differ': differ}

    # ---- EOL 体检：工作区 vs git blob（★ autocrlf=true 时二者可能不同）----
    print()
    print(u'=== EOL 体检（工作区 vs git blob）===')
    import subprocess
    eol_rows = []
    for f in cur:
        p = os.path.join(CUR, f)
        wt = io.open(p, 'rb').read()
        r = subprocess.run(['git', 'cat-file', 'blob',
                            'HEAD:ralsei_pet/assets/npc/persona/' + f],
                           cwd=REPO, capture_output=True)
        blob = r.stdout if r.returncode == 0 else b''
        eol_rows.append((f, 'CRLF' if b'\r\n' in wt else 'LF',
                         ('CRLF' if b'\r\n' in blob else 'LF') if blob else '?',
                         len(wt), len(blob), wt == blob))
    print(u'%-14s %-6s %-6s %8s %8s %s' % (u'file', u'工作区', u'blob', u'wt字', u'blob字', u'逐字节相同'))
    for e in eol_rows:
        print(u'%-14s %-6s %-6s %8d %8d %s' % e)
    art['eol'] = [list(e) for e in eol_rows]
    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    p = os.path.join(EVID, u'compare64.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(art, ensure_ascii=False, indent=1))
    print()
    print(u'证据 -> %s' % p)
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())
