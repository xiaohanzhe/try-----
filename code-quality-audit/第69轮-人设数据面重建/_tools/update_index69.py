# -*- coding: utf-8 -*-
"""第69轮 · 更新 `assets/npc/_personas.json`（50 → 76 条）。

为什么必须更新（★ 产品侧的硬判据）
----------------------------------
`npc_persona.load_personas()` 的判据是「**索引登记 + 磁盘有文件**，两者都要」：
> 判据是磁盘而不是索引：索引说"有"，文件不在也算没有（并记 warning）。
> 反过来，**索引里没登记但目录下有 `<id>.txt` 的，也**不**自动收录**。

⇒ 只往 `persona/` 放 26 个新文件是**不够**的，必须在索引里登记，否则新角色
永远不会被加载（这正是"我明明放了它却没生效"那类静默失败）。

口径（与第55/64轮逐条对齐，全部可从磁盘复现）
--------------------------------------------
* `chars`  = `len(磁盘文本)`，**含 CRLF 的 `\r`**（`_personas.json.chars_def` 原文：
  「len(磁盘文本，CRLF)」）；
* `bytes`  = 文件字节数；
* `sha256` = 磁盘字节的 sha256（CRLF 版本）；
* `sha256_lf` = LF 归一化后的 sha256（可从 git blob 复现，仓库 `autocrlf=true`）；
* `sections` = 正文里 `【...】` 标题（2~14 字，与第64轮同一个正则）；
* `tail_added` / `tail_sha256` = 尾部「本项目补充」块。

保留项（历史留痕，不动）：`tail_text` / `tail_sha256` / `extraction_fix` / `round64`。
新增项：`round69`（本轮变更摘要）。

用法
----
    python _tools/update_index69.py            # dry：只打印
    python _tools/update_index69.py --write
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


#: 开场白正则（名字上限 60 —— 第64轮实测 24 会漏 `The World Machine`）。
#: ★ 第69轮放宽：允许「以《A》**与**《B》中的 X 的身份」这种**多作品**写法。
#:   起因 = `ut_chara` 的新开场白「《Undertale》与《Undertale: Red & Yellow》」，
#:   旧正则的 `[^》]+` 被第一个 `》` 截断后就要求紧跟「中的」⇒ 解析失败 ⇒ 整条被丢
#:   （判据过窄 ⇒ 误报，第64轮「名字上限 24」同类错。见 _tools/probe_opener69.py）。
OPENER = re.compile(r'你是一个角色扮演 AI，你将完全以\s*'
                    r'(?P<works>《[^》]+》(?:\s*[与和、]\s*《[^》]+》)*)\s*'
                    r'中的\s*(?P<name>.{1,60}?)\s*的(?:双重)?身份进行对话')
WORK_RE = re.compile(r'《([^》]+)》')
SEC_RE = re.compile(r'【([^】]{2,14})】')
WORK_NORM = {
    'Deltarune': 'Deltarune',
    'OneShot': 'OneShot',
    'Undertale': 'Undertale',
    'Undertale Yellow': 'Undertale Yellow',
    'Undertale: Red & Yellow': 'Undertale Yellow',
    'Outertale': 'Outertale',
}


def norm_plain(name):
    return re.sub(r'[（(][^）)]*[）)]', '', name or '').strip()


def main():
    idx_p = os.path.join(N, '_personas.json')
    old = json.loads(io.open(idx_p, 'rb').read().decode('utf-8'))
    old_by_id = {r['id']: r for r in (old.get('personas') or [])}
    N_OLD = len(old_by_id)          # ★ 幂等：本工具可重跑，断言按"跑之前的条数"来
    TAIL = old.get('tail_text') or ''

    src_raw = io.open(SRC, 'rb').read()
    src_txt = src_raw.decode('utf-8', 'replace')
    w('源文件 %s' % SRC)
    w('  bytes=%d  sha256=%s' % (len(src_raw), hashlib.sha256(src_raw).hexdigest()[:16]))
    w('  chars=%d（LF 归一化后 %d）' % (len(src_txt), len(src_txt.replace('\r\n', '\n'))))

    # ---- 磁盘上的 persona 文件就是真源 ----
    files = sorted(f for f in os.listdir(PER) if f.endswith('.txt'))
    w('')
    w('persona/*.txt = %d' % len(files))

    recs = []
    n_from_old = n_new = 0
    multi_work = []
    for f in files:
        pid = f[:-4]
        raw = open(os.path.join(PER, f), 'rb').read()
        txt = raw.decode('utf-8', 'replace')
        txt_lf = txt.replace('\r\n', '\n').replace('\r', '\n')
        head = txt_lf.split('\n', 1)[0]
        m = OPENER.search(head)
        if not m:
            bad('%s 的首行不含标准开场白 ⇒ 无法解析 work/name（首行=%r）'
                % (pid, head[:90]))
            continue
        works_raw = [x.strip() for x in WORK_RE.findall(m.group('works'))]
        name = m.group('name').strip()
        if len(works_raw) > 1:
            multi_work.append((pid, works_raw))
        # ★ 多作品时取**第一个**能命中 WORK_NORM 的：与单作品主流写法一致；
        #   对 ut_chara 给出 `Undertale`，恰好等于既有索引里登记的 work。
        work_raw = next((x for x in works_raw if x in WORK_NORM), works_raw[0])
        work = WORK_NORM.get(work_raw)
        if work is None:
            bad('%s 的作品名 %r 未在 WORK_NORM 里' % (pid, work_raw))
            work = work_raw

        r = {
            'id': pid,
            'file': 'persona/%s' % f,
            'work': work,
            'chars': len(txt),
            'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'sha256_lf': hashlib.sha256(txt_lf.encode('utf-8')).hexdigest(),
            'sections': SEC_RE.findall(txt_lf),
            'tail_added': ('【本项目补充' in txt_lf),
            'tail_sha256': hashlib.sha256(TAIL.encode('utf-8')).hexdigest(),
        }
        if pid in old_by_id:
            # ★ 既有 50 条：name / name_plain / work 沿用索引（已校准过，别动）
            r['name'] = old_by_id[pid]['name']
            r['name_plain'] = old_by_id[pid].get('name_plain', norm_plain(r['name']))
            r['work'] = old_by_id[pid]['work']
            n_from_old += 1
        else:
            r['name'] = name
            r['name_plain'] = norm_plain(name)
            n_new += 1
        if not r['tail_added']:
            bad('%s 缺「本项目补充」尾块' % pid)
        recs.append(r)

    w('')
    w('沿用既有索引的 = %d ／ 新增 = %d ／ 合计 = %d' % (n_from_old, n_new, len(recs)))
    if len(recs) != 76:
        bad('记录数 %d ≠ 76' % len(recs))
    if n_from_old != N_OLD:
        bad('既有条数 %d ≠ 跑之前的 %d（应当只有新增，不该动老记录）'
            % (n_from_old, N_OLD))

    # ---- 新增记录预览 ----
    w('')
    w('=== 新增记录（26 条）===')
    for r in recs:
        if r['id'] not in old_by_id:
            w('  %-24s %-18s %-34s sections=%d chars=%d'
              % (r['id'], r['work'], r['name'], len(r['sections']), r['chars']))

    # ---- by_work ----
    by_work = {}
    for r in recs:
        by_work.setdefault(r['work'], []).append(r['id'])
    w('')
    w('=== by_work ===')
    for k in sorted(by_work):
        w('  %-18s %d' % (k, len(by_work[k])))
    if sum(len(v) for v in by_work.values()) != len(recs):
        bad('by_work 计数与记录数不符')

    w('')
    w('=== 既有 %d 条的字段级差异（49→50 那份索引里应当只有 3 条变）==='
      % N_OLD)
    n_chg = 0
    for r in recs:
        o = old_by_id.get(r['id'])
        if o is None:
            continue
        d = []
        for k in ('chars', 'bytes', 'sha256', 'sha256_lf', 'tail_added'):
            if k in o and o[k] != r[k]:
                d.append('%s: %s → %s' % (k, o[k], r[k]) if k != 'chars'
                         else 'chars: %d → %d' % (o[k], r[k]))
        if o.get('sections') != r['sections']:
            d.append('sections: %d → %d 项' % (len(o.get('sections') or []),
                                              len(r['sections'])))
        if d:
            n_chg += 1
            w('  DIFF %-22s %s' % (r['id'], '; '.join(d)))
    if n_chg == 0:
        w('  （无）')
    w('  ⇒ 实际变动 %d 条' % n_chg)

    w('')
    w('=== 多作品开场白（以《A》与《B》中的 X 的身份）===')
    if multi_work:
        for pid, works in multi_work:
            w('  %-22s %s' % (pid, ' + '.join(works)))
    else:
        w('  （无）')
    w('')

    # ---- 组装新索引 ----
    new = dict(old)                      # 保留 tail_text / tail_sha256 / extraction_fix / round64
    new['source'] = ('用户提供的《其余人物设定.txt》（DeepSeek 生成）；'
                     '第64轮首次提供 50 份（785,360 字节）；'
                     '★ 第69轮用户**更新**该文件（1,303,723 字节）⇒ 重建为 76 份')
    new['source_sha256'] = hashlib.sha256(src_raw).hexdigest()
    new['source_bytes'] = len(src_raw)
    new['source_chars'] = len(src_txt)
    new['count'] = len(recs)
    new['by_work'] = by_work
    new['personas'] = recs
    new['round69'] = {
        'what': '用户更新《其余人物设定.txt》（785,360 → 1,303,723 字节）⇒ 全文重抽 50 → 76 份',
        '新增': '黄魂 15（hy_*）+ Outertale 11（ot_*）',
        '改动': ('ut_chara：正文并入 Undertale: Red & Yellow 线，7,474 → 10,492 字符（+3,018）；'
                'ut_flowey：新版句末写成「AI 。」（比旧版多 1 个空格）；'
                'ut_toriel：删掉正文末尾的 `---` 分隔线（−2 行）。'
                '★ 三条都是**用户在新版源文件里真实做的编辑**，不是抽取器抖动。'),
        '不变': ('其余 47 份**逐字节**相同 —— 判据 = 与旧索引记的 sha256 全等'
                '（工具 `extract_personas69.py` 逐份核对并回读磁盘复核），'
                '不是"看起来一样"。'),
        '换行风格': ('★ 本轮踩到的坑：首版 `--write` 用 `newline="\\r\\n"` 把 76 份**全写成 CRLF**，'
                 '47 条旧记录的 bytes/chars/sha256 立刻与索引不符（各差 +8 / +9）而 `sha256_lf` 不变。'
                 '用 HEAD blob + 旧索引 hash 反推（`_tools/probe_rule69.py`）坐实：仓库 `autocrlf=true` '
                 '⇒ blob 一律 LF，但**工作区历史上有两代风格** —— '
                 '`2lf`（第64轮系，35 条）= `正文(CRLF) + "\\n\\n" + 尾块(LF) + "\\n"`；'
                 '`1lf`（第55轮系，12 条 Deltarune）= `正文(CRLF) + "\\r\\n\\n" + 尾块(LF) + "\\n"`。'
                 '两者渲染一模一样、clean 成 blob 后字节全等（所以 `git status` 只报 3 个 M）。'
                 '⇒ 抽取器改为**不猜**：拿旧索引 sha256 反选风格，新记录默认 `2lf`。'
                 '已恢复"47 条逐字节复现"，历史 hash 全部继续有效。'),
        '★ 数据残留': ('源文件 5146 行有一个**错位的 `黄魂：` 分区标题**，其后 5148~5154 是 '
                    '**Clover 的语言风格片段**、5156 是空 `【行为准则】`（Clover 正式正文从 5158 重新开始）。'
                    '按"遇到下一 head 行才停"会把这 12 行算进 **Gaster** ⇒ 已在 '
                    '`_tools/extract_personas69.py` 的 `CUT_AT = {"ut_gaster": "黄魂："}` 显式切断 '
                    '（正/负控制成对：切断后不含 "I reckon"/"Gun-Hat"，且保留 Gaster 自己的收尾语）。'
                    '**请用户裁定该残片原本属于谁**。'),
        '多作品开场白': ({pid: works for pid, works in multi_work} or '无'),
        '判据修正': ('`update_index69.py` 的旧 `OPENER` 正则只认「以《A》中的 X 的身份」，'
                 '遇到 `ut_chara` 的新写法「以《Undertale》与《Undertale: Red & Yellow》中的 '
                 'Chara 的身份」就解析失败并**整条丢弃**（表现为 75≠76）。'
                 '已放宽为允许多作品，并用 `_tools/probe_opener69.py` 量出全 76 份'
                 '「只有 ut_chara 一份是多作品」后才落改 —— 属**判据过窄**，非数据坏。'),
        'tool': ('code-quality-audit/第69轮-人设数据面重建/_tools/'
                 'extract_personas69.py + update_index69.py'),
        'evidence': ('code-quality-audit/第69轮-人设数据面重建/_evidence/'
                     'extract_personas69_dry.txt + update_index69.txt'),
    }

    if not DO_WRITE:
        w('')
        w('（dry-run，未落盘。加 --write 才写。）')
    else:
        text = json.dumps(new, ensure_ascii=False, indent=1)
        with io.open(idx_p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        w('')
        w('★ 已写盘 %s（%d 字节）' % (os.path.basename(idx_p), len(text.encode('utf-8'))))

        # ---- 回读自检：索引 ↔ 磁盘 双向对账 ----
        w('')
        w('=== 回读自检 ===')
        back = json.loads(io.open(idx_p, 'rb').read().decode('utf-8'))
        if back['count'] == len(files):
            ok('count=%d 与磁盘文件数一致' % back['count'])
        else:
            bad('count=%d ≠ 磁盘 %d' % (back['count'], len(files)))
        ids_idx = {r['id'] for r in back['personas']}
        ids_disk = {f[:-4] for f in files}
        if ids_idx == ids_disk:
            ok('索引 id 集合 == 磁盘文件名集合（双向）')
        else:
            bad('id 差集：索引多 %s / 磁盘多 %s'
                % (sorted(ids_idx - ids_disk), sorted(ids_disk - ids_idx)))
        n_bad = 0
        for r in back['personas']:
            raw = open(os.path.join(PER, r['id'] + '.txt'), 'rb').read()
            if (len(raw) != r['bytes']
                    or hashlib.sha256(raw).hexdigest() != r['sha256']
                    or len(raw.decode('utf-8', 'replace')) != r['chars']):
                n_bad += 1
                bad('%s 的 bytes/chars/sha256 与实际文件不符' % r['id'])
        if not n_bad:
            ok('★ 76 条的 bytes / chars / sha256 全部与实际文件逐一相符')

    out = os.path.join(EV, 'update_index69.txt')
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
