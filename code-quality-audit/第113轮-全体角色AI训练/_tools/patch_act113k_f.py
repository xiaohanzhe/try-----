# -*- coding: utf-8 -*-
"""第113轮k-f：细节词截到**类型词为止**。

问题（实测）：
    `家乡 · hospital hallway（医院）` —— 去重键挑中的是 `hospital_hallway`（sid 升序
    第一条）。「那要不去医院的走廊办事」不像人话：走廊在原作里不是个"去处"。
    同类：`library upstairs`、`spamton shop interior`、`couch overworld`。

★ 规则：**类型词之后**的词一律截掉，**之前**的留着。
  · 之前的是**店名前半截**：`icee pizza` 的 `icee`、`castle cafe` 的 `castle`、
    `fire restaurant` 的 `fire` —— 去掉就剩「披萨店」「咖啡店」，模型分不清是哪一家。
  · 之后的是**同一栋楼里的具体房间**：`lobby` / `hallway` / `upstairs` /
    `interior` / `overworld` —— 留着会把"去哪儿"说成"去那栋楼的某间房"。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
LIFE = os.path.join(PET, 'modules', 'npc_life.py')
NL = '\r\n'


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(t)


ADD = '''def trim_core_at_type(core, hits):
    """把 `core` 截到**类型词为止**：`hospital hallway` → `hospital`。

    ★★ 为什么必须截（正反两面都是实测）：
      · 类型词**之后**的是**同一栋楼里的具体房间**（`hospital lobby` / `hospital
        hallway` / `library upstairs` / `shop interior` / `couch overworld`）——
        留着会把"去哪儿"说成"去那栋楼的某间房"，而走廊/楼上在原作里不是去处。
      · 类型词**之前**的是**店名的前半截**（`icee pizza` / `castle cafe` /
        `fire restaurant` / `b3bs shop` / `city spamton shop`）—— 截掉就只剩
        「披萨店」「咖啡店」，同城几家店全糊成一个，模型说不出是哪一家。
    ★ 只按**空白分词**比：中文词（`餐` / `咖啡` / `舞台`）出现在**真名**里，
      走的是 `detail` 那一支，根本不进这里。
    ★ 命中不到类型词（`plat lab` 之类分词怪例）⇒ **原样返回**，不猜。
    """
    toks = str(core or '').split()
    if len(toks) < 2:
        return ' '.join(toks)
    lows = [t.lower() for t in toks]
    cut = -1
    for h in (hits or ()):
        h = str(h or '').strip().lower()
        if not h or ' ' in h:
            continue
        if h in lows:
            cut = max(cut, lows.index(h))
    if cut < 0 or cut >= len(toks) - 1:
        return ' '.join(toks)
    return ' '.join(toks[:cut + 1])


'''

ANCHOR = 'def place_label(area, detail, core, hits, sep=PLACE_SEP):'

WIRE_OLD = "    core = strip_room_index(' '.join(str(core or '').split()))"
WIRE_NEW = ("    core = trim_core_at_type(\n"
            "        strip_room_index(' '.join(str(core or '').split())), hits)")


def main():
    t = read(LIFE)
    if 'def trim_core_at_type(' in t:
        print('[SKIP] 已有 trim_core_at_type')
    else:
        if ANCHOR not in t:
            print('[FAIL] 锚点没命中')
            return 1
        t = t.replace(ANCHOR, ADD.replace('\n', NL) + ANCHOR, 1)
        print('[ OK ] 插入 trim_core_at_type')
    if WIRE_NEW.replace('\n', NL) in t:
        print('[SKIP] place_label 已接线')
    else:
        old = WIRE_OLD
        if old not in t:
            print('[FAIL] 接线锚点没命中')
            return 1
        t = t.replace(old, WIRE_NEW.replace('\n', NL), 1)
        print('[ OK ] place_label 接线')
    write(LIFE, t)

    import ast
    src = read(LIFE)
    try:
        ast.parse(src)
        print('[ OK ] 语法 PASS')
    except SyntaxError as e:
        print('[FAIL] 语法 %s' % e)
        return 1
    n = src.count('\n')
    crlf = src.count('\r\n')
    print('行=%d CRLF=%d gap=%d' % (n, crlf, n - crlf))
    return 0


if __name__ == '__main__':
    sys.exit(main())
