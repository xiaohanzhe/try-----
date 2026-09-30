# -*- coding: utf-8 -*-
"""第69轮 · 人设数据面重建：从用户新版《其余人物设定.txt》抽 76 份 persona。

背景（用户第69轮原话）
----------------------
> 「…**这些是新添加的设定有些有改动**…」
> 「…注意，**之前的人设物我有些做了改动，你记得别落下了**」

实证：`assets/npc/_personas.json` 记录的源文件是 **785,360 B**，而磁盘上的
`其余人物设定.txt` 现为 **1,303,723 B**（+66%）⇒ **确实被改过**，不能沿用旧产物。

口径（与第64轮一致，保持不变的部分）
----------------------------------
* 正文 = 每份从 `你是一个角色扮演 AI…` 起、到下一份该行之前（**剥掉**前言
  「以下是一段可直接用于…」与 `---` 分隔线，与 `_personas.json` 的 note 一致）；
* 每份尾部**统一**追加「本项目补充 —— 桌宠运行口径」块（复用 `_personas.json.tail_text`，
  **单一真源**，不在这里重写一份）；
* 文件名 = `<id>.txt`，id 规则：Deltarune 无前缀 / OneShot `os_` / Undertale `ut_` /
  **黄魂（UT Yellow·Red & Yellow）`hy_`**（新）/ **Outertale `ot_`**（新）。

★★★ 换行风格：必须**逐字节复现**历史形态（第69轮踩坑记录）
-----------------------------------------------------------
首版 `--write` 用 `newline='\r\n'` 把 76 份**全写成 CRLF**，结果 50 条旧记录里 47 条的
`bytes`/`chars`/`sha256` 全部与 `_personas.json` 不符（各差 +8 / +9），
而 `sha256_lf` 不变 —— 典型"**记录与事实脱节**"。

根因（用 HEAD blob + 旧索引 hash 反推坐实的，见 `_tools/probe_rule69.py`）：
仓库 `autocrlf=true` ⇒ **blob 一律是 LF**，但**工作区历史上有两种风格**：

* `2lf`（第64轮系，35 条 hy_*/ot_*/ut_*/os_*）：`正文(CRLF) + '\n\n' + 尾块(LF) + '\n'`
* `1lf`（第55轮系，12 条 Deltarune：asgore/berdly/gerson/king/kris/lancer/
  noelle/queen/rouxls/susie/tenna/toriel）：`正文(CRLF) + '\r\n\n' + 尾块(LF) + '\n'`

两者**视觉完全一样**、clean 成 blob 后**字节完全相同**（所以 `git status` 只报 3 个 M），
差别只在"尾块前那个换行是 CRLF 还是裸 LF"。

⇒ 本工具**不猜**：拿旧索引记的 `sha256` 当硬真值，逐个试两种风格，命中哪个用哪个；
新记录（索引里没有）默认用 `2lf`（第64轮系）。
⇒ 于是 47 条**逐字节**复现、索引差异只剩「3 改 + 26 新」，历史 hash 全部继续有效。

★★ 为什么用**序号 + 强断言**而不是"按名字自动映射"
--------------------------------------------------
76 份里重名极多（Toriel×3、Asgore×3、Flowey×3、Sans/Papyrus/Undyne/Alphys/Mettaton/
Muffet/Napstablook ×2），自动映射必然出错（首版实测就把 Outertale 的 Sans 映射到了
`ut_sans`、把 Tenna 当成了新增）。⇒ 这里显式列出 76 条期望表，
**每块的「作品名 + 角色名」必须命中期望**，错位立刻报红（源文件改版即失效）。

用法
----
    python _tools/extract_personas69.py            # dry：只对比，不写盘
    python _tools/extract_personas69.py --write    # 实际写盘
"""
import hashlib
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
N = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
PER = os.path.join(N, 'persona')
SRC = r'C:\Users\23002\Desktop\其余人物设定.txt'
EV = os.path.join(ROOT, 'code-quality-audit', '第69轮-人设数据面重建', '_evidence')

DO_WRITE = '--write' in sys.argv
FAIL = 0
LINES = []


