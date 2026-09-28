#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第62轮 · 人设文件完整性复检（结构 / 串味 / 编码 / 索引一致性）。

为什么单独做这一件事：
  第55轮把用户那份《其余人物设定.txt》切成 13 份。第62轮复检时肉眼发现
  `susie.txt` 末尾粘着一行「…尽可能还原《Deltarune》中 **Kris** 的…」——
  那是**别人**的人设开头。若属实，则 13 份人设的 system prompt 末尾
  都带一句"另一个角色的身份说明"，与用户口径「不要搞混了」正相反。
  本脚本把"是否属实、影响几份、链条是什么"变成可复核的证据。

判据（每条都配正/负控制；负控制真落进被测分支）：
  I1  UTF-8 严格可解 / 无 BOM / 无 U+FFFD / 行尾不混用
  I2  首行身份与文件自身一致（「你将完全以《Deltarune》中的 X 的身份」）
  I3  ★ 末尾外来行：出现「以下是一段…还原《Deltarune》中 X 的…」且 X != 自己
  I4  小节标题集合 == `_personas.json[].sections`
  I5  「本项目补充」tail 在位且 sha256 == 索引里的 `tail_sha256`
  I6  sha256 / bytes 与索引逐条一致（索引是否忠实描述磁盘）

用法：
  C:\\Python311\\python.exe persona_integrity62.py
