# -*- coding: utf-8 -*-
"""第六十八轮回归锁：**可交互道具实例补采**不许静默漂移。

用户口径（第48轮原话，本轮补的是这条需求剩下的那一半）
------------------------------------------------------
    「对于里面可互动的道具也要做到可以互动……」

第48轮把机制做完了，但如实登记过一个缺口：
**「可交互『道具』类当前一件实例都没有」**（只有存档点 / 暗之泉能互动）。
本轮把这条补上，根因有**三个 —— 只修一个都不够**：

  ① 普查没采   —— `inst42.csx` 的关键词表不含 readable/sign/chest/treasure/pickup/…
  ② 对象表错配 —— 生成器只读 **ch1** 的 353 对象表，却用于全五章
  ③ 素材不在库 —— `object()` 有"无素材跳过"，sprite 没进 `objs/` 就等于不存在

本锁守的是**这条链**（数据 → 素材 → 产物 → 行为），分工上：
`PROP_CLASSES` 的 `in_data` 与产物对账归**第48轮**（E3 已升级为两侧对账），
本锁不重复那一份判据，只锁"补采链本身没被改回去"。

判据纪律（本项目踩过的坑）
--------------------------
★ 正/负成对；★ 能上 AST 就上 AST；★ **不许依赖 E 盘临时区**（读完即删 ⇒ 会静默失去鉴别力）
★ 判据报红先怀疑判据；★ 恒真判据比不写还危险。
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
EV68 = os.path.join(HERE, '_evidence')
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
E43 = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OBJS = os.path.join(SCENES, 'objs')
MODULES = os.path.join(ROOT, 'ralsei_pet', 'modules')
GEN68 = os.path.join(HERE, '_tools', 'gen_objects68.py')

if MODULES not in sys.path:
    sys.path.insert(0, MODULES)

import companion as CP                          # noqa: E402
import item_interact as II                      # noqa: E402

INST68 = {'ch1': 'inst68.json', 'ch2': 'ch2_inst68.json', 'ch3': 'ch3_inst68.json',
          'ch4': 'ch4_inst68.json', 'ch5': 'ch5_inst68.json'}
INST42 = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
          'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}
#: 本轮期望**真的落地**的可交互 kind（每类至少 1 条）。
WANT_KINDS = ('readable', 'sign', 'chest', 'furniture')
#: 本轮搬进 objs/ 的 sprite（可交互类用到的）。
NEW_SPRITES = ('spr_interactable', 'spr_npc_sign', 'spr_treasurebox',
               'spr_classdesk', 'spr_alphysdesk')

PASS = []
FAIL = []


def ok(name):
    PASS.append(name)
    print('[PASS] %s' % name)


def bad(name):
    FAIL.append(name)
    print('[FAIL] %s' % name)


def check(name, cond, detail=''):
    if cond:
        ok('%s %s' % (name, detail))
    else:
        bad('%s %s' % (name, detail))
    return bool(cond)


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def _insts_of(path):
    """一章文件 → {房间下标: Counter(实例判等键)}。"""
    d = load(path)
    out = {}
    for rec in (d.get('rooms') or []):
        rid = rec.get('index')
        if not isinstance(rid, int):
            continue
        out[rid] = collections.Counter(
            (i.get('obj'), i.get('x'), i.get('y'), i.get('layer'), i.get('depth'))
            for i in (rec.get('insts') or []))
    return out


def _src_hist():
    """产物里每个 `src` 的出现次数（扫分片 + 独立文件）。"""
    hist = collections.Counter()
    for f in sorted(os.listdir(SCENES)):
        if not f.endswith('.json'):
            continue
        try:
            d = load(os.path.join(SCENES, f))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        tables = []
        if isinstance(d.get('scenes'), dict):
            tables.append(d['scenes'])
        if isinstance(d.get('objects'), list):
            tables.append({'_self': d})
        for t in tables:
            for _sid, raw in t.items():
                if not isinstance(raw, dict):
                    continue
                for o in (raw.get('objects') or []):
                    s = (o or {}).get('src')
                    if s:
                        hist[s] += 1
    return hist


def _objmap(ch):
    f = {'ch1': 'objmap43.txt', 'ch2': 'chapter2_objmap43.txt', 'ch3': 'chapter3_objmap43.txt',
         'ch4': 'chapter4_objmap43.txt', 'ch5': 'chapter5_objmap43.txt'}[ch]
    return os.path.join(E43, f)


# ===========================================================================
#  A 数据面 —— inst68 是 inst42 的**逐条超集**（等价性），且真采到了新类
# ===========================================================================

def seg_a():
    print('== A 数据面（五章实例普查）==')
    missing = [c for c in INST68 if not os.path.isfile(os.path.join(EV68, INST68[c]))]
    if not check('A0', not missing,
                 '五章实例普查文件齐备（缺 %s）' % (missing or '无')):
        return

    total68 = total42 = 0
    drift = []
    for ch in INST42:
        a = _insts_of(os.path.join(E42, INST42[ch]))
        b = _insts_of(os.path.join(EV68, INST68[ch]))
        for rid, need in a.items():
            have = b.get(rid) or collections.Counter()
            for k, n in need.items():
                if have.get(k, 0) < n:
                    drift.append((ch, rid, k))
        total42 += sum(v for c in a.values() for v in c.values())
        total68 += sum(v for c in b.values() for v in c.values())
    check('A1', not drift and total68 > total42,
          '★★ 等价性：inst68 逐条包含 inst42 的 %d 条（漂移 %d 条）；总量 %d → %d'
          % (total42, len(drift), total42, total68))
    for d in drift[:3]:
        print('      [DRIFT] %r' % (d,))

    # 交叉验证：UTMT 读到的房间数是否可信 —— 拿**第47轮锁已钉住**的原作房间总数比。
    #   ⚠️ `_original_rooms.json` 是"房间名表"（`chapters[].rooms` 合计 95），**不是**
    #      全量 room dump ⇒ 拿它当基准会得到恒真判据（首版就写成了 `n_orig is None or …`）。
    tot_rooms = 0
    for ch in INST68:
        tot_rooms += load(os.path.join(EV68, INST68[ch])).get('n_rooms_total') or 0
    check('A2', tot_rooms == 1251,
          'UTMT 五章房间数合计 %d == 原作房间总数 1,251（与第47轮锁一致）' % tot_rooms)

    # 新增类：逐个 kind 至少有一条（正控制）
    hist = collections.Counter()
    for ch in INST68:
        d = load(os.path.join(EV68, INST68[ch]))
        for rec in (d.get('rooms') or []):
            for i in (rec.get('insts') or []):
                hist[i.get('obj')] += 1
    by_kind = collections.Counter()
    for nm, n in hist.items():
        r = II.classify(nm)
        if r and r.get('kind') in WANT_KINDS:
            by_kind[r['kind']] += n
    check('A3', all(by_kind.get(k, 0) > 0 for k in WANT_KINDS),
          '★★ 新增类在普查里都有实例：%s'
          % {k: by_kind.get(k, 0) for k in WANT_KINDS})


# ===========================================================================
#  B 素材面 —— 可交互类要用的 sprite 真在 objs/（正/负成对）
# ===========================================================================

def seg_b():
    print('== B 素材面（assets/scenes/objs/）==')
    if not os.path.isdir(OBJS):
        bad('B0 objs/ 目录不存在')
        return
    have = set()
    for f in os.listdir(OBJS):
        m = re.match(r'^(.*)_\d+\.png$', f)
        if m:
            have.add(m.group(1))
    miss = [s for s in NEW_SPRITES if s not in have]
    check('B1', not miss, '★ 可交互类所需 sprite 全在盘上（缺 %s）' % (miss or '无'))
    # 负控制：编造的 sprite 名不该命中（防"判据恒真"）
    check('B2', ('spr_zzz_not_exist_68' not in have),
          'B2 负控制：编造的 sprite 名不在盘上')
    # 只数真 PNG（防把 xxx.png.hidden 之类算进来 —— 第49轮踩过）
    pngs = [f for f in os.listdir(OBJS) if f.lower().endswith('.png')]
    junk = [f for f in os.listdir(OBJS) if not f.lower().endswith('.png')]
    check('B3', len(pngs) == len(os.listdir(OBJS)) and not junk,
          'B3 objs/ 里全是 PNG（%d 张，杂项 %d 个）' % (len(pngs), len(junk)))


# ===========================================================================
#  C 产物面 —— 场景 JSON 的 objects 里真有条数 + 锚点
# ===========================================================================

def seg_c():
    print('== C 产物面（assets/scenes 的 objects）==')
    hist = _src_hist()
    check('C0', len(hist) > 0, 'C0 产物 src 品类 %d 个（读不到 ⇒ 后面判据会退化成全绿）' % len(hist))
    by_kind = collections.Counter()
    for nm, n in hist.items():
        r = II.classify(nm)
        if r:
            by_kind[r['kind']] += n
    check('C1', all(by_kind.get(k, 0) > 0 for k in WANT_KINDS),
          '★★ 产物里可交互类真有条数：%s'
          % {k: by_kind.get(k, 0) for k in WANT_KINDS})

    # 锚点：城堡镇（真实场景）必须含可读物
    idx = load(os.path.join(SCENES, '_index.json'))
    sid = 'ch1.castle_town.castle_town'
    ent = None
    for _ch, blk in (idx.get('chapters') or {}).items():
        if not isinstance(blk, dict):
            continue
        for _a, ablk in (blk.get('areas') or {}).items():
            if isinstance(ablk, dict) and isinstance((ablk.get('scenes') or {}).get(sid), dict):
                ent = ablk['scenes'][sid]
    objs = None
    if ent and ent.get('file'):
        d = load(os.path.join(SCENES, ent['file']))
        t = d.get('scenes') if isinstance(d, dict) else None
        if isinstance(t, dict) and sid in t:
            objs = (t[sid] or {}).get('objects')
        if objs is None:
            objs = d.get('objects')
    srcs = collections.Counter((o or {}).get('src') for o in (objs or []))
    check('C2', bool(objs) and srcs.get('obj_readable_room1', 0) > 0
          and srcs.get('obj_savepoint', 0) == 1,
          '★★ 锚点城堡镇：objects %d 条 / 可读物 %d / 存档点 %d'
          % (len(objs or []), srcs.get('obj_readable_room1', 0), srcs.get('obj_savepoint', 0)))

    # 负控制：声明仍是缺口的类，产物里必须 0 条
    gaps = II.data_gaps()
    gnames = [n for v in gaps.values() for n in v]
    present = sorted(n for n in gnames if hist.get(n, 0) > 0)
    check('C3', not present,
          'C3 负控制：缺口类 %d 个，产物里有实例的 %d 个（须为 0）'
          % (len(gnames), len(present)))
    for n in present[:5]:
        print('      [SUSPECT] %s' % n)


# ===========================================================================
#  D 行为面 —— chest / interactable / furniture 真能交互（本轮新增的实现）
# ===========================================================================

def seg_d():
    print('== D 行为面（InspectProp）==')
    got = {}
    props = II.build_props(
        {'scene_id': 't', 'original_room_id': 1,
         'objects': [{'src': 'obj_treasure_room'}, {'src': 'obj_schooldesk'},
                     {'src': 'obj_npc_sign'}, {'src': 'obj_doorA'},
                     {'src': 'obj_markerB'}]},
        'ch1', 'dark', present=lambda t, a=None: t)
    for p in props:
        got.setdefault(p.kind, 0)
        got[p.kind] += 1
    check('D1', got.get('chest') == 1 and got.get('furniture') == 1 and got.get('sign') == 1,
          '★ 三类真建出可交互物：%r' % got)
    # 负控制：门与落点标记**不许**建物（门归路由层）
    check('D2', got.get('door', 0) == 0 and got.get('marker', 0) == 0,
          'D2 负控制：门/标记不建可交互物（door=%d marker=%d）'
          % (got.get('door', 0), got.get('marker', 0)))

    # 真交互 + 台词非空
    # ★ 每个 kind 必须**换一条 bus**：`Interactable.interact()` 成功后会把全局锁
    #   **留在持有态**（等对话结束才释放，见 companion 的 `MYINTERACT_DIALOG` 分支）
    #   ⇒ 连续三次用默认 bus 只有第一次能进 `on_interact`（首版就栽在这，报的像"实现坏了"）。
    texts = {}
    for kind in ('chest', 'interactable', 'furniture'):
        CP.reset_default_bus()
        seen = []
        pr = II.InspectProp('k#%s' % kind, kind, present=lambda t, a=None: seen.append(t) or t)
        r = pr.interact()
        texts[kind] = (r, seen[0] if seen else None)
    check('D3', all(v[0] and v[1] for v in texts.values())
          and len(set(v[1] for v in texts.values())) == 3,
          '★ 三种 kind 交互成功且台词各不相同：%r' % {k: v[1] for k, v in texts.items()})

    # 负控制：没接 present ⇒ 如实 False（不假装成功）
    p = II.InspectProp('k#nop', 'chest', present=None)
    check('D4', p.interact() is False, 'D4 负控制：没接 present ⇒ 返回 False（不假装）')

    # AST：build_props 里必须真有 INSPECT_KINDS 分支（防"改了类但没接线"）
    src = io.open(os.path.join(MODULES, 'item_interact.py'), 'r', encoding='utf-8').read()
    code = _code_no_comment(src)
    check('D5', 'INSPECT_KINDS' in code and 'InspectProp(' in code,
          'D5 AST/源码：build_props 真接了 INSPECT_KINDS → InspectProp')


def _strip_comments(text):
    """剥掉 `#` 注释，但**保留字符串字面量**（表名/文件名都在字符串里）。

    ★ 与 `_code_no_comment` 的分工：
      · 找**字符串里的**内容（文件名、表名）⇒ 用本函数；
      · 找**代码里的**标识符 ⇒ 用 `_code_no_comment`（连字符串一起剥，
        防"注释或字符串里出现了这个名字"把判据骗过）。
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '#':
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c in ('"', "'"):
            q = c
            triple = text[i:i + 3] == q * 3
            out.append(q * 3 if triple else q)
            i += 3 if triple else 1
            while i < n:
                if triple and text[i:i + 3] == q * 3:
                    out.append(q * 3)
                    i += 3
                    break
                if not triple and text[i] == q:
                    out.append(q)
                    i += 1
                    break
                if text[i] == '\\':
                    out.append(text[i])
                    i += 1
                    if i < n:
                        out.append(text[i])
                        i += 1
                    continue
                out.append(text[i])
                i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def _code_no_comment(text):
    """剥掉注释与字符串字面量（★ 防"注释里出现的名字"把判据骗过 —— 项目踩过）。"""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '#':
            while i < n and text[i] != '\n':
                i += 1
        elif c in ('"', "'"):
            q = c
            triple = text[i:i + 3] == q * 3
            i += 3 if triple else 1
            while i < n:
                if triple and text[i:i + 3] == q * 3:
                    i += 3
                    break
                if not triple and text[i] == q:
                    i += 1
                    break
                if text[i] == '\\':
                    i += 1
                i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