def w(s=''):
    print(s)
    LINES.append(str(s))


def ok(m):
    w('[PASS] %s' % m)


def bad(m):
    global FAIL
    FAIL += 1
    w('[FAIL] %s' % m)


# ---------------------------------------------------------------------------
#  76 条期望表：(序号, 作品名关键词, 角色名关键词, id)
#  ★ 这份表是"事实的坐标"：源文件一改版，断言就会报红。
# ---------------------------------------------------------------------------
EXPECT = [
    (1, 'Deltarune', 'Susie', 'susie'),
    (2, 'Deltarune', 'Kris', 'kris'),
    (3, 'Deltarune', 'Asgore', 'asgore'),
    (4, 'Deltarune', 'Toriel', 'toriel'),
    (5, 'Deltarune', 'Lancer', 'lancer'),
    (6, 'Deltarune', 'King', 'king'),
    (7, 'Deltarune', 'Queen', 'queen'),
    (8, 'Deltarune', 'Berdly', 'berdly'),
    (9, 'Deltarune', 'Noelle', 'noelle'),
    (10, 'Deltarune', 'Tenna', 'tenna'),
    (11, 'Deltarune', 'Rouxls', 'rouxls'),
    (12, 'Deltarune', 'Gerson', 'gerson'),
    (13, 'Deltarune', 'Flowery', 'flowery'),
    (14, 'Deltarune', 'Spamton', 'spamton'),
    (15, 'Deltarune', 'Mike', 'mike'),
    (16, 'OneShot', 'Niko', 'os_niko'),
    (17, 'OneShot', 'World Machine', 'os_the_world_machine'),
    (18, 'OneShot', 'Author', 'os_the_author'),
    (19, 'OneShot', 'ProphetBot', 'os_prophetbot'),
    (20, 'OneShot', 'Silver', 'os_silver'),
    (21, 'OneShot', 'Rowbot', 'os_rowbot'),
    (22, 'OneShot', 'Prototype', 'os_prototype'),
    (23, 'OneShot', 'Calamus', 'os_calamus'),
    (24, 'OneShot', 'Alula', 'os_alula'),
    (25, 'OneShot', 'Maize', 'os_maize'),
    (26, 'OneShot', 'Magpie', 'os_magpie'),
    (27, 'OneShot', 'Shepherd', 'os_shepherd'),
    (28, 'OneShot', 'Cedric', 'os_cedric'),
    (29, 'OneShot', 'Lamplighter', 'os_lamplighter'),
    (30, 'OneShot', 'Watcher', 'os_watcher'),
    (31, 'OneShot', 'Ling', 'os_ling'),
    (32, 'OneShot', 'Mason', 'os_mason'),
    (33, 'OneShot', 'Kelvin', 'os_kelvin'),
    (34, 'OneShot', 'Kip', 'os_kip'),
    (35, 'OneShot', 'George', 'os_george'),
    (36, 'OneShot', 'Rue', 'os_rue'),
    (37, 'Undertale', 'Toriel', 'ut_toriel'),
    (38, 'Undertale', 'Sans', 'ut_sans'),
    (39, 'Undertale', 'Papyrus', 'ut_papyrus'),
    (40, 'Undertale', 'Undyne', 'ut_undyne'),
    (41, 'Undertale', 'Alphys', 'ut_alphys'),
    (42, 'Undertale', 'Mettaton', 'ut_mettaton'),
    (43, 'Undertale', 'Muffet', 'ut_muffet'),
    (44, 'Undertale', 'Napstablook', 'ut_napstablook'),
    (45, 'Undertale', 'Monster Kid', 'ut_monster_kid'),
    (46, 'Undertale', 'Asgore', 'ut_asgore'),
    (47, 'Undertale', 'Flowey', 'ut_flowey'),
    (48, 'Undertale', 'Frisk', 'ut_frisk'),
    (49, 'Undertale', 'Chara', 'ut_chara'),
    (50, 'Undertale', 'Gaster', 'ut_gaster'),
    (51, 'Yellow', 'Clover', 'hy_clover'),
    (52, 'Yellow', 'Flowey', 'hy_flowey'),
    (53, 'Yellow', 'Martlet', 'hy_martlet'),
    (54, 'Yellow', 'Ceroba', 'hy_ceroba_ketsukane'),
    (55, 'Yellow', 'Starlo', 'hy_starlo'),
    (56, 'Yellow', 'Ace', 'hy_ace'),
    (57, 'Yellow', 'Ed', 'hy_ed'),
    (58, 'Yellow', 'Mooch', 'hy_mooch'),
    (59, 'Yellow', 'Moray', 'hy_moray'),
    (60, 'Yellow', 'Dalv', 'hy_dalv'),
    (61, 'Yellow', 'Axis', 'hy_axis'),
    (62, 'Yellow', 'Sousborg', 'hy_sousborg'),
    (63, 'Yellow', 'Guardener', 'hy_guardener'),
    (64, 'Yellow', 'Chujin', 'hy_chujin_ketsukane'),
    (65, 'Yellow', 'Bowll', 'hy_bowll'),
    (66, 'Outertale', 'Asriel', 'ot_asriel_twinkly'),
    (67, 'Outertale', 'Undyne', 'ot_undyne'),
    (68, 'Outertale', 'Papyrus', 'ot_papyrus'),
    (69, 'Outertale', 'Mettaton', 'ot_mettaton'),
    (70, 'Outertale', 'Toriel', 'ot_toriel'),
    (71, 'Outertale', 'Asgore', 'ot_asgore'),
    (72, 'Outertale', 'Kidd', 'ot_kidd'),
    (73, 'Outertale', 'Sans', 'ot_sans'),
    (74, 'Outertale', 'Alphys', 'ot_alphys'),
    (75, 'Outertale', 'Napstablook', 'ot_napstablook'),
    (76, 'Outertale', 'Muffet', 'ot_muffet'),
]

