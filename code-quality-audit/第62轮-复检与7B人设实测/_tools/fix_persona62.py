#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第62轮 · 修掉人设文件末尾"下一份的开场白"（第55轮切分器差一行）。

证据（`_evidence/persona_integrity62.json`）：13 份里有 12 份，正文最后粘着
**别人**人设的开场白，构成完整链条

    susie=Kris → kris=Asgore → asgore=Toriel → toriel=Lancer → lancer=King
    → king=Queen → queen=Berdly → berdly=Noelle → noelle=Tenna
    → tenna=Rouxls Kaard → rouxls=Gerson Boom → gerson=Flowery
    （flowery 是源文件最后一份，故干净）

修法（**最小改动，不猜原文**）：
  只删掉那一行本身。删后原文结构恰好留下一个空行 ⇒ 与「【本项目补充】」的分隔不变。
  ★ 用户那份《其余人物设定.txt》已不在本机 ⇒ **不重抽、不改写正文**，
    只做"删掉已被证明不属于这份的行"这一件事。

同时把 `_personas.json` 的 `sha256 / bytes / chars` 按新内容重算，
并写入 `extraction_fix`（说明改了什么、为什么、如何回退）。

用法：
  C:\\Python311\\python.exe fix_persona62.py            # 干跑：只打印将要发生什么
  C:\\Python311\\python.exe fix_persona62.py --apply    # 落地
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
IDX = os.path.join(NPC, '_personas.json')

FOREIGN_RE = re.compile(
    u'^以下是一段可直接用于 AI 角色扮演的 system prompt，'
    u'旨在尽可能还原《Deltarune》(?:第[^》]{1,6}章)?中(.+?)的')


def main():
    apply = '--apply' in sys.argv
    with io.open(IDX, 'rb') as fh:
        raw_idx = fh.read()
    idx = json.loads(raw_idx.decode('utf-8'))

    # ① 先验 `chars` 的口径：必须能用某个定义复现现有值，否则不许改
    print(u'--- 0 先验 chars 口径（改动前必须能复现索引里的值）---')
    ok_def = True
    for it in idx['personas']:
        p = os.path.join(NPC, it['file'].replace('/', os.sep))
        txt = io.open(p, 'rb').read().decode('utf-8')
        if len(txt) != it['chars']:
            ok_def = False
            print(u'  [WARN] %-8s len(text)=%d != chars=%d'
                  % (it['id'], len(txt), it['chars']))
    print(u'  chars == len(text) 逐条成立: %s' % ok_def)
    if not ok_def:
        print(u'  ⇒ 口径不明，拒绝改索引。')
        return 2

    # ② json 往返是否保持原格式（否则改动会带一大片格式 diff）
    rt = json.dumps(idx, ensure_ascii=False, indent=1)
    same = (rt.encode('utf-8') == raw_idx) or (rt + u'\n').encode('utf-8') == raw_idx
    print(u'--- 0b json 往返一致（indent=1 / 非 ASCII 直出）: %s' % same)
    if not same:
        print(u'  ⇒ 往返不一致，先人工确认格式再改。')
        return 2

    # ③ 逐份删除
    print()
    print(u'--- 1 逐份删除外来行 ---')
    changed = []
    for it in idx['personas']:
        path = os.path.join(NPC, it['file'].replace('/', os.sep))
        raw = io.open(path, 'rb').read()
        text = raw.decode('utf-8')
        lines = text.split('\n')
        keep, drop = [], []
        for ln in lines:
            m = FOREIGN_RE.match(ln)
            nm = m.group(1).strip() if m else None
            if nm and nm not in (it.get('name') or u'') \
                    and not (it.get('name') or u'').split(u'（')[0] == nm:
                drop.append(ln)
            else:
                keep.append(ln)
        if not drop:
            print(u'  %-8s 无需改动' % it['id'])
            continue
        new_text = '\n'.join(keep)
        # 校验：只少了这些行，别的一个字符没动
        assert new_text != text
        assert len(lines) - len(keep) == len(drop)
        assert all(d in lines for d in drop)
        # 再校验：把 drop 放回去能还原原文（可逆性）
        assert sorted(lines) == sorted(keep + drop)
        nb = new_text.encode('utf-8')
        changed.append({
            'id': it['id'], 'file': it['file'],
            'dropped': [d.strip() for d in drop],
            'dropped_lines': len(drop),
            'bytes_old': len(raw), 'bytes_new': len(nb),
            'chars_old': len(text), 'chars_new': len(new_text),
            'sha_old': hashlib.sha256(raw).hexdigest(),
            'sha_new': hashlib.sha256(nb).hexdigest(),
        })
        print(u'  %-8s 删 %d 行（-%d B / -%d 字符）→ 新 sha=%s'
              % (it['id'], len(drop), len(raw) - len(nb),
                 len(text) - len(new_text),
                 hashlib.sha256(nb).hexdigest()[:16]))
        if apply:
            with io.open(path, 'wb') as fh:
                fh.write(nb)
            it['bytes'] = len(nb)
            it['chars'] = len(new_text)
            it['sha256'] = hashlib.sha256(nb).hexdigest()

    if not changed:
        print(u'  （没有需要改的：可能已经修过）')
        return 0

    if not apply:
        print()
        print(u'=== 干跑结束（未写盘）。加 --apply 落地。===')
        return 0

    # ④ 更新索引
    idx['extraction_fix'] = {
        'round': 62,
        'what': u'删掉每份人设正文末尾"下一份的开场白"行（第55轮切分器差一行）',
        'why': u'那行写的是**另一个角色**，会随 system prompt 一起发给模型，'
               u'与"不要搞混了"的口径相反',
        'how': u'只删该行；删后结构恰好留下一个空行 ⇒ 与「本项目补充」的分隔不变',
        'revert': u'git checkout -- ralsei_pet/assets/npc/persona ralsei_pet/assets/npc/_personas.json',
        'evidence': u'code-quality-audit/第62轮-复检与7B人设实测/_evidence/persona_integrity62.json',
        'fixed_files': sorted(c['id'] for c in changed),
        'note': u'★ 用户那份《其余人物设定.txt》已不在本机 ⇒ 未重抽、未改写正文，'
                u'仅做删除；如需按原文重抽，请重新提供该文件',
    }
    out = json.dumps(idx, ensure_ascii=False, indent=1)
    if not out.endswith('\n'):
        out += '\n'
    with io.open(IDX, 'wb') as fh:
        fh.write(out.encode('utf-8'))
    print()
    print(u'--- 2 索引已更新（%d 份 sha/bytes/chars + extraction_fix）---' % len(changed))

    # ⑤ 回验：重新从磁盘算一遍，必须与索引逐条相等
    idx2 = json.loads(io.open(IDX, 'rb').read().decode('utf-8'))
    bad = []
    for it in idx2['personas']:
        p = os.path.join(NPC, it['file'].replace('/', os.sep))
        b = io.open(p, 'rb').read()
        t = b.decode('utf-8')
        if hashlib.sha256(b).hexdigest() != it['sha256'] or len(b) != it['bytes'] \
                or len(t) != it['chars']:
            bad.append(it['id'])
    print(u'--- 3 回验（磁盘 ↔ 索引 逐条）: %s ---'
          % (u'全部一致' if not bad else u'不一致 %r' % bad))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
