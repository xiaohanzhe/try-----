# -*- coding: utf-8 -*-
u"""第85轮 · 把 UTMT 原始产物蒸馏成**可逐字核对的锚点表**。

纪律（第84轮教训）：
  ① 从「产物」抽，不从「我记忆里的源码」抽；
  ② 每条锚点必须能在原始 json 里 `in` 到 —— 蒸馏脚本自己给出回验；
  ③ 抽不到 ⇒ 如实写 `<NOT-FOUND>`，**不许编**。

产物：`_evidence/dr85_anchors.md`
"""
from __future__ import print_function
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, u'_evidence')
CODE = os.path.join(EV, u'dr85_code.json')
GLOB = os.path.join(EV, u'dr85_globals.json')
STRS = os.path.join(EV, u'dr85_strings.json')
OUT = os.path.join(EV, u'dr85_anchors.md')


def load(path):
    with io.open(path, u'r', encoding=u'utf-8') as fh:
        return json.load(fh)


def code_map(doc):
    """name -> src（重名取**最长的**那条，并记录重名）。"""
    m = {}
    dup = {}
    for rec in doc.get(u'codes') or []:
        nm = rec.get(u'name')
        src = rec.get(u'src') or u''
        if nm in m:
            dup.setdefault(nm, 1)
            dup[nm] += 1
            if len(src) > len(m[nm]):
                m[nm] = src
        else:
            m[nm] = src
    return m, dup


def block(src, start_pat, max_lines=200):
    """从 src 里截一段：从匹配 start_pat 的行开始，按大括号配平截到闭合。"""
    lines = src.split(u'\n')
    for i, ln in enumerate(lines):
        if re.search(start_pat, ln):
            depth = 0
            out = []
            for j in range(i, min(len(lines), i + max_lines)):
                out.append(lines[j])
                depth += lines[j].count(u'{') - lines[j].count(u'}')
                if depth <= 0 and j > i:
                    break
            return out, i
    return None, -1


def find_lines(src, pat, limit=12):
    out = []
    for i, ln in enumerate(src.split(u'\n')):
        if re.search(pat, ln):
            out.append((i, ln.rstrip()))
            if len(out) >= limit:
                break
    return out


def sec(title):
    return u'\n## %s\n' % title


def fenced(lines):
    return u'```gml\n' + u'\n'.join(lines) + u'\n```\n'