#: 正文起点行（每份都以此行开头）
BODY_START = '你是一个角色扮演 AI'
#: 前言行的特征（要剥掉）
PREAMBLE_PAT = re.compile(r'^\s*(以下是一段可直接用于|旨在尽可能还原)')
#: 名字提取（宽松，三种写法都收）
NAME_PATS = (
    re.compile(r'以《([^》]+)》中的\s*(.+?)\s*的(?:双重)?身份进行对话'),
    re.compile(r'旨在尽可能还原《([^》]+)》中\s*(.+?)\s*的'),
)

#: ★★ 源文件的**数据残留**（用户粘贴瑕疵，第69轮实测）——
#: `其余人物设定.txt` 行 5139 起是 Gaster 的收尾，但 5146 出现一个**孤立的分区标题
#: `黄魂：`**，其后 5148~5154 是 **Clover 的语言风格片段**、5156 是空的 `【行为准则】`
#: （Clover 的正式正文从 5158 的「以下是一段可直接用于…」+ 5162 的 head 行才重新开始）。
#: 按"遇到下一 head 行才停"的规则，这 12 行会被算进 **Gaster** ⇒ 污染 Gaster 人设
#: （会让 Gaster 说起 "I reckon" / 自称 "Gun-Hat"）。
#: ⇒ 显式在这里**切断**（把隐式巧合变成显式规则），并在报告里如实登记该残留、请用户裁定。
CUT_AT = {'ut_gaster': '黄魂：'}
#: 负控制：切断后 Gaster 正文里**不得出现**这些串（它们是 Clover 的口头禅）
CUT_NEGCTRL = ('I reckon', 'Gun-Hat')

#: ★★★ 换行风格（见文件头"换行风格"一节）：`1lf` 只在**旧索引 sha256 命中**时使用
STYLE_ORDER = ('2lf', '1lf')
DEFAULT_STYLE = '2lf'
#: 本轮**应当**只有这 3 条内容真改；其余 47 条必须逐字节复现旧索引记的 sha256
EXPECT_CHANGED = {'ut_chara', 'ut_flowey', 'ut_toriel'}


def _extract(ln):
    for p in NAME_PATS:
        m = p.search(ln)
        if m:
            return m.group(1), m.group(2).strip()
    return None, None