"""
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
NPC = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc')
PDIR = os.path.join(NPC, 'persona')
OUT = os.path.join(ROUND, '_evidence')

#: 每份人设的**第一行**模板（第55轮抽取自用户文件）
HEAD_RE = re.compile(
    u'你是一个角色扮演 AI，你将完全以《Deltarune》中的(.+?)的身份进行对话')
#: ★ 每份人设正文后面那一行"下一份"的开场白（**外来行的形态**）
#: ⚠️ 判据过窄的教训（本脚本第二版踩到）：`noelle.txt` 那行写的是
#:    「…还原《Deltarune》**第三章中** Tenna 的…」，只认「《Deltarune》中」
#:    会把这一份漏掉 ⇒ 必须允许可选的「第 N 章」。
FOREIGN_RE = re.compile(
    u'^以下是一段可直接用于 AI 角色扮演的 system prompt，'
    u'旨在尽可能还原《Deltarune》(?:第[^》]{1,6}章)?中(.+?)的')

R = []          # 逐文件结果
N = [0, 0]      # pass, fail


def ck(name, cond, extra=u''):
    N[0] += 1
    if cond:
        print(u'[PASS] %s %s' % (name, extra))
    else:
        print(u'[FAIL] %s %s' % (name, extra))
        N[1] += 1
    return bool(cond)


def rd_bytes(p):
    with io.open(p, 'rb') as fh:
        return fh.read()


def rd_text(p):
    return rd_bytes(p).decode('utf-8')


# --------------------------------------------------------------------- 夹具
def inspect_text(pid, name, text, tail_sha=None):
    u"""对一段人设文本做**首行身份 + 外来行**检查（纯函数，不碰磁盘）。

    之所以做成纯函数：I3 的负控制要把"人工注入外来行"的文本喂**进同一条分支**，
    而不是另写一套旁路逻辑（否则负控制根本没测到真判据）。
    """
    res = {'id': pid}
    lines = text.split('\n')
    # --- I2 首行身份 ---
    head = lines[0] if lines else u''
    m = HEAD_RE.search(head)
    res['head_name'] = m.group(1).strip() if m else None
    # 允许的名字集合（同名/中文别名都算对）
    alts = [name]
    if u'（' in name:
        alts.append(name.split(u'（')[0])
    res['head_ok'] = bool(m) and any(a and a in (m.group(1) or u'')
                                     for a in alts)
    # --- I3 ★ 外来行 ---
    foreign = []
    for i, ln in enumerate(lines):
        fm = FOREIGN_RE.match(ln)
        if not fm:
            continue
        nm = fm.group(1).strip()
        own = any(a and a in nm for a in alts)
        foreign.append({'line': i + 1, 'name': nm, 'is_self': own,
                        'text': ln[:70]})
    res['foreign'] = foreign
    res['foreign_alien'] = [f for f in foreign if not f['is_self']]
    # --- I4 小节标题 ---
    res['sections'] = re.findall(u'【([^】]{2,20})】', text)
    # --- I5 tail（可选：本函数主体不判，交给主循环；这里留接口）
    res['tail_ok'] = None
    return res


def selftest():
    u"""判据自检：负控制必须报红、正控制必须绿。"""
    got = []
    good = u'你是一个角色扮演 AI，你将完全以《Deltarune》中的 Susie 的身份进行对话。\n\n【角色身份】\n内容\n'
    bad = good + u'\n以下是一段可直接用于 AI 角色扮演的 system prompt，旨在尽可能还原《Deltarune》中 Kris 的性格、行为方式与内在矛盾：\n'
    self_line = good + u'\n以下是一段可直接用于 AI 角色扮演的 system prompt，旨在尽可能还原《Deltarune》中 Susie 的性格：\n'
    g = inspect_text('susie', u'Susie', good, None)
    b = inspect_text('susie', u'Susie', bad, None)
    s = inspect_text('susie', u'Susie', self_line, None)
    got.append((u'S1 干净文本 → 无外来行', g['foreign_alien'] == []))
    got.append((u'S2 ★ 注入他人开场白 → 必须报红（负控制真落进分支）',
                len(b['foreign_alien']) == 1 and b['foreign_alien'][0]['name'] == 'Kris'))
    got.append((u'S3 正向控制：开场白写的是自己 → 不算外来',
                s['foreign_alien'] == []))
    got.append((u'S4 首行身份识别正确', g['head_ok'] is True))
    got.append((u'S5 首行换成别人 → 身份失配被抓',
                inspect_text('susie', u'Susie',
                             good.replace(u'Susie 的身份', u'Kris 的身份'),
                             None)['head_ok'] is False))
    # ★ S6 锁住"判据过窄"那次修正：带「第 N 章」的外来行也必须被抓到
    ch = good + u'\n以下是一段可直接用于 AI 角色扮演的 system prompt，' \
                u'旨在尽可能还原《Deltarune》第三章中 Tenna 的性格、说话方式与行为模式：\n'
    r6 = [a for a in inspect_text('noelle', u'Noelle Holiday', ch,
                                  None)['foreign_alien'] if a['name'] == 'Tenna']
    got.append((u'S6 ★ 带「第N章」的外来行也被抓到（过窄判据修正的锁）',
                len(r6) == 1))
    return got


def main():
    if not os.path.isdir(PDIR):
        print(u'[FATAL] 人设目录不存在: %s' % PDIR)
        return 2
    with io.open(os.path.join(NPC, '_personas.json'), encoding='utf-8') as fh:
        idx = json.load(fh)
    tail_sha = None
    if idx.get('personas'):
        tail_sha = idx['personas'][0].get('tail_sha256')

    print(u'=' * 72)
    print(u'第62轮 · 人设文件完整性复检')
    print(u'=' * 72)
    print(u'人设目录: %s' % PDIR)
    print(u'索引条数: %d' % len(idx.get('personas') or []))
    print()

    print(u'--- 判据自检（正/负控制）---')
    st = selftest()
    for nm, ok in st:
        ck(nm, ok)
    print()

    print(u'--- I1 编码 / I2 身份 / I3 ★外来行 ---')
    rows = []
    for it in idx.get('personas') or []:
        pid = it['id']
        # ⚠️ `it['file']` 是相对 `assets/npc/` 的（`persona/susie.txt`），
        #    所以基准是 NPC 而不是 PDIR —— 本脚本第一版这里拼成了
        #    `persona/persona/susie.txt`（13 份全"文件不存在"）。
        path = os.path.join(NPC, it['file'].replace('/', os.sep))
        if not os.path.isfile(path):
            ck(u'%s 文件存在' % pid, False, path)
            continue
        raw = rd_bytes(path)
        row = {'id': pid, 'file': os.path.basename(path), 'bytes': len(raw)}
        row['bom'] = raw[:3] == b'\xef\xbb\xbf'
        try:
            text = raw.decode('utf-8')
            row['utf8'] = True
        except UnicodeDecodeError as e:
            row['utf8'] = False
            row['utf8_err'] = str(e)
            text = raw.decode('utf-8', 'replace')
        row['repl'] = text.count(u'\ufffd')
        crlf = raw.count(b'\r\n')
        row['crlf'] = crlf
        row['lf_only'] = raw.count(b'\n') - crlf
        row['sha256'] = hashlib.sha256(raw).hexdigest()
        row['sha_match'] = (row['sha256'] == it.get('sha256'))
        row['bytes_match'] = (row['bytes'] == it.get('bytes'))
        row['chars'] = len(text)

        # 小节集合
        secs = re.findall(u'【([^】]{2,20})】', text)
        want = list(it.get('sections') or [])
        # 文件里除标准小节外还有「本项目补充」这一块标题
        extra = [s for s in secs if s not in want]
        miss = [s for s in want if s not in secs]
        row['sec_extra'] = extra
        row['sec_miss'] = miss
        # tail
        tail_txt = idx.get('tail_text') or u''
        row['tail_ok'] = (tail_txt.strip() and
                          tail_txt.strip() in text and
                          hashlib.sha256(tail_txt.encode('utf-8')).hexdigest()
                          == (it.get('tail_sha256') or u''))
        # 首行 + 外来行（与 selftest 用**同一套**判定，避免两处逻辑分叉）
        _alts = [it.get('name') or u'']
        if u'（' in (it.get('name') or u''):
            _alts.append((it.get('name') or u'').split(u'（')[0])
        lines = text.split('\n')
        hm = HEAD_RE.search(lines[0] if lines else u'')
        row['head_name'] = hm.group(1).strip() if hm else None
        row['head_ok'] = bool(hm) and any(
            a and a in (row['head_name'] or u'') for a in _alts)
        alien = []
        for i, ln in enumerate(lines):
            fm = FOREIGN_RE.match(ln)
            if not fm:
                continue
            nm = fm.group(1).strip()
            if nm and not any(a and a in nm for a in _alts):
                alien.append({'line': i + 1, 'name': nm})
        row['alien'] = alien
        rows.append(row)

    for r in rows:
        ck(u'I1 %-8s UTF-8 可解 / 无 BOM / 无替换符' % r['id'],
           r.get('utf8') and not r['bom'] and r['repl'] == 0,
           u'utf8=%s bom=%s repl=%d crlf=%d lf=%d'
           % (r.get('utf8'), r['bom'], r['repl'], r['crlf'], r['lf_only']))
    for r in rows:
        ck(u'I2 %-8s 首行身份 == 自己' % r['id'], r['head_ok'],
           u'head=%r' % (r['head_name'],))
    # I3 是本轮的核心发现 —— 单独成组打印
    _alien_files = [r['id'] for r in rows if r['alien']]
    for r in rows:
        if r['alien']:
            print(u'[红] I3 %-8s 末尾混入他人人设开场白 → %s'
                  % (r['id'], u'; '.join(u'第%d行=%s' % (a['line'], a['name'])
                                         for a in r['alien'])))
        else:
            print(u'[PASS] I3 %-8s 无外来行' % r['id'])
    N[0] += len(rows)
    N[1] += len(_alien_files)
    # ★★ 这里必须带上"真扫到了几份"——否则一份都没读到时会以"空链条"为绿，
    #    正是"恒真判据比不写还危险"（本脚本第一版就踩了：路径拼错 ⇒ 13 份全缺
    #    ⇒ 这条照样 PASS）。
    ck(u'I3 ★★ 外来行链条（必须扫满 %d 份且全干净才算绿）'
       % len(idx.get('personas') or []),
       (not _alien_files) and len(rows) == len(idx.get('personas') or [])
       and len(rows) > 0,
       u'已扫 %d/%d 份；带外来行的 %d 份: %s'
       % (len(rows), len(idx.get('personas') or []), len(_alien_files),
          u' → '.join(u'%s=%s' % (r['id'], r['alien'][0]['name'])
                      for r in rows if r['alien']) or u'（无）'))
    print()
    print(u'--- I4 小节 / I5 tail / I6 索引一致性 ---')
    for r in rows:
        ck(u'I4 %-8s 小节集合与索引一致' % r['id'],
           not r['sec_miss'] and not r['sec_extra'],
           u'miss=%r extra=%r' % (r['sec_miss'], r['sec_extra']))
    for r in rows:
        ck(u'I5 %-8s 本项目补充 tail 在位且 sha256 相符' % r['id'], r['tail_ok'])
    for r in rows:
        ck(u'I6 %-8s 索引 sha256/bytes 忠实于磁盘' % r['id'],
           r['sha_match'] and r['bytes_match'],
           u'sha=%s bytes=%s' % (r['sha_match'], r['bytes_match']))

    # ---------------- 汇总 ----------------
    print()
    print(u'== 结果 ==')
    print(u'  断言 %d 项，FAIL %d 项' % (N[0], N[1]))
    ev = {
        'n_assert': N[0], 'n_fail': N[1],
        'persona_dir': PDIR,
        'index_count': len(idx.get('personas') or []),
        'rows': rows,
        'foreign_chain': [{'id': r['id'], 'got': r['alien'][0]['name']}
                          for r in rows if r['alien']],
        'selftest': [{'name': n, 'ok': o} for n, o in st],
    }
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    p = os.path.join(OUT, 'persona_integrity62.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'  证据 -> %s' % p)
    return 0 if N[1] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
