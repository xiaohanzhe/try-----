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

    # ---- H~H3 元叙事豁免（`_persona_is_meta`）
    #    ★ 为什么要有：OneShot 系的「玩家/代码/世界机器」**就是设定内核**，
    #      对他们写「别提…玩家、代码」= 要求角色违反自己的人设。
    #      而 `berdly`/`noelle` 虽然爱打游戏，`_META_RE` **并不抓「游戏」**这个词
    #      （只抓 Deltarune/Undertale/游戏角色/玩家/开发者/代码/脚本/桌宠/程序里），
    #      他们实测撞的是「Deltarune」「游戏角色」「开发者」⇒ 补丁该留。
    #    ★ 夹具必须用**真人设原文**：第一版我手写了一段，只有 3 次命中、被判不豁免
    #      ⇒ 又栽在"夹具不保真"上。真数据里这 8 个人是 7~59 次，
    #      模板句最多 2 次 ⇒ 阈值 5 两边都有余量，不是我凑出来的。
    pdir = os.path.join(C.NPC_DIR, 'persona')
    wm_path = os.path.join(pdir, 'os_the_world_machine.txt')
    with open(wm_path, 'r', encoding='utf-8') as fh:
        persona_wm = fh.read()
    ok, n = C._persona_is_meta(persona_wm)
    check('H ★★ 真人设 `os_the_world_machine` ⇒ 判豁免', ok and n >= 5, '命中 %d 次' % n)

    boiler = u'· 用纯文本说话，不要用 markdown（不要 # 标题、不要 * 或 - 列表、不要代码块、不要表格）。'
    ok2, n2 = C._persona_is_meta(boiler)
    check('H2 ★★ 负控制：只有模板句里的"代码块" ⇒ **不豁免**（噪声 1~2 次，远低于阈值 5）',
          not ok2, '命中 %d 次' % n2)

    ok3, n3 = C._persona_is_meta('')
    check('H3 空人设 ⇒ 不豁免、不抛', not ok3 and n3 == 0, '命中 %d 次' % n3)

    # 真数据：8 个元叙事角色应被豁免，而"只是模板句撞词"的不该
    roster_p = {r['id']: (r.get('persona') or '') for r in C.load_roster()[0]}
    should = ['os_niko', 'os_rowbot', 'os_the_author', 'os_the_world_machine',
              'os_shepherd', 'os_cedric', 'os_rue', 'ut_papyrus']
    miss = [i for i in should if not C._persona_is_meta(roster_p.get(i, ''))[0]]
    check('H4 8 个 OneShot/UT 元叙事角色在真数据上全部判豁免', not miss,
          '漏: %s' % (miss or '无'))

    # ---- I 组：豁免必须**逐条按命中词**判（H4 只管"这个人是不是元叙事"）----
    #   ★★ 这一段是修一个真错：第一版按 `v[0] != 'META'` 整类剔，
    #      于是 `ut_papyrus` 的「《Undertale》中的 Papyrus 就是这样被设计」
    #      也被当成"照设定说话"放过了。人元叙事 ≠ 每句话都合规。
    import common113 as _C
    check('I  ★★ 硬词 `Undertale` 不许豁免（ut_papyrus 真数据里的原话）',
          not _C.meta_hit_is_soft('出戏词：Undertale'))
    check('I2 负控制：软词 `玩家` 可以豁免（os_niko 的设定内核）',
          _C.meta_hit_is_soft('出戏词：玩家'))
    check('I3 `程序里`（_META_RE 产出的就是这个词）算软词', _C.meta_hit_is_soft('出戏词：程序里'))
    check('I4 ★ 认不出的词一律**不豁免**（判据方向守死）',
          not _C.meta_hit_is_soft('出戏词：某个我没登记过的词'))
    check('I5 空 / 没有冒号 ⇒ 不豁免，不抛',
          not _C.meta_hit_is_soft('') and not _C.meta_hit_is_soft(None)
          and not _C.meta_hit_is_soft('META'))
    check('I6 大写 `DELTARUNE` 同样算硬词（比较前统一 lower）',
          not _C.meta_hit_is_soft('出戏词：DELTARUNE'))

    # I7 ★ 端到端：同一条 META 违规，换成硬词/软词，patch 结果必须相反
    def _mk(nid, detail):
        rec = {'phase': 't30', 'turns_n': 1, 'turns': [
            {'i': 1, 'final': 'x', 'violations': [['META', detail]]}]}
        return {nid: {'baseline': rec}}

    rb = {'ut_papyrus': {'persona': roster_p.get('ut_papyrus', '')},
          'os_niko': {'persona': roster_p.get('os_niko', '')}}
    p_hard = E.build_patches(_mk('ut_papyrus', '出戏词：Undertale'), {}, [], rb)[0]
    p_soft = E.build_patches(_mk('os_niko', '出戏词：玩家'), {}, [], rb)[0]
    check('I7 ★★ 端到端：papyrus 撞 `Undertale` ⇒ 仍有 META 补丁',
          '作品名' in (p_hard.get('ut_papyrus') or ''),
          '%r' % (p_hard.get('ut_papyrus') or ''))
    check('I8 ★★ 端到端：niko 撞 `玩家` ⇒ 无补丁（没有别的毛病就不该动 prompt）',
          not p_soft.get('os_niko'), '%r' % (p_soft.get('os_niko') or ''))

    # I9 ★★ I8 的正控制：**同一个人设**，只把命中词从软换成硬 ⇒ 必须出补丁。
    #    没有这一条，I8 的"没补丁"可能只是"niko 这个夹具本来就不出补丁"（恒真）。
    p_niko_hard = E.build_patches(_mk('os_niko', '出戏词：Deltarune'), {}, [], rb)[0]
    check('I9 ★★ 正控制：同人设、只换命中词 ⇒ 硬词出补丁（证明 I8 不是恒真）',
          '作品名' in (p_niko_hard.get('os_niko') or ''),
          '%r' % (p_niko_hard.get('os_niko') or ''))

    # ---- J 组：`NOT_CN` 必须能真的进补丁 ----
    #   ★★★ 真 bug：`PATCH_RULES['NOT_CN']` 写好了，但 `build_patch` 的优先级元组里
    #   **没有 `NOT_CN`** ⇒ 这条纠正永远发不出来。`ut_sans` 47/48 整句英文，
    #   最终补丁只有「两三句」+「别重复」—— 最严重的问题零纠正。
    j1 = C.build_patch([('NOT_CN', 'x')], [], [])
    check('J  ★★★ 只有 NOT_CN ⇒ 补丁里必须有中文要求（原来恒为空）',
          u'简体中文' in j1, '%r' % j1)
    j2 = C.build_patch([('TOO_LONG', 'x'), ('NOT_CN', 'y')], [], [])
    check('J2 语言排在长度之前（两句都在，且顺序对）',
          j2.find(u'简体中文') >= 0 and j2.find(u'简体中文') < j2.find(u'两三句'), '%r' % j2)
    #   ★ 第一版 J3 用 `['MARKDOWN','AI_SELF','SLAVE','NOT_CN']` 当夹具 ⇒ 报红。
    #     错的是夹具：`AI_SELF` 是 **113轮l 故意不设**纠正句的（`PATCH_RULES` 里
    #     没有它，实测写了"我会更差"）⇒ 它不占 cap 的位置。
    #   ★ J3 我连错两次夹具，记下来：① 用 `AI_SELF` 当占位（它故意没有规则）；
    #     ② 以为 `NOT_CN` 排在 `ACTION_PAREN` 之后（实际我插在它**之前**）。
    #     正确的 cap 测试必须用 4 条**都有规则、且不含 NOT_CN** 的码。
    j3 = C.build_patch([('MARKDOWN', 'a'), ('SLAVE', 'b'),
                        ('ACTION_PAREN', 'c'), ('META', 'd')], [], [])
    check('J3 负控制：cap=3 仍生效（4 条都有句可发 ⇒ 第 4 条 META 被挤出）',
          u'作品名' not in j3 and j3.count(u'。') == 3, '%r' % j3)
    j5 = C.build_patch([('AI_SELF', 'b')], [], [])
    check('J5 锁住设计决定：`AI_SELF` **故意没有**纠正句（113轮l 实测写了更差）',
          j5 == u'' and 'AI_SELF' not in C.PATCH_RULES, '%r' % j5)

    # ---- K 组：`ACTION_PAREN` 的补丁措辞必须覆盖闸门实际抓的东西 ----
    #   ★ 实测 419 次括号里，纯动作/表情只占 **38.9%**，其余是插话与对白括注。
    #   `ut_papyrus` 45 条基本全是插话 ⇒ 旧措辞「不要用括号写动作或表情」对他不成立。
    kap = C.PATCH_RULES['ACTION_PAREN']
    check('K  ★★ 补丁要覆盖「插话」（真数据里 61% 的括号不是动作）',
          u'插话' in kap, '%r' % kap)
    check('K2 负控制：加了插话**不许把动作/表情丢掉**',
          u'动作' in kap and u'表情' in kap, '%r' % kap)

    # ---- L 组：括号豁免的角色，旧补丁里的括号句必须能剔掉 ----
    #   ★ 真矛盾：`kris`/`tenna`/`ut_frisk` 卡片里的 patch 至今还写着
    #   「不要用括号写动作或表情」，而人设要求他们"用括号表示动作"。
    #   `merge_patches` 不会删旧句 ⇒ 不主动剔就永远矛盾。
    mixed = u'不要用括号加动作、表情或插话，只写你说出口的话。 别把刚才说过的话再说一遍，换个说法。'
    got = E.strip_paren_rule(mixed)
    check('L  ★★ 剔掉括号句、保住其它纠正（不是清空补丁）',
          u'括号' not in got and u'别把刚才' in got, '%r' % got)
    check('L2 负控制：没有括号句的补丁**原样返回**（不误删别的）',
          E.strip_paren_rule(u'一次最多两三句。别重复。') == u'一次最多两三句。别重复。')
    check('L3 空串 / None 安全', E.strip_paren_rule(u'') == u'' and E.strip_paren_rule(None) == u'')
    # L4 真数据：kris 现在的卡片里确实有括号句（否则 L 组就是空转）
    kp = E.collect_cards().get('kris', {}).get('patch') or u''
    check('L4 ★ 夹具前提成立：`kris` 现盘补丁里确实有括号句',
          u'括号' in kp and u'括号' not in E.strip_paren_rule(kp), '%r' % kp[:40])
    check('L5 ★ 人设自证：kris 属于括号豁免名单（所以剔他是对的）',
          C._persona_allows_paren((C.load_roster()[0] and
                                   {r['id']: r for r in C.load_roster()[0]}['kris']['persona']) or u''))
    j4 = C.build_patch([('MARKDOWN', 'a'), ('ACTION_PAREN', 'b'), ('META', 'c')], [], [])
    check('J4 回归：不含 NOT_CN 的清单，前三句仍是原来的顺序（没改坏别人）',
          j4.startswith(u'说话就是说话') and u'括号' in j4 and u'作品名' in j4, '%r' % j4)

    print('\n' + '=' * 60)
    print('合计：PASS=%d FAIL=%d' % (_ok, _n - _ok))
    print('=' * 60)
    return 0 if _ok == _n else 1


if __name__ == '__main__':
    sys.exit(main())
