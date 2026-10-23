# -*- coding: utf-8 -*-
"""第113轮 · 按用户**新版**《其余人物设定.txt》重建有改动的人设（写盘）。

背景（必须写在最前面，否则半年后没人知道为什么动过）
--------------------------------------------------
2026-10-24 用户重新发来 `其余人物设定.txt`（1,369,264 B）。与仓库第69轮用的版本
（`_personas.json.source_bytes` = 1,303,723 B）逐块比对后：**63 份逐字一致**，
**6 份主角人设被重写**（旧的「平铺式」，新的「三层结构」，与另外 58 份的体例统一）：

    susie 2712→6599 · kris 2964→5870 · asgore 3623→6294
    toriel 3732→6989 · lancer 3628→6553 · berdly 4753→5931

另有 2 处**不动**（已核）：`ut_gaster` 差 6 字（换行/空格级）、`ot_papyrus` 的
+7098 属**同名多人配对歧义**（Outertale 与 Undertale 的 Papyrus 撞名），不是真改动。
`Ralsei` 在这份文件里是**新增块**，但仓库里 Ralsei 的真源是
`assets/ralsei_persona.md`（第75轮定的单一真源），**不覆盖**。

写盘口径（与第69轮逐字节一致）
------------------------------
* 正文 = 源文件里从「你是一个角色扮演 AI…」起，到下一个「以下是一段可直接用于…」前；
  去掉尾部 `---` 与空白；行尾统一 CRLF（源文件与历史产物都是 CRLF）。
* 这 6 份都属于第55轮系（`1lf`）：`正文(CRLF) + '\\r\\n\\n' + 尾块(LF) + '\\n'`。
  实测确认方式：读旧文件里 `【本项目补充` 之前的最后 4 个字节，若是 `\r\n\n` 即 1lf。
* 尾块正文**不重写**，直接取 `_personas.json.tail_text`（单一真源）。
* 索引按新内容重算 `chars/bytes/sha256/sha256_lf/sections/tail_*`。

用法
----
    python personas113.py            # 只对比，不写
    python personas113.py --write    # 写盘（会把旧文件备份到 E:\\Download\\_tmp\\persona_backup_113）
"""
import io
import json
import os
import re
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
NPC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
PER = os.path.join(NPC, 'persona')
IDX = os.path.join(NPC, '_personas.json')
SRC = r'C:\Users\23002\Desktop\其余人物设定.txt'
BACKUP = r'E:\Download\_tmp\persona_backup_113'
EV = os.path.join(ROUND, '_evidence')

#: 已实证「新版重写」的 6 人（不在表里的**一律不动** —— 证据不足就不改用户原文）
TARGETS = ['susie', 'kris', 'asgore', 'toriel', 'lancer', 'berdly']

OPEN = re.compile(r'你是一个角色扮演 AI，你将完全以《([^》]+)》中的\s*(.+?)\s*的身份进行对话')
PRE = re.compile(r'以下是一段可直接用于')
SEC = re.compile(r'【([^】]{1,24})】')


def body_of_block(text, m, pres):
    end = len(text)
    for p in pres:
        if p > m.end():
            end = p
            break
    b = text[m.start():end].replace('\r\n', '\n').strip()
    b = re.sub(r'\n\s*-{3,}\s*$', '', b).strip()
    return b


