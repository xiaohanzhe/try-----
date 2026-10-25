# -*- coding: utf-8 -*-
"""第113轮h · 人设语言段本地化（hy_guardener / hy_axis）+ 同步 _personas.json

## 为什么要改人设，而不是加 prompt 规则
人设【语言风格】明文写着「你的说话方式全部大写」「所有对话都以大写字母输出」。
中文没有大小写，模型收到这条只能改去说英文 —— 实测这两人的 12 轮**中文占比 0.00**，
`NOT_CN` 12/12。SPEAK_RULES 里那条「用简体中文说话」拉回了 `hy_axis`（0.00→0.52），
但压不住人设里的硬指令。

## 改什么、不改什么
**只改"用哪种语言输出"这一层**，情节/性格/关系/台词依据一律不动：
  · 「全部大写」→「机械播报腔（短句、平语气、不用语气词）」——保留机器人感，改用中文承载；
  · 「元音替换/数字乱码」（纯英文才能做的事）→「插程序符号/编号，像日志刷新」；
  · 「经典台词包括」那几行 **原样保留**：它们是原作依据，删了就不是这个角色了。
    （若重训后仍整段英文，再单独处理台词库——那是第二步，不在本次范围。）

## ★★ 为什么必须同步 _personas.json
`check113` A 面断言「人设 sha256 与磁盘同源」。改了 txt 不改索引 ⇒ 判据立刻报红，
而且报的是"人设被篡改"，比"忘了同步"难查得多。本脚本先**自证公式**（拿未改动的
文件重算一遍，必须与索引逐字段相等），再动手。

用法：
    python localize_persona113h.py            # 干跑：只打印将要改什么
    python localize_persona113h.py --apply    # 真改（改前自动备份到 _evidence/_persona_bak）
"""

import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
NPC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
PDIR = os.path.join(NPC, 'persona')
IDX = os.path.join(NPC, '_personas.json')
BAK = os.path.join(ROUND, '_evidence', '_persona_bak')

#: (id, 旧串, 新串)。旧串必须**逐字**匹配且只出现一次 —— 否则脚本拒绝动手。
EDITS = [
    ('hy_guardener',
     '· 你的说话方式全部大写。你像 Axis 一样，所有对话都以大写字母输出。',
     '· 你的说话方式像机械播报：句子短，语气平，不寒暄，也不用语气词。'
     '你说话时带着程序的痕迹，而不是人的随意。'),
    ('hy_guardener',
     '· 你的话语中充满了错误和乱码。你会把元音替换成下划线或符号，'
     '比如“_”、“;”、“>”。你会说“FORGI>ABLE”而不是“FORGIVABLE”。'
     '你会说“S_SEEMS”而不是“SEEMS”。你的乱码不是故障，它是你的系统正在崩溃的证明。',
     '· 你的话语里带着系统痕迹：偶尔插入程序符号或编号，把一句正常的话断成一段状态行，'
     '像日志在自己刷新。这些痕迹不是故障，它是你的系统正在崩溃的证明。'),
    ('hy_axis',
     '· 你的说话方式全部大写，简短，直接，充满了压抑的愤怒和笨拙的困惑。'
     '你会说“H-H-HUMA-N.”你会说“Y-YOU HAVE ANGERED ME GREATLY.”'
     '你会说“I AM [ticked] OFF AND OUT OF NON-LETHAL OPTIONS.”',
     '· 你的说话方式简短、直接、平直，字里带着压抑的愤怒和笨拙的困惑；'
     '说话像机械通报，不用语气词。你会说“H-H-HUMA-N.”'
     '你会说“你-你把我惹火-了。”你会说“我已经 [ticked] 没有非致命选项了。”'),
    ('hy_axis',
     '· 你在受损或激动时会混入数字和乱码。你会说“I H4D no_CHOICE.”'
     '你会说“TH3 SAME FaTE ThE.”你会说“I AM ONLY ABLE TO S4VE A FEW.”'
     '你的乱码不是故障，它是你的情感溢出到了语言层面。',
     '· 你在受损或激动时会混入编号和错字。你会说“我没4有 choice。”'
     '你会说“同一个结局。”你会说“我只来_得及救下几个人。”'
     '这些错字不是故障，它是你的情感溢出到了语言层面。'),
]

#: 公式自证用：这些字段必须能从磁盘重算出来并与索引逐值相等。
FIELDS = ('chars', 'bytes', 'sha256', 'sha256_lf')


def read_raw(path):
    with io.open(path, 'rb') as fh:
        return fh.read()


