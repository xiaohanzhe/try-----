# -*- coding: utf-8 -*-
u"""第113轮s · `eval113` 的两处修复自测（12 条）。

背景（都是**真发生过**的静默失效，不是假想）：
  ① `load_all` 原来只认 `phase == 'baseline'`，而 `train30` 写的是 `phase='t30'`；
     同一个文件里两条都在 ⇒ 评测一直在评**旧的 4 轮冒烟记录**，
     77 人只产出 **2 条** patch，48 轮实测的 419 次 `ACTION_PAREN` 一条没回产品。
  ② `main` 里 `idx['patches'] = patches` 是**整体替换** ⇒ 会把别的轮
     **手写**的 `ralsei` 名字规则删掉（那轮是为了「凯斯恩」这类拼名才加的）。

对应判据：A/A2 证明"选法变了且确实不同"、B/C/D 是边界、
E~E4 是并集规则、F/F2 是"不许删旧键"的正负对照、G 用真 `_index.json` 做一次集成核对。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common113 as C      # noqa: E402
import eval113 as E        # noqa: E402

_n = _ok = 0


def check(name, cond, detail=''):
    global _n, _ok
    _n += 1
    if cond:
        _ok += 1
        print('[PASS] %s    %s' % (name, detail))
    else:
        print('[FAIL] %s    %s' % (name, detail))


def rec(phase, turns, turns_n=None):
    r = {'phase': phase, 'turns': [{'i': i} for i in range(turns)]}
    if turns_n is not None:
        r['turns_n'] = turns_n
    return r


def main():
    # ---- A ★ 主记录必须按**轮数**挑，而不是按 phase 名字挑
    recs = [rec('baseline', 4), rec('t30', 48, 48)]
    picked = E.pick_main_record(recs)
    check('A ★ 同文件里「4 轮 baseline + 48 轮 t30」⇒ 必须挑 48 轮那条',
          picked is not None and picked.get('phase') == 't30', repr(picked.get('phase')))

    # ---- A2 负回归：旧写法（next(...=='baseline')）会挑到 4 轮那条 ⇒ 证明差异真实存在
    old_pick = next((r for r in recs if r.get('phase') == 'baseline'), None)
    check('A2 ★★ 负回归：旧写法挑到的是 4 轮那条，与新写法**不同**（差异真实）',
          old_pick is not None and old_pick.get('phase') == 'baseline'
          and picked is not old_pick,
          '旧=%s 新=%s' % (old_pick.get('phase'), picked.get('phase')))

    # ---- B 轮数相同 ⇒ 优先 baseline（老口径偏好，别让 t30 无理由抢走）
    tie = E.pick_main_record([rec('t30', 4), rec('baseline', 4)])
    check('B 轮数打平时优先 baseline', tie.get('phase') == 'baseline', repr(tie.get('phase')))

    # ---- C 只有 patch 记录时不许整个人消失（返回它，而不是 None）
    only_patch = E.pick_main_record([rec('patch', 4)])
    check('C 只有 patch 记录 ⇒ 仍返回它（不许让这个角色凭空消失）',
          only_patch is not None and only_patch.get('phase') == 'patch',
          repr(only_patch and only_patch.get('phase')))

    # ---- D 空输入
    check('D 空输入 ⇒ None（不抛）', E.pick_main_record([]) is None)

    # ---- E~E4 并集规则
    check('E 旧是新超集 ⇒ 原样保留旧的',
          E.merge_text(u'不要用括号写动作。别重复。', u'不要用括号写动作。')
          == u'不要用括号写动作。别重复。', '')
    check('E2 新是旧超集 ⇒ 用新的',
          E.merge_text(u'不要用括号写动作。', u'不要用括号写动作。别重复。')
          == u'不要用括号写动作。别重复。', '')
    u3 = E.merge_text(u'只认名字。', u'别重复。')
    check('E3 ★ 互不包含 ⇒ 求并集，两句都在（**不许二选一**）',
          u'只认名字' in u3 and u'别重复' in u3, repr(u3))
    check('E4 完全相同 ⇒ 不变', E.merge_text(u'别重复。', u'别重复。') == u'别重复。', '')
    check('E5 空值两端都安全', E.merge_text('', u'X。') == u'X。'
          and E.merge_text(u'X。', '') == u'X。' and E.merge_text('', '') == '')

    # ---- F ★★ 不许删掉"本轮算不出来"的旧补丁
    old = {'ralsei': u'只认得原作里真有的名字。不要自己造人名。'}
    new = {'susie': u'不要用括号写动作。'}
    merged, rep = E.merge_patches(old, new)
    check('F ★★ 只在新集合里的键不许丢：`ralsei` 必须还在且内容不变',
          merged.get('ralsei') == old['ralsei'] and 'susie' in merged,
          '键=%s' % sorted(merged))

    # ---- F2 负回归：直接整体替换会丢掉 ralsei ⇒ 证明这条守卫不是恒真
    check('F2 ★★ 负回归：`dict(new)` 整体替换后 `ralsei` 不见了（差异真实存在）',
          'ralsei' not in dict(new), '整体替换只剩 %s' % sorted(new))

    # ---- G 集成核对：用**真** `_index.json` 做一次（只读，不写盘）
    idx_path = os.path.join(C.TRAIN_DIR, '_index.json')
    real = (C.load_json(idx_path, {}) or {}).get('patches') or {}
    ral = real.get('ralsei') or ''
    if not ral:
        check('G 真 `_index.json` 里有 ralsei 的手写补丁（没有就跳过这条）', True,
              '跳过：当前没有 ralsei 补丁')
    else:
        m2, _ = E.merge_patches(real, {'ralsei': u'一次最多两三句，短一点。'})
        check('G ★ 真数据上跑并集：手写的「不要自己造人名」仍在',
              u'不要自己造人名' in (m2.get('ralsei') or ''),
              '%d 字' % len(m2.get('ralsei') or ''))

    print('\n' + '=' * 60)
    print('合计：PASS=%d FAIL=%d' % (_ok, _n - _ok))
    print('=' * 60)
    return 0 if _ok == _n else 1


if __name__ == '__main__':
    sys.exit(main())