def main():
    doc = load(CODE)
    gdoc = load(GLOB)
    sdoc = load(STRS)
    codes, dup = code_map(doc)

    buf = []
    buf.append(u'# 第85轮 · 原作锚点表（I1/I2/I4/I5/I10）\n')
    buf.append(u'> 本表由 `_tools/distill85.py` 从 `_evidence/dr85_code.json` '
               u'机械抽取，**每条都可回原 json `in` 一次**。\n')
    buf.append(u'> 抽不到的一律写 `<NOT-FOUND>`，不编造。\n')
    buf.append(u'\n- 产物：`dr85_code.json` code=%s（nonempty=%s / gml_ok=%s），'
               u'`dr85_globals.json` global=%s，`dr85_strings.json` str=%s\n'
               % (doc.get(u'code_count'), doc.get(u'nonempty'), doc.get(u'gml_ok'),
                  gdoc.get(u'global_count'), sdoc.get(u'str_count')))
    if dup:
        buf.append(u'- ⚠️ 重名 code：%s\n' % u', '.join(
            u'%s×%d' % (k, v) for k, v in sorted(dup.items())))

    # ---------------- A. 光/暗世界基准速度 + 跑动三段 ----------------
    buf.append(sec(u'A. 光/暗世界基准速度（`bwspeed`）与跑动三段（I1/I2）'))
    nm = u'gml_Object_obj_mainchara_Create_0'
    src = codes.get(nm)
    if src is None:
        buf.append(u'**%s**: `<NOT-FOUND>`\n' % nm)
    else:
        ls = find_lines(src, u'wspeed|bwspeed|darkmode =')
        buf.append(u'来源：`%s`（%d chars）\n' % (nm, len(src)))
        buf.append(fenced([u'%4d | %s' % (i, t) for i, t in ls]))

    nm = u'gml_Object_obj_mainchara_Step_0'
    src = codes.get(nm)
    if src is None:
        buf.append(u'**%s**: `<NOT-FOUND>`\n' % nm)
    else:
        blk, at = block(src, u'if \\(run == 1\\)')
        buf.append(u'来源：`%s`（%d chars）— `if (run == 1)` 整段（起始行 %d）\n'
                   % (nm, len(src), at))
        buf.append(fenced(blk or [u'<NOT-FOUND>']))
        blk2, at2 = block(src, u'if \\(run == 0\\)')
        buf.append(u'松键回落段（起始行 %d）：\n' % at2)
        buf.append(fenced(blk2 or [u'<NOT-FOUND>']))

    # ---------------- B. 跑表推进（runtimer） ----------------
    buf.append(sec(u'B. 跑表 `runtimer` 的推进与清零（I1 核心）'))
    if src:
        blk, at = block(src, u'runmove = 0;')
        buf.append(u'起始行 %d\n' % at)
        buf.append(fenced(blk or [u'<NOT-FOUND>']))
    buf.append(u'`autorun` 起点（`runtimer = 200 / 50`）：\n')
    if src:
        ls = find_lines(src, u'runtimer = 200|runtimer = 50', limit=4)
        buf.append(fenced([u'%4d | %s' % (i, t) for i, t in ls]))

    # ---------------- C. 按键：confirm / run / menu ----------------
    buf.append(sec(u'C. 按键判定（`button1_p` 确认 / `button2_h` 跑 / `button3_p` 菜单）'))
    if src:
        for pat, why in ((u'button2_h\\(\\)', u'跑键（含 `global.flag\\[11\\]` 反转那条）'),
                         (u'button3_p\\(\\)', u'菜单键'),
                         (u'button1_p\\(\\)', u'确认键'),):
            blk, at = block(src, pat)
            buf.append(u'%s —— `%s`（起始行 %d）：\n' % (why, pat, at))
            buf.append(fenced(blk if blk else [u'<NOT-FOUND>']))

    # ---------------- D. 全局闸 + 输入缓冲（I4/I5） ----------------
    buf.append(sec(u'D. `global.interact` 全局闸 与 输入缓冲（I4/I5）'))
    if src:
        blk, at = block(src, u'if \\(global\\.interact == 0\\)')
        buf.append(u'`obj_mainchara_Step_0` 起始行 %d：\n' % at)
        buf.append(fenced(blk or [u'<NOT-FOUND>']))
    # 缓冲相关：把 twobuffer/threebuffer/onebuffer 全列出来
    buf.append(u'`*buffer` 变量在本 code 里的每次出现：\n')
    if src:
        ls = find_lines(src, u'buffer', limit=40)
        buf.append(fenced([u'%4d | %s' % (i, t) for i, t in ls]))

    # ---------------- E. 被交互者三态（myinteract） ----------------
    buf.append(sec(u'E. 被交互者 `obj_interactablesolid` 的 `myinteract` 三态 + `onebuffer`'))
    for nm in (u'gml_Object_obj_interactablesolid_Step_0',
               u'gml_Object_obj_interactablesolid_Create_0',
               u'gml_Object_obj_interactablesolid_Other_10'):
        s = codes.get(nm)
        if s is None:
            buf.append(u'**`%s`**: `<NOT-FOUND>`\n' % nm)
            continue
        buf.append(u'来源：`%s`（%d chars）\n' % (nm, len(s)))
        buf.append(fenced(s.split(u'\n')[:120]))
    # 把名字里含 interactablesolid / interactable 的都列出来（★ 先探名字）
    hit = sorted(k for k in codes if u'interactable' in k.lower())
    buf.append(u'\n本产物里名字含 `interactable` 的 code（%d 条）—— ★ 先探名再引用：\n' % len(hit))
    for k in hit:
        buf.append(u'- `%s`（%d chars）\n' % (k, len(codes[k])))

    # ---------------- F. 剧情进度计数器 global.plot（I10） ----------------
    buf.append(sec(u'F. 剧情进度计数器 `global.plot`（I10 的唯一真源）'))
    hit = sorted(k for k in codes if u'plot' in k.lower())
    buf.append(u'名字含 `plot` 的 code：%s\n' % (u'、'.join(u'`%s`' % k for k in hit) or u'无'))
    # 在所有 code 里找 `plot >=` 这种判定
    rows = []
    for k in sorted(codes):
        for i, ln in enumerate(codes[k].split(u'\n')):
            if re.search(u'global\\.plot\\s*[><=!]', ln):
                rows.append((k, i, ln.strip()))
    buf.append(u'\n全产物里 `global.plot` 被**比较**的每一处（%d 处）：\n' % len(rows))
    if rows:
        buf.append(u'```text\n')
        for k, i, ln in rows[:60]:
            buf.append(u'%s : %4d | %s\n' % (k, i, ln))
        buf.append(u'```\n')
    else:
        buf.append(u'`<NOT-FOUND>`\n')
    buf.append(u'\n全局变量表里 `plot` 的登记：\n')
    gl = [g for g in (gdoc.get(u'globals') or [])
          if g.get(u'name') == u'plot']
    buf.append(u'```json\n%s\n```\n' % json.dumps(gl, ensure_ascii=False, indent=2))
    buf.append(u'\n同表里 `interact` / `darkzone` / `menuno` 的登记：\n')
    gl2 = [g for g in (gdoc.get(u'globals') or [])
           if g.get(u'name') in (u'interact', u'darkzone', u'menuno',
                                 u'facing', u'sp')]
    buf.append(u'```json\n%s\n```\n' % json.dumps(gl2, ensure_ascii=False, indent=2))

    # ---------------- G. 回验（每条锚点回原 json in 一次） ----------------
    buf.append(sec(u'G. 回验（锚点 → 原 json `in`）'))
    raw = io.open(CODE, u'r', encoding=u'utf-8').read()
    raws = io.open(STRS, u'r', encoding=u'utf-8').read()
    toks = [
        (u'bwspeed = 3;', raw),
        (u'bwspeed = 4;', raw),
        (u'wspeed = bwspeed + 1;', raw),
        (u'wspeed = bwspeed + 2;', raw),
        (u'wspeed = bwspeed + 3;', raw),
        (u'wspeed = bwspeed + 4;', raw),
        (u'wspeed = bwspeed + 5;', raw),
        (u'runtimer += 1;', raw),
        (u'if (runtimer > 10)', raw),
        (u'if (runtimer > 60)', raw),
        (u'runmove = 0;', raw),
        (u'global.interact == 0', raw),
        (u'button2_h()', raw),
        (u'button3_p()', raw),
        (u'global.plot', raw),
        (u'onebuffer', raw),
        (u'myinteract', raw),
    ]
    okc = 0
    buf.append(u'```text\n')
    for t, hay in toks:
        got = t in hay
        okc += 1 if got else 0
        buf.append(u'[%s] %s\n' % (u'OK' if got else u'MISS', t))
    buf.append(u'```\n')
    buf.append(u'\n回验结果：**%d/%d**\n' % (okc, len(toks)))
    if u'plot' not in raws:
        buf.append(u'\n⚠️ 字符串表里没有含 `plot` 的文本 —— '
                   u'"已过完剧情"的**用户可见提示**在原作里**不是字符串表条目**，'
                   u'所以本项目这一条是**扩展**（要如实标注）。\n')

    with io.open(OUT, u'w', encoding=u'utf-8', newline=u'\n') as fh:
        fh.write(u''.join(buf))
    print(u'[ok] %s  (%d bytes)' % (OUT, os.path.getsize(OUT)))
    print(u'[reverify] %d/%d' % (okc, len(toks)))
    return 0


if __name__ == u'__main__':
    sys.exit(main())
