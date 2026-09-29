# -*- coding: utf-8 -*-
u"""第64轮 · 定稿抽取器：把《其余人物设定.txt》的 50 份人设抽成 `assets/npc/persona/*.txt`。

设计（每条都有理由）：
  · 抽出的文件格式 **必须与已有 13 份逐字一致** ⇒ 用「重放已有 13 份」当**正控制**，
    13/13 通过才算抽取器可信（这是本轮唯一能证伪抽取正确性的办法）。
  · 尾部「本项目补充」块**从现有 `_personas.json` 的 `tail_text` 原样读**，
    不重新手打（避免两处真源不一致）。
  · 只**新增**文件，绝不覆盖已有 13 份（改动最小）。
  · `--write` 才落盘；默认 dry-run。

★ 本轮踩到的两个「判据过窄」（都写进报告）：
  1. 开场白正则的 `.{1,24}?` 名字上限太小 ⇒ 漏掉 `The World Machine（又称 The Entity / 本体）`
     （33 字）⇒ 误判成 49 份。放宽到 60。
  2. 比对时没归一化 EOL ⇒ 13/13 假红；没剥长块尾部 `---` ⇒ 13/13 假红。
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
NPC = os.path.join(REPO, u'ralsei_pet', u'assets', u'npc')
CUR = os.path.join(NPC, u'persona')
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')

OPENER = re.compile(u'你是一个角色扮演 AI，你将完全以《([^》]+)》中的\\s*'
                    u'(.{1,60}?)\\s*的身份进行对话')          # ★ 24 -> 60
SHORT_OPEN = re.compile(u'请始终以\\s*(.{1,60}?)\\s*的身份回应')
NEXT_HEADER = re.compile(u'以下是一段可直接用于 AI 角色扮演的 system prompt')
SEC_RE = re.compile(u'【([^】]{2,14})】')
TAIL_MARK = u'【本项目补充'

#: 已有 13 份：源名 -> 现有 id（一字不改地沿用，避免动到既有契约）
EXISTING = [u'susie', u'kris', u'asgore', u'toriel', u'lancer', u'king', u'queen',
            u'berdly', u'noelle', u'tenna', u'rouxls', u'gerson', u'flowery']

#: 新 id 规则：Deltarune 沿用 registry 已定的 id；跨界一律带工作前缀（防跨作品同名撞车）
OS_ID = {
    u'Niko': u'os_niko', u'The Author': u'os_the_author', u'ProphetBot': u'os_prophetbot',
    u'Silver': u'os_silver', u'Rowbot': u'os_rowbot', u'Prototype': u'os_prototype',
    u'Calamus': u'os_calamus', u'Alula': u'os_alula', u'Maize': u'os_maize',
    u'Magpie': u'os_magpie', u'Shepherd': u'os_shepherd', u'Cedric': u'os_cedric',
    u'Lamplighter': u'os_lamplighter', u'Watcher': u'os_watcher', u'Ling': u'os_ling',
    u'Mason': u'os_mason', u'Kelvin': u'os_kelvin', u'Kip': u'os_kip',
    u'George': u'os_george', u'Rue': u'os_rue',
    u'The World Machine': u'os_the_world_machine',
}
UT_ID = {
    u'Toriel': u'ut_toriel', u'Sans': u'ut_sans', u'Papyrus': u'ut_papyrus',
    u'Undyne': u'ut_undyne', u'Alphys': u'ut_alphys', u'Mettaton': u'ut_mettaton',
    u'Muffet': u'ut_muffet', u'Napstablook': u'ut_napstablook',
    u'Monster Kid': u'ut_monster_kid', u'Asgore Dreemurr': u'ut_asgore',
    u'Flowey': u'ut_flowey', u'Frisk': u'ut_frisk', u'Chara': u'ut_chara',
    u'W.D. Gaster': u'ut_gaster',
}
DR_ID = {u'Spamton G. Spamton': u'spamton', u'Mike': u'mike',
         # ★ 源里的全名 -> 仓库沿用已久的短 id（不匹配就会误判成"新角色"）
         u'Asgore Dreemurr': u'asgore', u'Noelle Holiday': u'noelle',
         u'Rouxls Kaard': u'rouxls', u'Gerson Boom': u'gerson'}


def norm_name(s):
    s = re.sub(u'[（(][^）)]*[）)]', u'', s or u'')
    return re.sub(u'[\\s·、．.,\\-—]', u'', s).lower()


def slug_of(work, name):
    n = re.sub(u'[（(][^）)]*[）)]', u'', name).strip()
    if work == u'Deltarune':
        for k, v in DR_ID.items():
            if norm_name(k) == norm_name(n):
                return v
        for e in EXISTING:
            if norm_name(e) == norm_name(n):
                return e
        return re.sub(u'[^a-z0-9]+', u'_', n.lower()).strip(u'_')
    if work == u'OneShot':
        for k, v in OS_ID.items():
            if norm_name(k) == norm_name(n):
                return v
    if work == u'Undertale':
        for k, v in UT_ID.items():
            if norm_name(k) == norm_name(n):
                return v
    return work.lower() + u'_' + re.sub(u'[^a-z0-9]+', u'_', n.lower()).strip(u'_')


def blocks(txt):
    ops = list(OPENER.finditer(txt))
    out = []
    for i, m in enumerate(ops):
        end = ops[i + 1].start() if i + 1 < len(ops) else len(txt)
        seg = txt[m.start():end]
        # 「下一份的开场白」= 下一个角色的 preamble，本段不含它
        seg = NEXT_HEADER.split(seg)[0]
        seg = seg.rstrip()
        sm = SHORT_OPEN.search(seg)
        if sm:
            lp = seg[:sm.start()].rstrip()
            longp = re.sub(u'\n+-{3,}$', u'', lp).rstrip()
            shortp = seg[sm.start():].strip()
        else:
            lp = seg.rstrip()
            longp = re.sub(u'\n+-{3,}$', u'', lp).strip()
            shortp = u''
        # ★ 守卫：一段里若出现**第二个**「请始终以…回应」，说明又有一个角色缺开场白
        #    —— 本轮就是这样漏掉 The World Machine 的（判据过窄）。留着当探针。
        n_short = len(SHORT_OPEN.findall(txt[m.start():end]))
        if sm:
            n_short -= 1
        out.append({'work': m.group(1).strip(), 'name': m.group(2).strip(),
                    'long': longp, 'short': shortp,
                    'stray_short': n_short,
                    'sections': SEC_RE.findall(longp)})
    return out


def sha256_of(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def main(argv):
    write = u'--write' in argv
    raw = io.open(SRC, 'rb').read()
    txt = raw.decode('utf-8', 'replace').replace(u'\r\n', u'\n')

    old_index = json.loads(io.open(os.path.join(NPC, u'_personas.json'), 'rb')
                           .read().decode('utf-8'))
    TAIL = old_index[u'tail_text']
    print(u'尾部补充块：%d 字（取自现有 _personas.json 的 tail_text）' % len(TAIL))
    print()

    bl = blocks(txt)
    print(u'[A1] 长块 = %d' % len(bl))
    bad = [b['name'] for b in bl if not b['name'] or u'角色扮演' in b['name']]
    print(u'[A2] 角色名异常 = %r' % bad)
    names = [b['name'] for b in bl]
    dup = [n for n in set(names) if names.count(n) > 1]
    print(u'[A3] 重名 = %r （跨作品同名是预期的）' % dup)
    stray = [(b['name'], b['stray_short']) for b in bl if b['stray_short']]
    print(u'[A4] 段内残留短块（应空）= %r' % stray)
    byw = {}
    for b in bl:
        byw.setdefault(b['work'], []).append(b['name'])
    for w in sorted(byw):
        print(u'      《%s》 %d 人' % (w, len(byw[w])))

    # ---------- 正控制：重放已有 13 份 ----------
    print()
    print(u'=== 正控制：抽取器必须逐字复现已有 13 份 ===')
    okc, failc = 0, []
    for b in bl:
        sid = slug_of(b['work'], b['name'])
        if sid not in EXISTING:
            continue
        fp = os.path.join(CUR, sid + u'.txt')
        cur = io.open(fp, 'rb').read().decode('utf-8').replace(u'\r\n', u'\n')
        built = b['long'] + u'\n\n---\n\n' + b['short'] + u'\n\n' + TAIL + u'\n'
        if built == cur:
            okc += 1
            print(u'  [PASS] %-10s %d 字' % (sid, len(built)))
        else:
            k = 0
            while k < min(len(cur), len(built)) and cur[k] == built[k]:
                k += 1
            failc.append((sid, k, repr(cur[k:k + 30]), repr(built[k:k + 30])))
            print(u'  [FAIL] %-10s 首差@%d  库=%s 重建=%s' % (sid, k, cur[k:k + 30], built[k:k + 30]))
    print(u'  => %d PASS / %d FAIL' % (okc, len(failc)))
    if failc:
        print(u'★ 正控制未过 ⇒ 抽取格式与既有文件不一致，**停止落盘**')
        return 3

    # ---------- 计划：新增哪些 ----------
    print()
    print(u'=== 计划新增 ===')
    plan = []
    for b in bl:
        sid = slug_of(b['work'], b['name'])
        if sid in EXISTING:
            continue
        plan.append((sid, b))
    print(u'共 %d 份新增：' % len(plan))
    for sid, b in plan:
        print(u'  %-24s %-12s %-24s %7d 字  %s' % (
            sid, b['work'], b['name'], len(b['long']),
            u'/'.join(b['sections'][:2])))
    unpicked = [c[:-4] for c in os.listdir(CUR)
                if c.endswith(u'.txt') and c[:-4] not in [p[0] for p in plan] + EXISTING]
    print(u'[C1] 未被计划覆盖的目录内其它 .txt（应为空）= %r' % unpicked)

    if not write:
        print()
        print(u'（dry-run，未落盘。加 --write 才写。）')
        return 0

    # ---------- 落盘 ----------
    print()
    print(u'=== 落盘 ===')
    wrote = []
    for sid, b in plan:
        body = b['long'] + u'\n\n---\n\n' + b['short'] + u'\n\n' + TAIL + u'\n'
        # ★ 与既有 13 份**同构**：正文用 CRLF，尾部「本项目补充」块用 LF
        #   （第55轮的写入器就是这样拼的；实测 13 份里 12 份如此，flowery 是手改过的例外）
        head = (b['long'] + u'\n\n---\n\n' + b['short']).replace(u'\n', u'\r\n')
        disk = (head + u'\n\n' + TAIL + u'\n').encode('utf-8')
        fp = os.path.join(CUR, sid + u'.txt')
        if os.path.exists(fp):
            print(u'  !! 已存在，跳过（绝不覆盖）：%s' % fp)
            continue
        with io.open(fp, u'wb') as fh:
            fh.write(disk)
        wrote.append((sid, len(disk), hashlib.sha256(disk).hexdigest()))
    for w in wrote:
        print(u'  写入 %-24s %7d 字节  %s' % w)
    print(u'  共写 %d 个文件' % len(wrote))
    return 0


if __name__ == u'__main__':
    raise SystemExit(main(sys.argv[1:]))