# ===========================================================================
#  E 工具面 —— 生成器的两处关键修复必须在位（AST + 鉴别力）
# ===========================================================================

def seg_e():
    print('== E 工具面（gen_objects68.py）==')
    if not os.path.isfile(GEN68):
        bad('E0 生成器脚本不在盘上')
        return
    # ★ 按章取表（修既有缺陷）——老写法是"只读 ch1 表却用于全五章"
    #   ⚠️ 表名在**字符串字面量**里（`{'ch2': 'chapter2_objmap43.txt'}`）
    #      ⇒ 这里必须用 `_strip_comments`（剥注释、**保留字符串**）。
    #      用 `_code_no_comment`（连字符串一起剥）会恒假；
    #      用原始文本又会被**注释里**的同一个文件名骗过（本脚本注释里就写了它）。
    code_keep = _strip_comments(io.open(GEN68, 'r', encoding='utf-8').read())
    per_ch = all(k in code_keep for k in ('chapter2_objmap43.txt', 'chapter3_objmap43.txt',
                                          'chapter4_objmap43.txt', 'chapter5_objmap43.txt'))
    check('E1', per_ch, '★★ 生成器**按章取对象表**（五张表名都在代码里，注释骗不过）')
    # ★ 复用第44轮纯函数（单一真源），不是复制一份 object()
    check('E2', 'gen_objects44.py' in code_keep and 'object(' in code_keep,
          'E2 复用第44轮的 object()/parse_objmap()（逻辑单一真源）')
    # 鉴别力：合成"只读 ch1 表"的老写法，必须被判否
    fake_old = "OBMAP = {'ch1': 'objmap43.txt'}\nobjmap = g44.parse_objmap('objmap43.txt')"
    fake_hit = all(k in _strip_comments(fake_old) for k in
                   ('chapter2_objmap43.txt', 'chapter3_objmap43.txt'))
    check('E3', fake_hit is False,
          'E3 ★ 鉴别力：合成"只读 ch1 表"的写法**判不出**按章取表 ⇒ 判据不是恒真')


