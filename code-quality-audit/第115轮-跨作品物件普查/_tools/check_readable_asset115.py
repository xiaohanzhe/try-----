# -*- coding: utf-8 -*-
u"""第117轮：`ralsei_pet/assets/scenes/_readable_text.json` 的判据。

这个文件是**产品数据**，不是中间产物 —— 它一旦被手改或回滚，桌宠会读到错的正文，
而且**不会报错**（空串照样能显示）。所以要像守产品代码一样守它。

判据
----
A 结构：能解析 · `schema_version` · `markers_raw` 为真（标记没被偷偷替换）
B 分母：条目数够多（下界，只增不减）；uty 的 0 条是**事实**，显式记录成 EMPTY 不算通过
C 引用完整性：每个 scene_id 真在产品 `_zone.*.json` 里；每个 key 真在 `readables115.json` 里
D 正文有效性：每条至少有 cn/cn_tight/en 之一，且**非空白**
E ★ `cn_tight` 只差空白：去空白后与 `cn` 逐字相等（不是"改了几个字"）
F ★ 分母守恒：资产里的 (场景, 对象) 组合必须真在 `inst_full.tsv` 里有实例
G ★ 未解如实登记：`unresolved` 的条数与 `readable_bind` 的缺口对得上，且**没被塞进 by_scene**
H 破坏性负控制：把某条正文改成空白 / 把某个 key 改名 / 把 cn_tight 改一个字
   ⇒ 对应判据必须变红（证明 C/D/E 有牙）
I 本脚本自检：无恒真判据
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.join(ROUND, '..', '..')

AUDIT = os.path.join(ROOT, 'code-quality-audit', '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(AUDIT, 'raw')
ASSET = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_readable_text.json')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

_fail = []
_np = _nf = 0


def check(desc, cond, detail=''):
    global _np, _nf
    if cond:
        _np += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _nf += 1
        _fail.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def read(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


print('=' * 74)
print('A 结构')
print('=' * 74)

_ok_parse = True
try:
    doc = json.loads(read(ASSET))
except Exception as e:                                   # noqa: BLE001
    doc = {}
    _ok_parse = False
    print('  解析失败: %s: %s' % (type(e).__name__, e))

check('A1 资产能解析成 JSON 对象', _ok_parse and isinstance(doc, dict))
# ★★ 第119轮：schema 2 = 每条候选带 `guard`（base/pos/state）。
#   旧判据写死 `== 1` 是为了防止“不知道就换掉”；现在两代都是**已通过验证**的形状，
#   但 v2 的字段集合不同（有 guard、无旧的一些计数）⇒ 需要同时验一下字段，避免“版本号对、内容错”。
check('A2 `schema_version` ∈ {1, 2}（v1=无 guard；v2=带 guard）',
      doc.get('schema_version') in (1, 2),
      repr(doc.get('schema_version')))
check('A3 `markers_raw` 为真（% & / ^1 没在数据层被替换）',
      doc.get('markers_raw') is True, repr(doc.get('markers_raw')))
check('A4 有 `markers_note` 说明"未解码、原样保留"',
      bool(doc.get('markers_note')))

by_scene = doc.get('by_scene') or {}
games = doc.get('games') or {}
check('A5 `by_scene` 非空且 `games` 有 ut / outertale / uty 三键',
      bool(by_scene) and set(games) == {'ut', 'outertale', 'uty'}, repr(sorted(games)))
check('A6 v2 每条候选都带 `guard`（版本号对、内容也得对）',
      doc.get('schema_version') != 2
      or all(e.get('guard') in ('base', 'pos', 'state')
             for v in by_scene.values() for e in v),
      '条目=%d' % sum(len(v) for v in by_scene.values()))


print()
print('=' * 74)
print('B 分母（下界，只增不减）')
print('=' * 74)

n_ut = sum(len(v) for k, v in by_scene.items() if k.startswith('ut.'))
n_ot = sum(len(v) for k, v in by_scene.items() if k.startswith('outertale.'))
n_uty = sum(len(v) for k, v in by_scene.items() if k.startswith('uty.'))
check('B1 ut 条目 ≥ 300（v1 是 194；v2 把同房间的分支全收了）', n_ut >= 300, '实际 %d' % n_ut)
check('B2 outertale 条目 ≥ 250（v1 是 161）', n_ot >= 250, '实际 %d' % n_ot)
check('B3 uty 0 条 = 原作事实（该作没有可读物正文表），显式记 EMPTY 而不是当"通过"',
      n_uty == 0 and (games.get('uty') or {}).get('entries') == 0
      and (games.get('uty') or {}).get('unresolved', 0) == 0,
      '扫描 %d 条；entries=%r unresolved=%r'
      % (n_uty, (games.get('uty') or {}).get('entries'),
         (games.get('uty') or {}).get('unresolved')))
check('B4 `games.<g>.entries` 与 by_scene 实际条数一致',
      all((games.get(g) or {}).get('entries', 0) ==
          sum(len(v) for k, v in by_scene.items() if k.startswith(g + '.'))
          for g in ('ut', 'outertale', 'uty')),
      repr({g: (games.get(g) or {}).get('entries') for g in ('ut', 'outertale', 'uty')}))


print()
print('=' * 74)
print('C 引用完整性（场景 id / 文本键都要真存在）')
print('=' * 74)

_scene_ids = set()
for p in sorted(glob.glob(os.path.join(SCENES, '_zone.*.json'))):
    try:
        d = json.loads(read(p))
    except Exception:                                    # noqa: BLE001
        continue
    _scene_ids.update((d.get('scenes') or {}).keys())

_bad_scene = [s for s in by_scene if s not in _scene_ids]
check('C1 每个 scene_id 都真在产品 `_zone.*.json` 里', not _bad_scene,
      '%d 个不认识：%s' % (len(_bad_scene), _bad_scene[:4]))

_texts = json.loads(read(os.path.join(AUDIT, 'readables115.json')))
_bad_key = []
for sid, rows in by_scene.items():
    g = sid.split('.', 1)[0]
    keys = (_texts.get(g) or {}).get('keys') or {}
    for e in rows:
        if e.get('key') not in keys:
            _bad_key.append((sid, e.get('key')))
check('C2 每个文本键都真在 `readables115.json` 里', not _bad_key,
      '%d 个查无此键：%s' % (len(_bad_key), _bad_key[:4]))


print()
print('=' * 74)
print('D/E 正文有效性 与 `cn_tight` 只差空白')
print('=' * 74)

_empty = []
_bad_tight = []
for sid, rows in by_scene.items():
    for e in rows:
        texts = [e.get('cn'), e.get('cn_tight'), e.get('en')]
        if not any((t or '').strip() for t in texts):
            _empty.append((sid, e.get('key')))
        cn, tight = e.get('cn'), e.get('cn_tight')
        if cn is not None and tight is not None:
            f = lambda s: re.sub(r'\s+', '', s)
            if f(cn) != f(tight):
                _bad_tight.append((sid, e.get('key')))
check('D1 每条至少有一种语言的正文且非空白（不用空串顶）', not _empty,
      '%d 条空白：%s' % (len(_empty), _empty[:4]))
check('E1 ★ `cn_tight` 去空白后与 `cn` 逐字相等（只许少空格）', not _bad_tight,
      '%d 条不等：%s' % (len(_bad_tight), _bad_tight[:4]))


print()
print('=' * 74)
print('F/G 分母守恒 与 未解登记')
print('=' * 74)


def load_inst_pairs(game):
    p = os.path.join(RAW, game, 'inst_full.tsv')
    if not os.path.isfile(p):
        return None
    out = set()
    cur = None
    for ln in read(p).splitlines():
        c = ln.split('\t')
        if not c:
            continue
        if c[0] == 'R' and len(c) >= 2:
            try:
                cur = int(c[1])
            except ValueError:
                cur = None
        elif c[0] == 'I' and len(c) >= 2 and cur is not None and 'readable' in c[1]:
            out.add((cur, c[1]))
    return out


# 场景 id → original_room_id（用产品自己的数据反查，不另建表）
_sid2oid = {}
for p in sorted(glob.glob(os.path.join(SCENES, '_zone.*.json'))):
    try:
        d = json.loads(read(p))
    except Exception:                                    # noqa: BLE001
        continue
    for sid, s in (d.get('scenes') or {}).items():
        oid = s.get('original_room_id')
        if isinstance(oid, int):
            _sid2oid.setdefault(sid, oid)

_pairs_ut = load_inst_pairs('ut')
_pairs_ot = load_inst_pairs('outertale')
_phantom = []
for sid, rows in by_scene.items():
    g = sid.split('.', 1)[0]
    src = _pairs_ut if g == 'ut' else (_pairs_ot if g == 'outertale' else None)
    if src is None:
        continue
    oid = _sid2oid.get(sid)
    for e in rows:
        if (oid, e.get('obj')) not in src:
            _phantom.append((sid, e.get('obj')))
check('F1 ★ 资产里的每个 (场景, 对象) 组合都真在 `inst_full.tsv` 有实例'
      '（不是凭空造出来的挂载点）', not _phantom,
      '%d 条对不上：%s' % (len(_phantom), _phantom[:4]))

# ★★ 第119轮：`unresolved` 在 v2 里分两种——
#   `no_room_guard`（这段赋值根本没房间条件）与
#   `room_without_scene`（房间名在产品里没有对应场景）。
#   后者必须**逐条去 zone 里反查**：万一那房间其实有场景，
#   就是“本该收进来却被丢掉”的真错误（而且不报错）。
_zone_names = {}
for _g in ('ut', 'outertale'):
    _nm = set()
    for _p in glob.glob(os.path.join(SCENES, '_zone.%s.*.json' % _g)):
        for _sid, _s in (json.loads(read(_p)).get('scenes') or {}).items():
            _nm.add(_s.get('name_raw'))
    _zone_names[_g] = _nm

_ghost = []
_uns_total = 0
for _g in ('ut', 'outertale'):
    for _u in ((games.get(_g) or {}).get('unresolved_list') or []):
        _uns_total += 1
        if not _u.get('why'):
            _ghost.append((_g, _u.get('key'), '缺 why'))
        elif _u.get('why') == 'room_without_scene' and _u.get('room') in _zone_names[_g]:
            _ghost.append((_g, _u.get('room'), '房间其实有场景'))
check('G1 ★★ 未解条目都带 `why`，且 `room_without_scene` 那批'
      '房间**真的**在产品里没场景（逐条反查 zone，不是自证）',
      _uns_total > 0 and not _ghost,
      '未解=%d 对不上=%d %r' % (_uns_total, len(_ghost), _ghost[:2]))
check('G2 `unresolved` 数量与 `games.<g>.unresolved` 对得上',
      all(len((games.get(g) or {}).get('unresolved_list') or []) ==
          (games.get(g) or {}).get('unresolved', -1)
          for g in ('ut', 'outertale')),
      repr({g: ((games.get(g) or {}).get('unresolved'),
                len((games.get(g) or {}).get('unresolved_list') or []))
            for g in ('ut', 'outertale')}))
check('G3 未解数 ≥ 1 且被如实记下（ut 无房间条件 19；outertale 另有 167 个房间没场景）',
      (games.get('ut') or {}).get('unresolved', 0) >= 1
      and (games.get('outertale') or {}).get('unresolved', 0) >= 1,
      'ut=%r outertale=%r' % ((games.get('ut') or {}).get('unresolved'),
                              (games.get('outertale') or {}).get('unresolved')))


print()
print('=' * 74)
print('H 破坏性负控制（证明 C/D/E 不是恒真）')
print('=' * 74)

_one_sid = sorted(s for s in by_scene if by_scene[s])[0]
_one = by_scene[_one_sid][0]

# H1：正文变空白 ⇒ D1 的判据要能抓到
_fake = {'cn': '   ', 'cn_tight': None, 'en': None}
check('H1 把一条正文改成纯空白 ⇒ "至少一种语言非空白"判据会判红',
      not any((t or '').strip() for t in
              [_fake.get('cn'), _fake.get('cn_tight'), _fake.get('en')]))

# H2：key 改名 ⇒ C2 的判据要能抓到
_keys_ut = ((_texts.get('ut') or {}).get('keys') or {})
check('H2 把 key 改一个字母 ⇒ "键必须真存在"判据会判红',
      (_one.get('key') + 'X') not in _keys_ut,
      '原 key=%r' % (_one.get('key'),))

# H3：cn_tight 改一个字 ⇒ E1 的判据要能抓到（只在有 cn 的条目上做）
_cand = None
for sid, rows in by_scene.items():
    for e in rows:
        if e.get('cn') and e.get('cn_tight') and len(e['cn_tight']) > 4:
            _cand = e
            break
    if _cand:
        break
if _cand is None:
    check('H3 夹具：找不到"cn 与 cn_tight 都在"的条目（E1 无从检验，显式记 NOP）',
          False, 'NOP')
else:
    f = lambda s: re.sub(r'\s+', '', s)
    _mut = _cand['cn_tight'][:-1] + ('X' if _cand['cn_tight'][-1] != 'X' else 'Y')
    check('H3 把 cn_tight 末字换掉 ⇒ E1 判据会判红（不是恒真）',
          f(_mut) != f(_cand['cn']),
          'key=%r' % (_cand.get('key'),))


print()
print('=' * 74)
print('I 本脚本自检')
print('=' * 74)

_self = read(os.path.abspath(__file__))


def _taut_count(src):
    """数 `check(<desc>, True)` / `check(<desc>, 1)`。★ 用 AST，不扫文本 ——
    第一版用正则，结果被**自己的正控制字符串** `'check("x", True)'` 打红（误报）。"""
    import ast
    n = 0
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'check' and len(node.args) >= 2:
            a = node.args[1]
            if isinstance(a, ast.Constant) and a.value in (True, 1):
                n += 1
    return n


_t = _taut_count(_self)
check('I1 本套件里没有 `check(..., True)` 这类恒真判据（AST 判，不扫文本）',
      _t == 0, '命中 %d 处' % _t)
check('I2 上一条的正控制：同一个扫描器对 `check("x", True)` 会数出 1 处',
      _taut_count('check("x", True)\n') == 1,
      '数出 %d 处' % _taut_count('check("x", True)\n'))
check('I3 负控制：对 `check("x", ok)`（非常量）不数',
      _taut_count('check("x", ok)\n') == 0)

print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_np, _nf))
if _fail:
    print('失败项：')
    for d in _fail:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if _nf == 0 else 1)
