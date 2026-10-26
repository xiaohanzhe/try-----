# -*- coding: utf-8 -*-
"""第113轮k-h：两个"读起来别扭"的收尾（都是全量人读看出来的）。

1. `幽谷 · Dock（dock）` —— 中文类型名查不到时 `place_type_name` 原样返回英文，
   而 `'dock' not in 'Dock'` 因为**大小写**成立 ⇒ 自我括注。改成不区分大小写比。
   期望：`幽谷 · Dock` / `幽谷 · Research Station`（不再重复一遍自己）。
2. `城市（地表区） · Factory（工厂）` —— 区名自带括注，再拼中点就成了两层括注、
   读着分不清哪个是注释。区名里有括注时改用 `PLACE_JOIN_ALT`（` — `）：
   `城市（地表区） — Factory（工厂）`。★ 与 113j 那条「区名自带中点就换分隔符」
   是同一条道理，只是触发条件从「含中点」扩到「含括注」。
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


OLD = """    # ① 已经有像样的名字 ⇒ 原样用（`希望之园 · 理想餐厅` 不许再加 `（餐厅）`）
    if detail:
        if cn and cn not in detail:
            return '%s（%s）' % (detail, cn)
        return detail

    # ② 只剩区名 ⇒ 用原作 id 末段当细节
    body = core
    if body:
        if cn and cn not in body:
            body = '%s（%s）' % (body, cn)
        return (area + sep + body) if area else body
    return area"""

NEW = """    # ★ 区名**自己带括注**（`城市（地表区）`）⇒ 换一个分隔符，否则两层括注
    #   读起来分不清哪个是注释（与 113j「区名自带中点」同一条道理）。
    if area and ('（' in area or '(' in area):
        sep = PLACE_JOIN_ALT

    # ★ 括注去重必须**不分大小写**：`place_type_name('dock')` 查不到中文就原样返回
    #   `dock`，而 `'dock' not in 'Dock'` 会因大小写成立 ⇒ `Dock（dock）` 自我括注。
    #   `casefold()` 比 `lower()` 更稳（土耳其等等，虽然这里用不上）。
    def _has(hay, needle):
        return needle.casefold() in hay.casefold()

    # ① 已经有像样的名字 ⇒ 原样用（`希望之园 · 理想餐厅` 不许再加 `（餐厅）`）
    if detail:
        if cn and not _has(detail, cn):
            return '%s（%s）' % (detail, cn)
        return detail

    # ② 只剩区名 ⇒ 用原作 id 末段当细节
    body = core
    if body:
        if cn and not _has(body, cn):
            body = '%s（%s）' % (body, cn)
        return (area + sep + body) if area else body
    return area"""


def main():
    t = read(LIFE)
    old = OLD.replace('\n', NL)
    new = NEW.replace('\n', NL)
    if new in t:
        print('[SKIP] 已是新版')
    else:
        if old not in t:
            print('[FAIL] 锚点没命中')
            return 1
        t = t.replace(old, new, 1)
        write(LIFE, t)
        print('[ OK ] place_label 大写不敏感 + 括注区名换分隔符')
    import ast
    src = read(LIFE)
    try:
        ast.parse(src)
        print('[ OK ] 语法 PASS')
    except SyntaxError as e:
        print('[FAIL] 语法 %s' % e)
        return 1
    print('行=%d CRLF=%d gap=%d' % (src.count('\n'), src.count('\r\n'),
                                   src.count('\n') - src.count('\r\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
