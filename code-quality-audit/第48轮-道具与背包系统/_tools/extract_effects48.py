# -*- coding: utf-8 -*-
"""第48轮 · 从五章真反编译 GML 里**机器抽取**道具效果（可复跑）。

为什么要单独一个文件：效果表是产品数据层的唯一事实来源，
一旦是"手抄进生成器"的，就没法证明它跟原作一致。抽成独立、可复跑的脚本后，
任何人重跑一遍就能得到同一份 `_evidence/items_effects48.json`。

输入：`E:\\Download\\_tmp\\drw\\chapterN_windows\\gml48b\\gml_GlobalScript_scr_{itemuse,litemuseb,itemnamelist,litemname}.gml`
输出：`_evidence/items_effects48.json`

★ 两个已修的坑（都是"判据过窄"型）
1. `reviveamt = ceil(global.maxhp[global.char[global.charselect]] / 2)`
   —— 下标**嵌套**，`\[[^\]]+\]` 匹配不到 ⇒ 改用"出现 `reviveamt = ceil(` 就算复活"。
   漏掉它的后果：复活薄荷被归成 `none`（**一条效果无声消失**）。
2. 名字表里存在、但 `scr_itemuse` 里没有 `case` 的道具（例如 ch1 的 id 3）
   —— 只看 use 分支会**漏条目** ⇒ 与 `scr_itemnamelist` / `scr_litemname` 求并集。

用法: C:\\Python311\\python.exe extract_effects48.py [E:\\Download\\_tmp\\drw]
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
OUT = os.path.join(ROUND, '_evidence', 'items_effects48.json')
DEFAULT_ROOT = r'E:\Download\_tmp\drw'


def read(root, ch, name):
    p = os.path.join(root, 'chapter%d_windows' % ch, 'gml48b', name)
    if not os.path.isfile(p):
        return ''
    return io.open(p, encoding='utf-8', errors='replace').read()


def cases(text, pattern=r'\n\s*case\s+(\d+):\s*\n'):
    """把 switch 的 case 切成 {id: body}。"""
    out = {}
    parts = re.split(pattern, '\n' + text)
    i = 1
    while i < len(parts) - 1:
        out[int(parts[i])] = parts[i + 1]
        i += 2
    return out


def dark_effects(body):
    eff = []
    if 'reviveamt' in body:
        eff.append(['revive', 0])
    for m in re.finditer(r'scr_healitem_all\(\s*(\d+)\s*\)', body):
        eff.append(['heal_all', int(m.group(1))])
    for m in re.finditer(r'scr_healitem\(\s*[^,]+,\s*(\d+)\s*\)', body):
        eff.append(['heal', int(m.group(1))])
    if 'obj_darkphone_event' in body:
        eff.append(['phone', 0])
    if 'snd_egg' in body:
        eff.append(['egg', 0])
    if 'obj_dialoguer' in body:
        eff.append(['dialog', 0])
    per = {}
    for m in re.finditer(r'global\.char\[global\.charselect\]\s*==\s*(\d+)\)\s*\{(.*?)\n\s*\}',
                         body, re.S):
        mm = re.search(r'scr_healitem\(\s*global\.charselect,\s*(\d+)\s*\)', m.group(2))
        if mm:
            per[m.group(1)] = int(mm.group(1))
    if per:
        eff.append(['per_char', per])
    return eff


def light_effects(body):
    eff = []
    if 'scr_lweaponeq' in body:
        eff.append(['equip', 0])
    if 'scr_lrecoitem' in body:
        eff.append(['recover', 0])
    if 'scr_litemshift' in body:
        eff.append(['consume', 0])
    if 'snd_egg' in body:
        eff.append(['egg', 0])
    if re.search(r'\broom\s*==', body):
        eff.append(['room_gate', 0])
    if 'scr_writetext' in body:
        eff.append(['text', 0])
    return eff


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    out = {}
    for ch in range(1, 6):
        dark = {}
        for cid, body in cases(read(root, ch, 'gml_GlobalScript_scr_itemuse.gml')).items():
            dark[cid] = dark_effects(body)
        for cid in re.findall(r'case\s+(\d+)\s*:', read(root, ch, 'gml_GlobalScript_scr_itemnamelist.gml')):
            dark.setdefault(int(cid), [])
        light = {}
        for cid, body in cases(read(root, ch, 'gml_GlobalScript_scr_litemuseb.gml')).items():
            light[cid] = light_effects(body)
        for cid in re.findall(r'itemid\s*==\s*(\d+)', read(root, ch, 'gml_GlobalScript_scr_litemname.gml')):
            light.setdefault(int(cid), [])
        out['ch%d' % ch] = {
            'dark': {str(k): dark[k] for k in sorted(dark)},
            'light': {str(k): light[k] for k in sorted(light)},
        }

    if os.path.isfile(OUT):
        os.remove(OUT)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))

    for ch, v in out.items():
        d, l = v['dark'], v['light']
        revive = [k for k, e in d.items() if any(x[0] == 'revive' for x in e)]
        print('%s 暗 %d 条（含复活 %s） / 光 %d 条' % (ch, len(d), ','.join(revive) or '无', len(l)))
    print('输出：%s' % OUT)


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    main()