def calc(raw):
    """从**原始字节**算出索引里的四个字段。

    ★ `chars` 用 `newline=''` 解码 ⇒ CRLF 会算成 2 个字符（与索引既有口径一致，
      已用未改动文件自证过）。`sha256_lf` 是"折成 LF 之后"的摘要，供跨平台比对。
    """
    text = raw.decode('utf-8')
    return {
        'chars': len(text),
        'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'sha256_lf': hashlib.sha256(
            text.replace('\r\n', '\n').encode('utf-8')).hexdigest(),
    }


def main(argv):
    apply = '--apply' in argv
    idx = json.load(io.open(IDX, encoding='utf-8'))
    by_id = {e.get('id'): e for e in (idx.get('personas') or [])
             if isinstance(e, dict)}

    # ---- ① 公式自证：先拿**没改过**的文件重算，必须与索引全等 ----
    print('=' * 74)
    print('① 字段公式自证（未改动文件重算 vs 索引）')
    bad = []
    for nid in sorted({e[0] for e in EDITS}):
        e = by_id.get(nid)
        if not e:
            print('  !! 索引里没有 %s' % nid)
            bad.append(nid)
            continue
        path = os.path.join(PDIR, os.path.basename(e['file']))
        got = calc(read_raw(path))
        ok = all(got[f] == e.get(f) for f in FIELDS)
        print('  %-14s %s' % (nid, 'PASS' if ok else 'FAIL'))
        if not ok:
            for f in FIELDS:
                if got[f] != e.get(f):
                    print('       %-9s 重算=%r 索引=%r' % (f, got[f], e.get(f)))
            bad.append(nid)
    if bad:
        print('⇒ 公式对不上，**拒绝动手**（先查清索引口径）')
        return 2

    # ---- ② 逐条替换（干跑也要真校验旧串存在且唯一）----
    print()
    print('=' * 74)
    print('② 替换（旧串必须逐字存在且唯一）')
    texts = {}
    for nid in {e[0] for e in EDITS}:
        e = by_id[nid]
        path = os.path.join(PDIR, os.path.basename(e['file']))
        with io.open(path, 'r', encoding='utf-8', newline='') as fh:
            texts[nid] = fh.read()

    for nid, old, new in EDITS:
        n = texts[nid].count(old)
        print('  %-14s 命中 %d 处  %s' % (nid, n, old[:34].replace('\n', ' ') + '…'))
        if n != 1:
            print('!! 旧串出现 %d 次（要求恰好 1 次）⇒ 停止' % n)
            return 3
        texts[nid] = texts[nid].replace(old, new, 1)

    if not apply:
        print('\n（干跑）加 --apply 才会写盘。')
        return 0

    # ---- ③ 备份 → 写盘 → 重算索引 ----
    if not os.path.isdir(BAK):
        os.makedirs(BAK)
    print()
    print('=' * 74)
    print('③ 写盘')
    for nid in texts:
        e = by_id[nid]
        base = os.path.basename(e['file'])
        path = os.path.join(PDIR, base)
        shutil.copy2(path, os.path.join(BAK, base + '.bak'))
        raw = texts[nid].encode('utf-8')
        with io.open(path, 'wb') as fh:
            fh.write(raw)
        got = calc(raw)
        _old_chars = int(e.get('chars') or 0)
        for f in FIELDS:
            e[f] = got[f]
        print('  %-14s chars %d→%d  bytes %d' % (nid, _old_chars, got['chars'],
                                                 got['bytes']))

    with io.open(IDX, 'w', encoding='utf-8') as fh:
        json.dump(idx, fh, ensure_ascii=False, indent=1)
    print('  索引已更新：%s' % IDX)

    # ---- ④ 回验：磁盘 vs 索引 ----
    print()
    print('=' * 74)
    print('④ 回验（从磁盘重算，逐个字段比索引）')
    idx2 = json.load(io.open(IDX, encoding='utf-8'))
    by2 = {e.get('id'): e for e in (idx2.get('personas') or []) if isinstance(e, dict)}
    ok_all = True
    for nid in texts:
        e = by2[nid]
        got = calc(read_raw(os.path.join(PDIR, os.path.basename(e['file']))))
        ok = all(got[f] == e.get(f) for f in FIELDS)
        ok_all = ok_all and ok
        print('  %-14s %s' % (nid, 'PASS' if ok else 'FAIL'))
    print('\n结论：%s' % ('PASS' if ok_all else 'FAIL'))
    return 0 if ok_all else 4


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
