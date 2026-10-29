# -*- coding: utf-8 -*-
"""第113轮 · 训练纠正（patch）回产品的端到端校验 —— 2026-10-29。

## 为什么要单独验这一层
`eval113.py` 把 59 条纠正写进 `assets/npc/_training/_index.json`，
但"写进去了"不等于"产品读得到"。第113轮s 已经栽过一次同类问题：
评测读的是 4 轮冒烟记录，48 轮训练的 419 次 `ACTION_PAREN` **一条都没变成
运行时纠正**，而报告、表格、数字全都正常。

所以这里不走"文件里有 59 个键"这种弱判据，而是**从产品入口调**：
    `npc_persona.training_patch(npc_id)`   ← `main.py:3494` 真正调的就是它
逐字比对返回值与 JSON 里的原句。

## 判据（正负成对，怕恒真）
- T1  `_index.json` 的 `patches` 是 dict 且非空
- T2  77 个训练卡 id 逐个调 ⇒ 非空集合 **完全等于** patches 的键集（不躲不漏）
- T3  逐字相等（`training_patch(id) == patches[id].strip()`）
- T4  [负] 不存在的 id ⇒ `''`
- T5  [负] `assets_dir` 指到空目录 ⇒ `''`（证明读盘失败走兜底）
- T6  [正] 空目录调过之后，再用真实目录调**同一个人** ⇒ 必须拿到真值
         （验证缓存键含 `assets_dir`，没有被前一次的空结果污染）
- T7  长度上限：进 system 的一句不能太长
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.join(ROUND, '..', '..')
ASSETS = os.path.abspath(os.path.join(REPO, 'ralsei_pet', 'assets'))
sys.path.insert(0, os.path.abspath(os.path.join(REPO, 'ralsei_pet')))

import modules.npc_persona as P        # noqa: E402

IDX = os.path.join(ASSETS, 'npc', '_training', '_index.json')
CARDS = os.path.join(ASSETS, 'npc', '_training', 'cards')
MAX_PATCH_CHARS = 200

_ok, _bad = [], []


def check(name, cond, detail=''):
    (_ok if cond else _bad).append(name)
    print('[%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('  ' + detail) if detail else ''))
    return bool(cond)


def main():
    if not os.path.isfile(IDX):
        check('T1 _index.json 存在', False, IDX)
        return 1
    with io.open(IDX, encoding='utf-8', newline='') as f:
        idx = json.loads(f.read())
    patches = idx.get('patches') if isinstance(idx, dict) else None
    if not check('T1 patches 是 dict 且非空',
                 isinstance(patches, dict) and bool(patches),
                 '%s 条' % (len(patches) if isinstance(patches, dict) else 'NA')):
        return 1

    # 训练卡 id（96 张全档；有人设的 77 张才可能有 patch）
    card_files = [f for f in os.listdir(CARDS)
                  if f.endswith('.json') and not f.startswith('_')]
    ids = sorted(f[:-5] for f in card_files)
    check('T0 训练卡 = 96 张（全档，含纯 NPC）', len(ids) == 96, '实际 %d 张' % len(ids))

    got = {}
    for nid in ids:
        v = P.training_patch(nid, assets_dir=ASSETS)
        if v:
            got[nid] = v

    check('T2 从产品入口取到的非空集合 == patches 的键集',
          set(got) == set(patches),
          '取到 %d / JSON %d；差集 取到多=%s JSON多=%s' % (
              len(got), len(patches),
              sorted(set(got) - set(patches))[:4],
              sorted(set(patches) - set(got))[:4]))

    # ★★★ 恒真闸：`got` 为空时「逐字相等」的空集判断会**恒真通过** ——
    #   第一次跑就是这么绿过的（T0 路径写错 ⇒ got={} ⇒ T3 报 PASS）。
    #   「判据也是被测物」：先证明分母不为零，再谈相等。
    if not check('T3a 分母非空（否则 T3 恒真）', len(got) > 0, 'got=%d' % len(got)):
        print('[FAIL] T3b 跳过：分母为 0')
        _bad.append('T3b')
    else:
        mismatch = [(k, got[k], patches[k].strip())
                    for k in got if got[k] != patches[k].strip()]
        check('T3b 每条逐字相等（不是"大概有"）', not mismatch,
              '比对 %d 条，不一致 %d%s' % (
                  len(got), len(mismatch),
                  ('：%s' % (mismatch[:2],)) if mismatch else ''))

    # ---- 负控制 ----
    check('T4 [负] 不存在的 id ⇒ 空串',
          P.training_patch('obj_THIS_IS_NOT_REAL', assets_dir=ASSETS) == '')

    empty_dir = os.path.abspath(os.path.join(os.environ.get('TEMP', '.'), '_wb_empty_assets'))
    if not os.path.isdir(empty_dir):
        os.makedirs(empty_dir)
    probe = sorted(patches)[0] if patches else 'ralsei'
    check('T5 [负] assets_dir 指到空目录 ⇒ 空串',
          P.training_patch(probe, assets_dir=empty_dir) == '',
          'probe=%s' % probe)
    # ---- 正控制：证明 T5 的"空"不是被缓存带过来的 ----
    check('T6 [正] 空目录之后用真实目录仍能取到（缓存键含 assets_dir）',
          P.training_patch(probe, assets_dir=ASSETS) == patches[probe].strip(),
          'probe=%s' % probe)

    over = [(k, len(v)) for k, v in patches.items() if len(v) > MAX_PATCH_CHARS]
    longest = max(((len(v), k) for k, v in patches.items()), default=(0, ''))
    check('T7 没有超长的纠正句（≤ %d 字）' % MAX_PATCH_CHARS, not over,
          '最长 %d 字（%s）' % longest)

    # ---- T8 SFT 语料条数必须跟"主记录"逐人对齐 ----
    # ★ 2026-10-29 这里锁的是一个真发生过的事故：`eval113.write_corpus` 原来拿
    #   **绝对合规轮数** 比 `ok(patch) > ok(base)`，而补训 4 轮、基线 48 轮 ⇒
    #   唯一"补训比基线合规更多"的 asgore（48 轮全违规、补训 4/4 合规）
    #   把 48 轮语料换成了 4 轮，**语料凭空少 44 条**。
    #   "补训越成功、语料越少" —— 反向激励，必须锁死。
    import eval113 as EV
    data = EV.load_all()
    corpus_dir = os.path.join(ASSETS, 'npc', '_training', 'corpus')
    bad_len = []
    total = 0
    for nid, recs in sorted(data.items()):
        base = recs.get('baseline') or {}
        want = sum(1 for t in (base.get('turns') or []) if t.get('final'))
        p = os.path.join(corpus_dir, nid + '.jsonl')
        got_n = 0
        if os.path.isfile(p):
            with io.open(p, encoding='utf-8', newline='') as f:
                got_n = sum(1 for line in f if line.strip())
        total += got_n
        if got_n != want:
            bad_len.append((nid, want, got_n))
    check('T8a 每个角色的语料条数 == 主记录里非空回答数', not bad_len,
          '不一致 %d 人%s' % (len(bad_len), ('：%s' % (bad_len[:3],)) if bad_len else ''))
    check('T8b 语料总数 > 3000（防止被短记录顶掉后的缩水）', total > 3000,
          '实际 %d 条' % total)

    # ---- T9 合并必须幂等（同一份输入重跑，产品数据不许变） ----
    # ★ 2026-10-29 实证事故：`merge_text` 原来按 `keep + extra`（旧独有在前、新句在后）拼，
    #   而 `cap_patch` 只从尾部裁自动句 ⇒ "保留哪一句模板"取决于**旧值里恰好有哪一句**
    #   ⇒ `ralsei` 在 **158 ⇄ 160** 之间形成 2-循环。连跑三次 `eval113`，
    #   写进产品的 `_index.json` 出现两个不同 sha1（`432ff0a2…` / `a2c5618f…`）。
    #   **同一份输入，每次产出不同的产品数据** —— 这是最难查的一类：没有任何报错。
    hand = u'只认得原作里真有的名字：Kris（克里斯）、Susie（苏西）、Lancer、Ralsei 自己、'
    hand += u'Toriel、Asgore、Asriel、Noelle、Berdly。 不要自己造人名（例如「凯斯恩」这种把'
    hand += u'两个名字拼起来的说法），拿不准名字的时候就称「你」「他」「她」，不要编。'
    tpl_a = u'一次最多两三句，短一点，像随口说出来的。'
    tpl_b = u'别把刚才说过的话再说一遍，换个说法。'
    new_ = tpl_a + u' ' + tpl_b
    seeds = [hand + u' ' + tpl_a, hand + u' ' + tpl_b, new_, hand]
    bad_idem = []
    for s in seeds:
        once = EV.merge_text(s, new_)
        twice = EV.merge_text(once, new_)
        if once != twice:
            bad_idem.append((len(s), len(once), len(twice)))
    check('T9a 合并幂等：merge(merge(x)) == merge(x)（4 个起点）', not bad_idem,
          '不收敛 %d 个%s' % (len(bad_idem), ('：%s' % (bad_idem,)) if bad_idem else ''))

    def _bad_merge(old, new):
        """**旧写法**的复刻（keep + extra，旧独有在前）——只用来做负控制。"""
        old_s, new_s = EV._split_sents(old), EV._split_sents(new)
        have = {x.strip(u'。 ') for x in new_s}
        keep = [x for x in old_s if x.strip(u'。 ') not in have]
        extra = [x for x in new_s if x.strip(u'。 ') not in {y.strip(u'。 ') for y in old_s}]
        return EV.cap_patch(u' '.join(keep + extra).strip())

    cyc = 0
    for s in seeds:
        o1 = _bad_merge(s, new_)
        o2 = _bad_merge(o1, new_)
        if o1 != o2:
            cyc += 1
    check('T9b [负控制] 旧顺序（keep+extra）确实不收敛（否则 T9a 恒真）', cyc > 0,
          '旧写法不收敛的起点数 = %d / %d' % (cyc, len(seeds)))

    print()
    print('===== %d PASS / %d FAIL =====' % (len(_ok), len(_bad)))
    return 0 if not _bad else 1


if __name__ == '__main__':
    sys.exit(main())