def cut_blocks(lines):
    """→ [{'line':int,'work':str,'name':str,'body':str}]"""
    heads = []
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith(BODY_START):
            ws, nm = _extract(ln)
            if not ws:                      # 名字可能只在前 15 行
                for j in range(i - 2, max(-1, i - 16), -1):
                    ws, nm = _extract(lines[j])
                    if ws:
                        break
            heads.append({'line': i, 'work': ws, 'name': nm})
    for k, h in enumerate(heads):
        end = heads[k + 1]['line'] - 1 if k + 1 < len(heads) else len(lines)
        body = lines[h['line'] - 1:end]
        while body and (not body[-1].strip() or PREAMBLE_PAT.match(body[-1])
                        or body[-1].strip().startswith('---')):
            body.pop()
        h['body'] = '\n'.join(body).rstrip() + '\n'
    return heads


def main():
    if not os.path.isfile(SRC):
        bad('源文件不存在：%s' % SRC)
        return 1
    raw = io.open(SRC, encoding='utf-8', errors='replace').read()
    lines = raw.split('\n')
    w('源文件 %s' % SRC)
    w('  字节=%d  字符=%d  行=%d' % (os.path.getsize(SRC), len(raw), len(lines)))

    blocks = cut_blocks(lines)
    ok('切块 %d 份（期望 76）' % len(blocks)) if len(blocks) == 76 else \
        bad('切块 %d 份 ≠ 76 ⇒ 源文件结构变了' % len(blocks))

    # ---- 强断言：每块的 作品名/角色名 必须命中期望 ----
    w('')
    w('=== 期望表核对（作品名 + 角色名 必须命中）===')
    mism = []
    for (idx, ws_kw, nm_kw, _id), b in zip(EXPECT, blocks):
        ws = b['work'] or ''
        nm = b['name'] or ''
        if ws_kw.lower() not in ws.lower() or nm_kw.lower() not in nm.lower():
            mism.append((idx, ws_kw, nm_kw, ws, nm))
    if mism:
        for m in mism:
            bad('序号 %d 期望《%s》/ %s，实得《%s》/ %s' % m)
    else:
        ok('★ 76 条全部命中期望（作品名 + 角色名，逐条）')

    # ---- 尾部补充块（单一真源）----
    pj = json.load(io.open(os.path.join(N, '_personas.json'), encoding='utf-8'))
    tail = pj.get('tail_text') or ''
    if not tail.strip():
        bad('_personas.json.tail_text 为空 ⇒ 补充块无真源')
    else:
        ok('补充块真源 = _personas.json.tail_text（%d 字符）' % len(tail))
    # ★ 校准（实测）：`tail_text` 与现有文件里的尾块**只差末尾一个 `\n`**
    #   （`tail.strip() == file_tail.strip()`）⇒ 组装时统一按「\n\n + tail + \n」，
    #   否则 50 份会全部因"差 1 个字符"被误报成"有差异"（首版实测 50/50 假红）。
    _probe = os.path.join(PER, 'susie.txt')
    if os.path.isfile(_probe):
        _cur = io.open(_probe, encoding='utf-8', errors='replace').read()
        _k = _cur.find('【本项目补充')
        if _k >= 0 and _cur[_k:].rstrip() == tail.rstrip():
            ok('★ 校准：tail_text 与现有文件尾块等价（仅差末尾换行）')
        else:
            bad('tail_text 与现有 persona 尾块不一致 ⇒ 补充块真源已漂移')
    else:
        bad('找不到校准样本 susie.txt')

    # ---- 组装（应用 CUT_AT：切断源文件里的粘贴残留）----
    def _body_for(pid, b):
        body = b['body']
        mk = CUT_AT.get(pid)
        if mk:
            bl = body.split('\n')
            for j, l in enumerate(bl):
                if l.strip() == mk:
                    bl = bl[:j]
                    break
            while bl and not bl[-1].strip():
                bl.pop()
            body = '\n'.join(bl).rstrip('\n') + '\n'
        return body

    # ---- 与现有文件对比（`--write` 时实际写盘）----
    w('')
    w('=== 与现有 persona/*.txt 对比 ===')

    def _norm(s):
        """比较用：CRLF / CR / LF 一律归一 —— 仓库 `autocrlf=true`，
        工作区是 CRLF、blob 是 LF，不归一就会把"同一内容"误报成"有差异"。"""
        return s.replace('\r\n', '\n').replace('\r', '\n')

    #: 旧索引（`--write` 前）：既提供 `tail_text`，也提供 `sha256` 硬真值
    old_rec = {r['id']: r for r in (pj.get('personas') or [])}
    #: ★ 历史复现判据只在"索引还是第64轮的 50 条"时成立；索引已升到 76 条后
    #:   3 条"本轮真改"的 hash 也已在索引里，再判就会假红 ⇒ 自动降级为提示。
    STRICT = (len(old_rec) == 50)

    def _build(body_lf, style):
        """按历史风格拼装。`body_lf` = LF 正文（尾部 \n 已剥）。"""
        b = body_lf.rstrip('\n').replace('\n', '\r\n')     # 正文 → CRLF
        t = tail.rstrip('\n')                              # 尾块按 JSON 原文（LF）
        if style == '1lf':        # 第55轮系：尾块前那个换行是裸 LF
            return b + '\r\n\n' + t + '\n'
        return b + '\n\n' + t + '\n'                       # 2lf：第64轮系（默认）

    same = diff = new = 0
    diff_ids, new_ids = [], []
    repro_ok, repro_bad, style_use = [], [], {}
    written = 0
    gaster_body = None
    for (idx, _ws, _nm, pid), b in zip(EXPECT, blocks):
        body = _body_for(pid, b)
        if pid == 'ut_gaster':
            gaster_body = body
        body_lf = _norm(body)

        # ★ 用旧索引的 sha256 反选风格（不猜）；新记录走默认
        orec = old_rec.get(pid)
        style = DEFAULT_STYLE
        if orec:
            for cand in STYLE_ORDER:
                if hashlib.sha256(_build(body_lf, cand).encode('utf-8')).hexdigest() \
                        == orec['sha256']:
                    style = cand
                    break
        style_use[style] = style_use.get(style, 0) + 1
        full = _build(body_lf, style)

        fp = os.path.join(PER, pid + '.txt')
        exists = os.path.isfile(fp)
        cur = io.open(fp, encoding='utf-8', errors='replace').read() if exists else ''
        is_same = exists and _norm(cur) == _norm(full)
        if not exists:
            new += 1
            new_ids.append(pid)
            w('  %-24s ★ 新增' % pid)
        elif not is_same:
            diff += 1
            diff_ids.append(pid)
            w('  %-24s ★★ 有差异（现 %d / 新 %d 字符）' % (pid, len(cur), len(full)))
        else:
            same += 1
        # ★ 逐字节复现核对（只对索引里已有的记录做）
        if orec:
            if hashlib.sha256(full.encode('utf-8')).hexdigest() == orec['sha256']:
                repro_ok.append(pid)
            else:
                repro_bad.append(pid)

        if DO_WRITE:
            # ★ `newline=''`：**不做任何换行翻译**。正文自带 CRLF、尾块保持 LF，
            #   拼出来就是历史形态（`chars_def` = 「len(磁盘文本，CRLF)」同步成立）。
            with io.open(fp, 'w', encoding='utf-8', newline='') as fh:
                fh.write(full)
            written += 1

    # ---- ★ 逐字节复现判据（本轮最硬的一条）----
    w('')
    w('=== 逐字节复现（旧索引 sha256 当硬真值）===')
    w('  逐字节复现 = %d ／ 与旧 hash 不符 = %d' % (len(repro_ok), len(repro_bad)))
    w('  风格使用：%s' % ', '.join('%s=%d' % (k, v) for k, v in sorted(style_use.items())))
    if set(repro_bad) == EXPECT_CHANGED:
        ok('★ 与旧 hash 不符的恰好是 EXPECT_CHANGED 的 3 条 ⇒ 其余 %d 条逐字节复现'
           % len(repro_ok))
    elif not STRICT:
        w('  （索引已是 %d 条 ⇒ 跳过历史复现判据；此模式下本条不判红）' % len(old_rec))
    else:
        bad('与旧 hash 不符的集合 %s ≠ 期望 %s（多出 %s / 少了 %s）'
            % (sorted(repro_bad), sorted(EXPECT_CHANGED),
               sorted(set(repro_bad) - EXPECT_CHANGED),
               sorted(EXPECT_CHANGED - set(repro_bad))))

    # ---- CUT_AT 的正/负控制（成对）----
    w('')
    if gaster_body is None:
        bad('拿不到 ut_gaster 的正文 ⇒ CUT_AT 判据无法执行')
    else:
        for t in CUT_NEGCTRL:
            if t in gaster_body:
                bad('负控制：ut_gaster 正文仍含 %r ⇒ 残留未切断' % t)
            else:
                ok('负控制：ut_gaster 正文不含 %r' % t)
        if 'W.D. Gaster 的身份回应' in gaster_body:
            ok('正控制：ut_gaster 保留了自身收尾语（"请始终以 W.D. Gaster 的身份回应…"）')
        else:
            bad('正控制：ut_gaster 自己的收尾语被误切')

    w('')
    w('相同 = %d ／ 有差异 = %d ／ 新增 = %d' % (same, diff, new))
    w('有差异：%s' % (', '.join(diff_ids) or '(无)'))
    w('新增：%s' % (', '.join(new_ids) or '(无)'))
    if DO_WRITE:
        w('★ 已写盘 %d 个文件' % written)

    # ---- 写盘后自检（只在 --write 时做）----
    if DO_WRITE:
        w('')
        w('=== 写盘后自检 ===')
        fs = sorted(f for f in os.listdir(PER) if f.endswith('.txt'))
        if len(fs) == 76:
            ok('persona/*.txt = 76（与源文件块数一致）')
        else:
            bad('persona/*.txt = %d ≠ 76' % len(fs))
        n_bom = n_fffd = n_head = n_tail = 0
        for f in fs:
            raw = open(os.path.join(PER, f), 'rb').read()
            t = raw.decode('utf-8', 'replace')
            if raw[:3] == b'\xef\xbb\xbf':
                n_bom += 1
            if '\ufffd' in t:
                n_fffd += 1
            if not t.startswith(BODY_START):
                n_head += 1
            if '【本项目补充' not in t:
                n_tail += 1
        ok('无 BOM') if not n_bom else bad('有 BOM 的文件 = %d' % n_bom)
        ok('无 U+FFFD（编码干净）') if not n_fffd else bad('含 U+FFFD 的文件 = %d' % n_fffd)
        ok('每份都以正文起点行开头') if not n_head else bad('正文起点行不符 = %d' % n_head)
        ok('每份都带「本项目补充」尾块') if not n_tail else bad('缺尾块 = %d' % n_tail)

        # ★ 回读磁盘，逐字节核对"旧记录必须与旧索引 sha256 相同"
        n_disk_ok, n_disk_bad, bad_names = 0, 0, []
        for pid, orec in old_rec.items():
            p = os.path.join(PER, pid + '.txt')
            if not os.path.isfile(p):
                continue
            if hashlib.sha256(open(p, 'rb').read()).hexdigest() == orec['sha256']:
                n_disk_ok += 1
            else:
                n_disk_bad += 1
                bad_names.append(pid)
        if set(bad_names) == EXPECT_CHANGED:
            ok('★ 回读磁盘：%d 条与旧索引 sha256 逐字节相同，仅 %d 条内容真改（%s）'
               % (n_disk_ok, n_disk_bad, ', '.join(sorted(bad_names))))
        elif not STRICT:
            w('  回读磁盘：%d 与旧 hash 相同 / %d 不同（索引已升级，跳过判红）'
              % (n_disk_ok, n_disk_bad))
        else:
            bad('回读磁盘不符集合 %s ≠ 期望 %s' % (sorted(bad_names), sorted(EXPECT_CHANGED)))

    out = os.path.join(EV, 'extract_personas69_dry.txt')
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(LINES) + '\n')
    w('')
    w('落盘 %s' % out)
    w('RESULT: FAIL=%d' % FAIL)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