def main():
    do_write = '--write' in sys.argv
    src = open(SRC, 'rb').read().decode('utf-8')
    pres = [x.start() for x in PRE.finditer(src)]
    idx = json.load(open(IDX, encoding='utf-8'))
    recs = {r['id']: r for r in idx['personas']}
    tail = idx['tail_text']

    plan = []
    for nid in TARGETS:
        rec = recs.get(nid)
        if not rec:
            print('[跳过] %s：索引里没有' % nid)
            continue
        want_work = rec.get('work') or 'Deltarune'
        want_name = rec.get('name') or ''
        hit = None
        for m in OPEN.finditer(src):
            if (m.group(1).strip() == want_work
                    and re.sub(r'（.*?）', '', m.group(2).strip()) == want_name):
                hit = m
                break
        if hit is None:
            print('[失败] %s：新文件里找不到《%s》%s' % (nid, want_work, want_name))
            continue
        new_body = body_of_block(src, hit, pres)
        if not new_body:
            print('[失败] %s：切出的正文为空' % nid)
            continue
        old_path = os.path.join(NPC, rec['file'])
        old_raw = open(old_path, 'rb').read()
        old_text = old_raw.decode('utf-8')
        i = old_text.find('【本项目补充')
        sep = old_text[i - 4:i] if i > 0 else ''
        style = '1lf' if sep.endswith('\r\n\n') else '2lf'
        body_crlf = new_body.replace('\r\n', '\n').replace('\n', '\r\n')
        junction = '\r\n\n' if style == '1lf' else '\n\n'
        payload = (body_crlf + junction + tail + '\n').encode('utf-8')
        plan.append({'id': nid, 'path': old_path, 'bytes': payload,
                     'style': style, 'old_len': len(old_text),
                     'new_text': body_crlf + junction + tail + '\n'})

    print('计划重建 %d 份：%s' % (len(plan), '、'.join(p['id'] for p in plan)))
    for p in plan:
        print('  %-8s %s  %6d 字 → %6d 字  %6d B → %6d B'
              % (p['id'], p['style'], p['old_len'], len(p['new_text']),
                 os.path.getsize(p['path']), len(p['bytes'])))
    if not do_write:
        print('\n（dry：未写盘。加 --write 执行）')
        return 0

    if not os.path.isdir(BACKUP):
        os.makedirs(BACKUP)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    log = {'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'source': SRC,
           'source_bytes': len(src.encode('utf-8')), 'items': []}

    for p in plan:
        rid = p['id']
        # ① 先备份（用户口径：处置文件先留档，不直接覆盖）
        bak = os.path.join(BACKUP, '%s_%s.txt' % (rid, stamp))
        shutil.copy2(p['path'], bak)
        # ② 写盘（原子）
        tmp = p['path'] + '.tmp'
        with open(tmp, 'wb') as fh:
            fh.write(p['bytes'])
        os.replace(tmp, p['path'])
        # ③ 回读校验
        back = open(p['path'], 'rb').read()
        assert back == p['bytes'], '%s 写后回读不一致' % rid
        # ④ 更新索引（口径与第69轮一致：chars/bytes/sha256 = 磁盘 CRLF 版本）
        import hashlib
        rec = recs[rid]
        text = back.decode('utf-8')
        rec['chars'] = len(text)
        rec['bytes'] = len(back)
        rec['sha256'] = hashlib.sha256(back).hexdigest()
        rec['sha256_lf'] = hashlib.sha256(back.replace(b'\r\n', b'\n')).hexdigest()
        rec['sections'] = [s for s in SEC.findall(text.split('【本项目补充')[0])]
        rec['tail_added'] = True
        rec['tail_sha256'] = hashlib.sha256(tail.encode('utf-8')).hexdigest()
        log['items'].append({'id': rid, 'backup': bak, 'chars': rec['chars'],
                             'bytes': rec['bytes'], 'sha256': rec['sha256'],
                             'sections': rec['sections']})
        print('  [写入] %s  %d 字  sha256=%s' % (rid, rec['chars'], rec['sha256'][:12]))

    with open(IDX, 'wb') as fh:
        fh.write(json.dumps(idx, ensure_ascii=False, indent=1).encode('utf-8') + b'\n')
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with open(os.path.join(EV, 'persona_update113.json'), 'w',
              encoding='utf-8', newline='\n') as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    print('\n索引已更新；备份在 %s；变更单 → _evidence/persona_update113.json' % BACKUP)
    return 0


if __name__ == '__main__':
    sys.exit(main())
