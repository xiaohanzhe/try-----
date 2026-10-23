# -*- coding: utf-8 -*-
"""第113轮 · 关系卡接线复检（改过 prompt 唯一出口就必须逐项验）

判据（每条都有正/负控制，避免"看着在守其实没守"）：
  A1 不传 relation 与传 '' ⇒ prompt **逐字相同**（回归锁 C1 的同一性质）
  A2 传 relation ⇒ 该块出现在 WHO_IS_TALKING 之后、SPEAK_RULES 之前
  A3 负控制：不传 relation 时，prompt 里**不许**出现关系块标题
  B1 `relation_patch('susie')` 非空，且内容确实讲到 Lancer
  B2 负控制：`relation_patch('不存在')` == ''
  B3 负控制：assets_dir 指向空目录 ⇒ ''（读盘失败不抛）
  C1 产品真接线：`main.py` 里 `npc_system_prompt` 调用 `relation_patch`
  C2 无关系卡的角色（gerson）⇒ '' 且 prompt 与"不传"逐字相同
"""
import ast
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
sys.path.insert(0, PET)

from modules import npc_persona as NP  # noqa: E402

FAILED = []


def check(name, ok, detail=''):
    print('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                       '' if not detail else '  ' + detail)) 
    if not ok:
        FAILED.append(name)


def main():
    persona = '我是 Susie，说话很短。'
    base = NP.build_system_prompt('Susie', persona, entries=None, npc_id='susie')

    # A1
    with_empty = NP.build_system_prompt('Susie', persona, entries=None, npc_id='susie',
                                        relation='')
    check('A1 不传 relation 与传空串逐字相同', base == with_empty,
          '%d vs %d 字' % (len(base), len(with_empty)))

    # A3 负控制：不传时不许有关系块
    check('A3 未传 relation 时不含关系块标题',
          '【你和其他人的关系' not in base)

    # A2
    rel = NP.relation_patch('susie')
    with_rel = NP.build_system_prompt('Susie', persona, entries=None, npc_id='susie',
                                      relation=rel)
    head = '【你和其他人的关系（照这个，别自己编）】'
    i_rel = with_rel.find(head)
    i_who = with_rel.find(NP.WHO_IS_TALKING)
    i_rules = with_rel.find(NP.SPEAK_RULES)
    check('A2 关系块位置正确（WHO 之后 / SPEAK_RULES 之前）',
          -1 < i_who < i_rel < i_rules,
          'who=%d rel=%d rules=%d' % (i_who, i_rel, i_rules))

    # B1
    check('B1 relation_patch(susie) 非空且讲到 Lancer',
          bool(rel) and 'Lancer' in rel, '%d 字' % len(rel))

    # B2 负控制
    check('B2 负控制：不存在的 id ⇒ 空串', NP.relation_patch('no_such_npc_xyz') == '')

    # B3 负控制：读盘失败
    with tempfile.TemporaryDirectory() as td:
        NP._PATCH_CACHE.pop(('rel', 'susie', td), None)
        got = NP.relation_patch('susie', assets_dir=td)
    check('B3 负控制：assets_dir 为空目录 ⇒ 空串（不抛）', got == '')

    # C1 真接线（AST，不靠字符串扫，避免注释里提到函数名就误报）
    src = io.open(os.path.join(PET, 'src', 'main.py'), encoding='utf-8').read()
    tree = ast.parse(src)
    hit = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'build_system_prompt':
            for kw in node.keywords:
                if kw.arg == 'relation' and isinstance(kw.value, ast.Call) \
                        and isinstance(kw.value.func, ast.Attribute) \
                        and kw.value.func.attr == 'relation_patch':
                    hit = True
    check('C1 main.py 真接线 relation_patch → build_system_prompt', hit)

    # C2 无卡角色
    no_card = NP.relation_patch('gerson')
    other = NP.build_system_prompt('Gerson', '我是 Gerson。', npc_id='gerson',
                                   relation=no_card)
    ref = NP.build_system_prompt('Gerson', '我是 Gerson。', npc_id='gerson')
    check('C2 无卡角色 relation 为空串，prompt 与不传时相同',
          no_card == '' and other == ref,
          'no_card=%r 相同=%s %d/%d 字' % (no_card[:30], other == ref, len(other), len(ref)))
    if other != ref:
        for i, (x, y) in enumerate(zip(other, ref)):
            if x != y:
                print('    首个差异 @%d: %r || %r'
                      % (i, other[max(0, i - 30):i + 30], ref[max(0, i - 30):i + 30]))
                break

    print('—' * 46)
    print('FAIL=%d' % len(FAILED))
    return 0 if not FAILED else 1


if __name__ == '__main__':
    sys.exit(main())
