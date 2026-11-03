# -*- coding: utf-8 -*-
u"""第149轮 · 勘察：**「显示切换的唯一驱动 = 灵魂」这条口径，本地这棵树上到底成立不成立**。

## 为什么先查这个

记忆里 §109.5 一直标"未实现"。但动手前查到两件必须先说清的事：

1. 本地 `main` 与 `origin/main` **早已分叉**（分叉点 `0efda6b5` / 第110轮）。当年就核查过并
   定案（`7e0bafe6` 第113轮补记）：「故本轮成果只落本地 commit，**未推送**；强推会覆盖主线
   第114~118轮」。之后改成推 `local-N` 分支。
   ⇒ **差事（`npc_errand`）那两轮在第113/114的远端线上**（`ac3b9e31` / `844bda0a`），
   本地这棵树里**根本没有**。

2. 所以"§109.5 未实现"在本地是**真话**，但它不等于"什么都没做" —— 三条口径里，
   前两条（NPC 自己移动不切显示 / 离场仍存在）本地**已经成立**，第三条（差事）**缺口**。

## 本脚本只做勘察，不改任何东西

产出：
  A 所有 `switch()/travel_to()` 调用点 + 所在函数 + 谁驱动它；
  B NPC 侧四个模块（`npc_roam`/`npc_life`/`npc_intent`/`npc_placement`）是否碰显示；
  C 差事机制在本地是否存在（`npc_errand` 模块 / `_npc_errand_*` 函数）；
  D 落 `_evidence/measure149.json`（只放稳定结论，不放行号/时间戳）。
"""
import ast
import io
import json
import os

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src', 'main.py')
MODS = os.path.join(PET, 'modules')
EVID = os.path.join(ROUND, '_evidence')

SWITCHERS = ('switch', 'travel_to')
NPC_MODS = ('npc_roam.py', 'npc_life.py', 'npc_intent.py', 'npc_placement.py')


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _lf(t):
    return t.replace(u'\r\n', u'\n')


def say(s):
    import sys
    sys.stdout.write(s + u'\n')


def _enclosing(tree, lineno):
    best = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = n.end_lineno or n.lineno
            if n.lineno <= lineno <= end:
                if best is None or n.lineno > best.lineno:
                    best = n
    return best.name if best else u'<模块级>'


def _calls(tree, names):
    u"""[(名字, 所在函数)] —— 只认 `ast.Call`，注释/字符串里提一句不算。"""
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = getattr(f, 'attr', '') or getattr(f, 'id', '')
        if nm in names:
            out.append((nm, _enclosing(tree, n.lineno)))
    return out


def main():
    src = _lf(_read(SRC))
    tree = ast.parse(src)

    say(u'== A 显示切换的调用点 ==')
    hits = _calls(tree, SWITCHERS)
    for nm, host in sorted(hits, key=lambda x: x[1]):
        say(u'   %-10s ← %s' % (nm, host))
    say(u'   共 %d 处' % len(hits))

    # 往上追两层：这些 host 又是由谁调的
    hosts = sorted(set(h for _n, h in hits))
    say(u'')
    say(u'== A2 往上一层（谁触发这些 host）==')
    up = {}
    for h in hosts:
        callers = sorted(set(host for _n, host in _calls(tree, (h,))))
        up[h] = callers
        say(u'   %-28s ← %s' % (h, u', '.join(callers) or u'（无内部调用者）'))

    say(u'')
    say(u'== B NPC 侧是否碰显示 ==')
    npc_hits = {}
    for fn in NPC_MODS:
        p = os.path.join(MODS, fn)
        t = ast.parse(_lf(_read(p)))
        # 只看调用；属性名 current_scene 也算（读它=关心显示）
        c = _calls(t, SWITCHERS)
        attr = [n for n in ast.walk(t)
                if isinstance(n, ast.Attribute) and n.attr == 'current_scene']
        npc_hits[fn] = {'calls': len(c), 'current_scene_refs': len(attr)}
        say(u'   %-18s 切换调用 %d 处 · 读 current_scene %d 处'
            % (fn, len(c), len(attr)))

    say(u'')
    say(u'== C 差事机制在本地是否存在 ==')
    errand_mod = os.path.join(MODS, 'npc_errand.py')
    has_mod = os.path.exists(errand_mod)
    errand_fns = [n.name for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and u'errand' in n.name]
    say(u'   modules/npc_errand.py 存在：%s' % has_mod)
    say(u'   main.py 里 `*errand*` 函数：%d 个' % len(errand_fns))
    if not has_mod and not errand_fns:
        say(u'   ⇒ 本地**零实现**。远端线（origin/main）有：')
        say(u'     `ac3b9e31` 第113轮：§109.5 机制层 —— NPC 差事（npc_errand）')
        say(u'     `844bda0a` 第114轮：差事「世界门控 + 派发入口 + 独立落盘」')
        say(u'     （两条都在 `origin/main` 与 `workbuddy/main-a7556e9c` 上，'
            u'不在本地 main 的祖先链里）')

    out = {
        'switch_calls': sorted([{'name': n, 'host': h} for n, h in hits],
                               key=lambda x: (x['host'], x['name'])),
        'switch_callers': up,
        'npc_modules': npc_hits,
        'npc_touches_display': any(v['calls'] or v['current_scene_refs']
                                   for v in npc_hits.values()),
        'errand_module_present': has_mod,
        'errand_funcs_in_main': len(errand_fns),
        'fork_point': u'0efda6b5（第110轮）',
        'remote_only_commits': [u'ac3b9e31 第113轮差事机制层',
                                u'844bda0a 第114轮差事门控/派发/落盘'],
    }
    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    with io.open(os.path.join(EVID, 'measure149.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    say(u'')
    say(u'证据已落 `_evidence/measure149.json`')


main()
