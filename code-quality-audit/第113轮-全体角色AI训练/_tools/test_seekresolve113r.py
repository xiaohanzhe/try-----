# -*- coding: utf-8 -*-
u"""第113轮r · `gen_seek113p.pick_id` 的「剥尾部括号注释」自测（8 条）。

为什么值得单独锁：
  `_seek.json` 决定「NPC 想去找谁」，而**猜错就是把 A 的偏好挂到 B 头上**——
  产品不会报错，只会让某人莫名其妙天天往另一个人那儿跑。所以：
    · 正向要能解开 `Silver（总工程师）` → `os_silver`；
    · **反向更要紧**：`Sans（ambiguous）` 必须**仍然**判重名（`ot_sans`/`ut_sans`），
      `母亲`/`Kanako` 必须**仍然**判 unknown（名册外），一个都不许被"剥"出名分来；
    · 消歧规则不许因此退化：`Toriel（她妈妈）` 从 kris 视角仍应落到 Deltarune 的
      `toriel`，不是 `ot_toriel`/`ut_toriel`。

名册索引**用真卡现造**（`assets/npc/_training/cards/*.json`），不用手写桩 ——
桩比产品旧就是假红（第107轮教训）。
"""
import glob
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CARDS = os.path.join(HERE, '..', '..', '..', 'ralsei_pet', 'assets', 'npc',
                     '_training', 'cards')

_n = _ok = 0


def check(name, cond, detail=''):
    global _n, _ok
    _n += 1
    if cond:
        _ok += 1
        print('[PASS] %s    %s' % (name, detail))
    else:
        print('[FAIL] %s    %s' % (name, detail))


def load():
    p = os.path.join(HERE, 'gen_seek113p.py')
    spec = importlib.util.spec_from_file_location('gs113r', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def index():
    by_name, by_lower, by_cn, ids = {}, {}, {}, set()
    for f in sorted(glob.glob(os.path.join(CARDS, '*.json'))):
        c = json.load(open(f, encoding='utf-8'))
        ids.add(c['id'])
        for x in (c.get('name'), c.get('name_cn')):
            if not x:
                continue
            by_name.setdefault(x, []).append(c['id'])
            by_lower.setdefault(str(x).lower(), []).append(c['id'])
            by_cn.setdefault(x, []).append(c['id'])
    return by_name, by_lower, by_cn, ids


def main():
    m = load()
    by_name, by_lower, by_cn, ids = index()
    assert len(ids) >= 77, '名册只有 %d 人，卡片目录可能不对' % len(ids)

    # ---- A 正向：带注释的名字能解开（这条就是本次修的东西）
    got = m.pick_id(u'Silver（总工程师）', 'os_rowbot', by_name, by_lower, by_cn, ids)
    check('A ★ 正向：`Silver（总工程师）` 从 os_rowbot 视角解到 `os_silver`',
          got == ('os_silver', 'ok'), repr(got))

    # ---- B ★★ 负控制：本文件自己加的 `（ambiguous）` 不许被剥成"有名字"
    got = m.pick_id(u'Sans（ambiguous）', 'asgore', by_name, by_lower, by_cn, ids)
    check('B ★★ 负控制：`Sans（ambiguous）` 仍判重名（ot_sans/ut_sans 两个候选）',
          got == (None, 'ambiguous'), repr(got))

    # ---- C ★★ 负控制：名册外的人不许因为"剥括号"被认领
    for nm in (u'母亲', u'Kanako', u'后备机器人'):
        got = m.pick_id(nm, 'hy_guardener', by_name, by_lower, by_cn, ids)
        check('C ★★ 负控制：`%s` 仍判 unknown（名册里没有）' % nm,
              got == (None, 'unknown'), repr(got))

    # ---- D 消歧规则没被破坏：从 kris 视角 Toriel 仍应是 Deltarune 本体那个
    got = m.pick_id(u'Toriel（她妈妈）', 'kris', by_name, by_lower, by_cn, ids)
    check('D 按作品前缀消歧仍生效：`Toriel（她妈妈）` → `toriel`（不是 ot_/ut_）',
          got == ('toriel', 'ok'), repr(got))

    # ---- E `_strip_note` 自身的边界
    check('E `_strip_note` 不剥太短的核心（`A（b）` 剥完只剩 1 字 ⇒ 原样返回）',
          m._strip_note(u'A（b）') == u'A（b）', repr(m._strip_note(u'A（b）')))
    # ★ 夹具别用单字核心：`X（unknown）` 的核心只有 1 字，按设计**本来就不剥**
    #   （E 那条测的就是这个），拿它来测"照剥"必然假红。
    check('E2 `_strip_note` 是**纯字符串**操作：`（ambiguous）` 也照剥 '
          '（"该不该信"归 pick_id 的原因回传管，塞进来会让 B 退化）',
          m._strip_note(u'Sans（ambiguous）') == u'Sans' and
          m._strip_note(u'Zsasz（unknown）') == u'Zsasz',
          repr(m._strip_note(u'Sans（ambiguous）')))
    check('E3 `_strip_note` 对多层括号会逐层变短、必然终止（不死循环）',
          m._strip_note(u'Silver（a）（b）') in (u'Silver（a）（b）', u'Silver（a）', u'Silver'),
          repr(m._strip_note(u'Silver（a）（b）')))
    # ★ 原因必须**回传**，不能被"剥"这一步吞掉：`X（unknown）` 剥完 `X` 解不出，
    #   若不回传就会把它记成 unknown 以外的别的东西，或者静默变成别的名字。
    got = m.pick_id(u'Zsasz（unknown）', 'kris', by_name, by_lower, by_cn, ids)
    check('E4 剥完仍解不出时，括号里的原因要回传（`（unknown）` ⇒ unknown）',
          got == (None, 'unknown'), repr(got))

    print('\n' + '=' * 60)
    print('合计：PASS=%d FAIL=%d' % (_ok, _n - _ok))
    print('=' * 60)
    return 0 if _ok == _n else 1


if __name__ == '__main__':
    sys.exit(main())