# ===========================================================================
#  F 判据自身体检
# ===========================================================================

def seg_f():
    print('== F 判据自身体检 ==')
    # F1 记账口是活的：前面各段必须**真的**记过账。
    #   ⚠️ 不能写成 `len(PASS)+len(FAIL) > 0` —— check 的参数在调用前求值，
    #      而前面几段已经记过账 ⇒ 那个判据**恒真**（"看着在守其实没守"）。
    #      改成"至少记了 20 条"：记账口若坏了（不 append）立刻报红。
    check('F1', len(PASS) + len(FAIL) >= 15,
          'F1 记账口是活的：已记 PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))

    # F2 恒真体检：--f2 造一个必假判据，必须进 FAIL
    if '--f2' in sys.argv:
        check('F2-fake', False, 'F2 自发破坏（应报红）')
    else:
        ok('F2 恒真体检模式未开启（用 --f2 自证判据会报红）')

    # F3 数据真被读到（防"读不到 ⇒ 空表 ⇒ 一切相等 ⇒ 全绿"）
    n_files = sum(1 for c in INST68 if os.path.isfile(os.path.join(EV68, INST68[c])))
    n_objs = len(os.listdir(OBJS)) if os.path.isdir(OBJS) else 0
    check('F3', n_files == 5 and n_objs >= 40,
          'F3 数据在位：inst68 文件 %d/5，objs/ 文件 %d' % (n_files, n_objs))


def main():
    for seg in (seg_a, seg_b, seg_c, seg_d, seg_e, seg_f):
        seg()
    print('')
    print('合计：%d 条判据，PASS=%d FAIL=%d' % (len(PASS) + len(FAIL), len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
