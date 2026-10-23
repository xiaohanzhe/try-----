# -*- coding: utf-8 -*-
"""第一百一十三轮 · 关系叙述入库（只读分析 + 归档，不改产品代码）

用户 2026-10-24 给了两份真源：
  * `C:\\Users\\23002\\Desktop\\其余人物设定.txt`（1,369,264 B，已用于重建 6 份主线人设）
  * `C:\\Users\\23002\\Desktop\\人物关系叙述.txt`（40,845 B，19,267 字，5 部作品的**关系总纲**）

本脚本只做三件事：
  1. 把关系总纲**逐字节**归档进仓库（`assets/npc/_relations/relations_source.txt`），
     算 sha256，防止桌面上那份被改/丢。
  2. 切成「作品 → 小节」两层，按 96 人名单匹配出每节涉及哪些角色 ⇒ `_index.json`。
     ⇒ 以后某个 NPC 想知道"我和 X 什么关系"，可直接 `by_npc['kris']` 取原文段落。
  3. 出人读报告 `_evidence/relations113.md`：覆盖率、跨作品重名、没被提到的角色。

⚠️ 本脚本**不写** `persona/*.txt`、**不改** `build_system_prompt`。
   训练正在跑，此刻动 prompt 会让 baseline / patch 两阶段口径不一致。
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))     # 仓库根 = try - 副本/
PET = os.path.join(ROOT, 'ralsei_pet')
NPC_DIR = os.path.join(PET, 'assets', 'npc')
OUT_DIR = os.path.join(NPC_DIR, '_relations')
EV_DIR = os.path.abspath(os.path.join(HERE, '..', '_evidence'))

SRC = r'C:\Users\23002\Desktop\人物关系叙述.txt'

# 作品分界：标题行文本 → (key, 标题, id 前缀)
WORKS = [
    ('Deltarune：', 'deltarune', 'Deltarune', ''),
    ('Oneshot：', 'oneshot', 'Oneshot', 'os_'),
    ('Undertale：', 'undertale', 'Undertale', 'ut_'),
    ('黄魂：', 'yellow', 'Undertale Yellow（黄魂）', 'hy_'),
    ('Outertale：', 'outertale', 'Outertale', 'ot_'),
]

SEC_RE = re.compile(r'^([一二三四五六七八九十]+)、\s*(.+)$')

#: 长名字的单个词也当别名（`Asgore Dreemurr` → 文件里只写 `Asgore`）。
#: 但通用词必须排除，否则 `Monster Kid` 会把满篇的 "monster" 全算命中。
ALIAS_MIN_LEN = 5
ALIAS_BLACKLIST = {
    'Monster', 'World', 'Machine', 'Author', 'Entity', 'Player',
    'Story', 'Knight', 'Roaring', 'Dreemurr',
}
#: 登记名与正文写法对不上时手工补（`Roaring Knight` 正文只写“骑士”）。
EXTRA_ALIASES = {
    'knight': ['骑士'],
}


def read_raw(path):
    """逐字节忠实读（不转 newline），返回 (text_lf, sha256, bytes)。"""
    with open(path, 'rb') as f:
        raw = f.read()
    text = raw.decode('utf-8-sig')
    return text.replace('\r\n', '\n'), hashlib.sha256(raw).hexdigest(), len(raw)


def load_npcs():
    with io.open(os.path.join(NPC_DIR, '_registry.json'), encoding='utf-8') as f:
        d = json.load(f)
    return d['npcs']


def names_of(npc):
    """一个 NPC 的可匹配名字集合。`ot_asriel_twinkly` 这种带 '与' 的拆开。"""
    out = set()
    for raw in (npc.get('name') or '', npc.get('name_cn') or ''):
        for part in re.split(r'\s+与\s+|/', raw):
            p = part.strip()
            if len(p) >= 2:
                out.add(p)
            for word in p.split():
                w = word.strip('.,')
                if len(w) >= ALIAS_MIN_LEN and w not in ALIAS_BLACKLIST:
                    out.add(w)
    for a in EXTRA_ALIASES.get(npc['id'], ()):
        out.add(a)
    return out


def match_npcs(text, pool):
    """返回本节命中的 npc_id 列表（保持 pool 顺序，便于复算）。"""
    hits = []
    for npc in pool:
        for nm in names_of(npc):
            if nm.isascii():
                if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(nm), text):
                    hits.append(npc['id'])
                    break
            else:
                if nm in text:
                    hits.append(npc['id'])
                    break
    return hits


def split_works(text):
    """按作品标题行切块。返回 [(key, title, prefix, body, start_line), ...]"""
    lines = text.split('\n')
    marks = []
    for i, line in enumerate(lines):
        t = line.strip()
        for marker, key, title, prefix in WORKS:
            if t == marker:
                marks.append((i, key, title, prefix))
    out = []
    for idx, (i, key, title, prefix) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        out.append((key, title, prefix, '\n'.join(lines[i + 1:end]), i + 1))
    return out


def split_sections(body, base_line):
    """作品内部再按 '一、' 切小节。返回 [{'heading','line','text'}]"""
    lines = body.split('\n')
    marks = []
    for i, line in enumerate(lines):
        m = SEC_RE.match(line.strip())
        if m:
            marks.append((i, line.strip()))
    secs = []
    for idx, (i, heading) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        chunk = '\n'.join(lines[i + 1:end]).strip()
        chunk = re.sub(r'\n*---\n*', '\n', chunk).strip()
        secs.append({'heading': heading, 'line': base_line + i, 'text': chunk})
    return secs


def main(argv=None):
    dry = '--dry' in (argv or sys.argv[1:])
    if not os.path.isfile(SRC):
        print('[FAIL] 源文件不存在：%s' % SRC, flush=True)
        return 2
    text, sha, nbytes = read_raw(SRC)
    print('源：%s' % SRC, flush=True)
    print('  bytes=%d  chars=%d  sha256=%s' % (nbytes, len(text), sha[:16],), flush=True)

    npcs = load_npcs()
    by_prefix = {'': [n for n in npcs if not any(
        n['id'].startswith(p) for p in ('os_', 'hy_', 'ut_', 'ot_'))]}
    for p in ('os_', 'hy_', 'ut_', 'ot_'):
        by_prefix[p] = [n for n in npcs if n['id'].startswith(p)]

    works = []
    by_npc = {}
    for key, title, prefix, body, start in split_works(text):
        pool = by_prefix.get(prefix, [])
        secs = split_sections(body, start)
        w_hits = set()
        for s in secs:
            s['npcs'] = match_npcs(s['heading'] + '\n' + s['text'], pool)
            w_hits.update(s['npcs'])
            for nid in s['npcs']:
                by_npc.setdefault(nid, []).append(
                    {'work': key, 'heading': s['heading'], 'line': s['line']})
        works.append({
            'key': key, 'title': title, 'prefix': prefix,
            'line': start, 'sections': secs, 'npcs': sorted(w_hits),
        })
        print('  [%-10s] 行 %-4d 小节 %-2d 命中角色 %d/%d'
              % (key, start, len(secs), len(w_hits), len(pool)), flush=True)

    total = len(npcs)
    covered = len(by_npc)
    print('覆盖：%d/%d 人被关系总纲提到（%d 人没提到）'
          % (covered, total, total - covered), flush=True)
    miss = [n['id'] for n in npcs if n['id'] not in by_npc]
    print('  未提到：%s' % (', '.join(miss) if miss else '（无）'), flush=True)

    if dry:
        print('[dry] 不写盘。', flush=True)
        return 0

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    dst = os.path.join(OUT_DIR, 'relations_source.txt')
    shutil.copyfile(SRC, dst)
    with open(dst, 'rb') as f:
        sha2 = hashlib.sha256(f.read()).hexdigest()
    same = (sha2 == sha)
    print('归档：%s  同源=%s' % (dst, same), flush=True)

    index = {
        'schema_version': 1,
        'source': {'from': SRC, 'archived': 'relations_source.txt',
                   'bytes': nbytes, 'chars': len(text), 'sha256': sha},
        'works': works,
        'by_npc': by_npc,
        'coverage': {'total': total, 'covered': covered, 'missing': miss},
    }
    ipath = os.path.join(OUT_DIR, '_index.json')
    with io.open(ipath, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print('索引：%s  %.1f KB' % (ipath, os.path.getsize(ipath) / 1024), flush=True)

    # ---------------- 人读报告 ----------------
    L = []
    L.append('# 第一百一十三轮 · 关系叙述入库')
    L.append('')
    L.append('> 源：`%s`（%.0f KB / %d 字，sha256 `%s`）' %
             ('C:\\Users\\23002\\Desktop\\人物关系叙述.txt', nbytes / 1024, len(text), sha[:16]))
    L.append('> 归档：`ralsei_pet/assets/npc/_relations/relations_source.txt`（逐字节复制，同源=%s）' % same)
    L.append('> 索引：`ralsei_pet/assets/npc/_relations/_index.json`')
    L.append('')
    L.append('## 一、五部作品 × 小节')
    L.append('')
    L.append('| 作品 | 起始行 | 小节数 | 命中角色 | 该作品登记数 |')
    L.append('|---|---|---|---|---|')
    for w in works:
        L.append('| %s | %d | %d | %d | %d |'
                 % (w['title'], w['line'], len(w['sections']), len(w['npcs']),
                    len(by_prefix.get(w['prefix'], []))))
    L.append('')
    L.append('## 二、逐节清单')
    for w in works:
        L.append('')
        L.append('### %s' % w['title'])
        for s in w['sections']:
            L.append('- **%s**（行 %d）：%s' %
                     (s['heading'], s['line'],
                      ', '.join('`%s`' % n for n in s['npcs']) or '（未匹配到登记角色）'))
    L.append('')
    L.append('## 三、覆盖')
    L.append('')
    L.append('- 登记 **%d** 人，被总纲提到 **%d** 人（%.1f%%）。'
             % (total, covered, covered * 100.0 / total))
    L.append('- 未提到 **%d** 人：%s' % (len(miss), ', '.join('`%s`' % m for m in miss) or '（无）'))
    L.append('')
    L.append('## 四、跨作品重名')
    L.append('')
    L.append('同一名字在多个作品出现时，索引**按作品内候选池**匹配，不会串味：')
    L.append('')
    L.append('| 名字 | 出现的作品 |')
    L.append('|---|---|')
    seen = {}
    for w in works:
        for s in w['sections']:
            for nid in s['npcs']:
                seen.setdefault(nid.split('_')[0] if '_' in nid else nid, set()).add(w['key'])
    dup = {k: v for k, v in seen.items() if len(v) >= 2}
    for k in sorted(dup):
        L.append('| `%s` | %s |' % (k, ', '.join(sorted(dup[k]))))
    if not dup:
        L.append('| （无） | |')
    L.append('')
    L.append('## 五、下一步（未做，留作下一轮）')
    L.append('')
    L.append('1. 把 `by_npc[id]` 的段落接进 `npc_persona.build_system_prompt` 的「人际关系」块，')
    L.append('   与现有 `relations()`（从人设抽）**合并去重**，而不是替换。')
    L.append('2. 接入前必须跑 `check113` C 组（prompt 契约），确认无 patch 时仍与第112轮逐字相同。')
    L.append('')

    if not os.path.isdir(EV_DIR):
        os.makedirs(EV_DIR)
    rpath = os.path.join(EV_DIR, 'relations113.md')
    with io.open(rpath, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L))
    print('报告：%s' % rpath, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
