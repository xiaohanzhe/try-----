# -*- coding: utf-8 -*-
"""第196轮回归锁 · **NPC 表情动画**（每个人用自己的帧，在自己的窗口里演）。

用户口径（本轮起点，直接推翻我上一轮的判断）
--------------------------------------------
    「每个角色在原作可是都有自己的动画的，为啥要用 ralsei 的啊」

上一轮（195）我把这条能力记成"NPC 没素材、只能顶 Ralsei 的身体"，是错的。
真实现状（四轮探针 + 逐帧放大核对的结果）：
  · 原作解包目录 34,520 张 PNG，逐角色分章节；Susie 一人 3,314 张；
  · 但**"有动画"≠"能当表情动画用"**：绝大多数是 cutscene 整图（一张图画两个人）
    或另一种画布（塞进小窗必跳）；
  · **能用的**是"与走路帧同尺寸族"的那一套 —— 而原作在 overworld 里表现情绪
    本来就是**换一套行走图**（`walk_down_dw_unhappy` / `laugh_dw`）；
  · Ralsei 自己的 `animations.json` 里也写着同一套（`walk_down_unhappy`）。

它守什么
--------
A 素材清单与磁盘对账 —— 清单里每一帧真的在盘上、尺寸与声明一致、没有孤儿文件
B 情绪口径         —— `laugh`/`cry`/`smile` 的归类，以及"`smile` 故意不映射"
C 行为（真窗口）   —— 开演后**屏幕上那一格真的换了图**、四帧四个画面、到点回站姿
D 接线（AST）      —— `char_id` 不再被挡在门外、NPC 走自己的层、Ralsei 老路径没被拆
E 素材质量契约     —— 高度族 / bbox 宽度 / 单人帧 / 姿势词，四道闸在**产物**上仍然成立
F 自检

★ 为什么 C 要比像素而不是比返回值：`play_once` 返回 True 只证明状态位写了；
  真正的契约是屏幕上那一格换了图（第191轮"`grab()` 能看见、屏幕看不见"的教训）。
★ 为什么 E 要重算一遍：清单是**构建期产物**，人可以手改；改错了不会报错、只会画错人。
"""
from __future__ import print_function

import ast
import io
import json
import os
import re
import struct
import sys

import os as _os
_os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.join(HERE, '..', '..', '..')
ROOT = os.path.abspath(ROOT)
PET = os.path.join(ROOT, 'ralsei_pet')
DR = os.path.join(PET, 'assets', 'sprites', 'dr')
sys.path.insert(0, PET)
sys.path.insert(0, os.path.join(PET, 'src'))

from PyQt5.QtWidgets import QApplication          # noqa: E402
from modules import npc_body_render as R          # noqa: E402

_n = {'p': 0, 'f': 0}


def check(name, ok, extra=u''):
    if ok:
        _n['p'] += 1
        print('[PASS] %s' % name)
    else:
        _n['f'] += 1
        print('[FAIL] %s' % name)
    if extra:
        print('       %s' % extra)


def rd(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()


def jload(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def png_hw(path):
    with open(path, 'rb') as f:
        head = f.read(16)
        w, h = struct.unpack('>II', f.read(8))
        assert head[:8] == b'\x89PNG\r\n\x1a\n', path
    return int(w), int(h)


def bbox(path):
    """实心区（alpha>32）的宽高。与构建期同一把尺子。"""
    from PIL import Image
    im = Image.open(path)
    im.load()
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    xs, ys, op = [], [], 0
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 32:
                xs.append(x)
                ys.append(y)
                op += 1
    if not xs:
        return None
    return (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, op)


def bits(win):
    pm = None if win is None else win.pixmap()
    if pm is None:
        return b''
    im = pm.toImage()
    return bytes(im.bits().asstring(im.byteCount()))


frames_man = jload(os.path.join(DR, '_npc_frames.json')).get('characters') or {}
anims = R.load_anims(PET)
anims_man = anims.get('characters') or {}
main_src = rd(os.path.join(PET, 'src', 'main.py'))
dui_src = rd(os.path.join(PET, 'modules', 'dialogue_ui.py'))
main_tree = ast.parse(main_src)
dui_tree = ast.parse(dui_src)

app = QApplication.instance() or QApplication([])
book = R.NpcFrameBook(root=PET)
layer = R.NpcBodyLayer(book=book)

# ================================================================ A 清单对账
print('\n=== A 素材清单与磁盘对账 ===')
check(u'A1 表情动画清单存在且有 characters',
      os.path.isfile(os.path.join(DR, '_npc_anims.json')) and bool(anims_man),
      u'%d 人' % len(anims_man))

_files = []
for _cid, _e in anims_man.items():
    for _cls, _ds in _e.items():
        for _dd, _rows in _ds.items():
            for _r in _rows:
                _files.append((_cid, _cls, _dd, _r))
_missing = [(c, r['f']) for c, k, d, r in _files
            if not os.path.isfile(os.path.join(DR, c, r['f'].replace('/', os.sep)))]
check(u'A2 清单里每一帧都在盘上', not _missing,
      u'共 %d 帧 · 缺 %d %s' % (len(_files), len(_missing), _missing[:3]))

# 尺寸：清单声明的 w/h 必须等于 PNG IHDR 真值
_size_bad = []
for c, k, d, r in _files:
    _w, _h = png_hw(os.path.join(DR, c, r['f'].replace('/', os.sep)))
    if (_w, _h) != (r['w'], r['h']):
        _size_bad.append((r['f'], r['w'], r['h'], _w, _h))
check(u'A3 声明的宽高 == PNG 头里的真尺寸', not _size_bad, u'%r' % _size_bad[:3])

# 反向：磁盘上 anim/ 里的 png 必须都能在清单里找到（防孤儿）
_orphan = []
for c in anims_man:
    d = os.path.join(DR, c, 'anim')
    if not os.path.isdir(d):
        continue
    _known = set(r['f'].split('/')[-1] for _c, _k, _d, r in _files if _c == c)
    for f in os.listdir(d):
        if f.lower().endswith('.png') and f not in _known:
            _orphan.append('%s/anim/%s' % (c, f))
check(u'A4 没有孤儿文件（磁盘 anim/ 下的 png 都在清单里）', not _orphan,
      u'%d 个 %s' % (len(_orphan), _orphan[:3]))

_emit = sum(1 for c in anims_man if anims_man[c])
check(u'A5 每个登记角色至少一类情绪', _emit == len(anims_man),
      u'%d / %d' % (_emit, len(anims_man)))

# ================================================================ B 情绪口径
print('\n=== B 情绪口径 ===')
check(u'B1 laugh 归 happy 类（`大笑` 实际产出的就是这个键）',
      R.EMOTION_CLASS.get('laugh') == 'happy', repr(R.EMOTION_CLASS.get('laugh')))
check(u'B2 cry 归 sad 类（NPC 侧无 cry 素材 ⇒ 如实退一档）',
      R.EMOTION_CLASS.get('cry') == 'sad', repr(R.EMOTION_CLASS.get('cry')))
check(u'B3 smile 故意不映射（微笑是换脸，不该放成一段大笑动作）',
      'smile' not in R.EMOTION_CLASS, repr(sorted(R.EMOTION_CLASS)))
check(u'B4 五类动作齐全 happy/sad/angry/surprised/hurt',
      set(R.EMOTION_CLASS.values()) == set(['happy', 'sad', 'angry',
                                            'surprised', 'hurt']),
      repr(sorted(set(R.EMOTION_CLASS.values()))))
check(u'B5 清单只出现这五类（没有第六类偷偷混进来）',
      all(k in set(R.EMOTION_CLASS.values())
          for c in anims_man for k in anims_man[c]),
      repr(sorted(set(k for c in anims_man for k in anims_man[c]))))

# ================================================================ C 行为
print('\n=== C 行为（真窗口）===')
_item = {'id': 'susie', 'x': 300.0, 'y': 300.0, 'facing': 'down', 'moving': False}
T0 = 1000000
layer.sync([_item], scale=2.0, now_ms=T0, anchor='foot')
_win = layer.window_of('susie')
_base_bits = bits(_win)
_base_size = (None if _win is None else (_win.width(), _win.height()))
check(u'C1 先站定：窗口建起来且画了东西',
      _win is not None and _win.isVisible() and bool(_base_bits),
      u'尺寸 %r' % (_base_size,))

check(u'C2 原始情绪键 laugh 能被接受', layer.play_once('susie', 'laugh', now_ms=T0 + 10))
layer.sync([_item], scale=2.0, now_ms=T0 + 20, anchor='foot')
check(u'C3 开演后**屏幕那一格真的换了图**（比像素，不比尺寸）',
      bits(_win) != _base_bits, u'尺寸 %r → %r' % (_base_size,
                                                  (_win.width(), _win.height())))

_shots = []
for _dt in (20, 140, 260, 380):
    layer.sync([_item], scale=2.0, now_ms=T0 + _dt, anchor='foot')
    _st = layer.oneshot_of('susie')
    _shots.append((_st['emo'] if _st else None, bits(_win)))
check(u'C4 演的过程中情绪一直是 happy(laugh)',
      [s[0] for s in _shots] == ['happy'] * 4, repr([s[0] for s in _shots]))
check(u'C5 四个时间点给出四个不同画面（真在播，不是卡一格）',
      len(set(s[1] for s in _shots)) == 4,
      u'不同画面 %d 个' % len(set(s[1] for s in _shots)))

layer.sync([_item], scale=2.0, now_ms=T0 + 10 + 4 * R.ANIM_FRAME_MS
           + R.ANIM_HOLD_MS + 50, anchor='foot')
check(u'C6 到点自动清状态（不会永远卡在表情上）',
      layer.oneshot_of('susie') is None)
check(u'C7 演完回到站姿那一格（像素级）', bits(_win) == _base_bits,
      u'尺寸 %r' % ((_win.width(), _win.height()),))

# 拒绝路径
check(u'C8 没素材的人不演，且不留状态',
      layer.play_once('addison_tea', 'laugh') is False
      and layer.oneshot_of('addison_tea') is None)
check(u'C9 没有该情绪的人不演（susie 没有 hurt）',
      layer.play_once('susie', 'hurt') is False
      and layer.oneshot_of('susie') is None)
check(u'C10 空 id 不演', layer.play_once('', 'laugh') is False)
layer.play_once('lancer', 'happy', now_ms=T0)
check(u'C11 一人开演不会顺手点亮另一个人',
      layer.oneshot_of('lancer') is not None
      and layer.oneshot_of('susie') is None)
layer.destroy_all()
check(u'C12 销毁时把演出状态一起清掉（防再生时从半截开始）',
      layer.oneshot_of('lancer') is None)

# ================================================================ D 接线（AST）
print('\n=== D 接线（AST）===')


def _func(tree, name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == name:
                    return sub
    return None


_pea = _func(main_tree, 'play_expression_anim')
_npea = _func(main_tree, '_play_npc_expression_anim')
check(u'D1 `play_expression_anim` 与 `_play_npc_expression_anim` 都在',
      _pea is not None and _npea is not None)


def _early_char_id_guard(fn):
    """找 `if char_id: return False` 这种"把 NPC 挡在门外"的守卫。"""
    for sub in ast.walk(fn):
        if not isinstance(sub, ast.If):
            continue
        t = sub.test
        simple = ((isinstance(t, ast.Name) and t.id == 'char_id')
                  or (isinstance(t, ast.Attribute) and t.attr == 'id'))
        if simple:
            for st in sub.body:
                if isinstance(st, ast.Return):
                    v = st.value
                    if isinstance(v, ast.Constant) and v.value is False:
                        return True
    return False


check(u'D2 不再有 `if char_id: return False` 这种把 NPC 挡在门外的守卫',
      not _early_char_id_guard(_pea))
_calls = [getattr(n.func, 'attr', None) or getattr(n.func, 'id', None)
          for n in ast.walk(_pea) if isinstance(n, ast.Call)]
check(u'D3 NPC 分支仍然被真的调用（不是删掉了守卫就完事）',
      '_play_npc_expression_anim' in _calls, repr(sorted(set(c for c in _calls if c))))

_npea_calls = [getattr(n.func, 'attr', None) or getattr(n.func, 'id', None)
               for n in ast.walk(_npea) if isinstance(n, ast.Call)]
check(u'D4 NPC 分支真的调了渲染层的 `play_once`', 'play_once' in _npea_calls,
      repr(sorted(set(c for c in _npea_calls if c))))


def _attrs_read(fn):
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)          # `getattr(self, 'x')` 的字符串形式
    return out


_npea_attrs = _attrs_read(_npea)
check(u'D5 NPC 分支取的是 `_npc_body_layer`（那个池），不是别的对象',
      '_npc_body_layer' in _npea_attrs, repr(sorted(a for a in _npea_attrs
                                                    if a.startswith('_npc'))))

# Ralsei 老路径还在：仍然会写 `_expr_anim_at` 且仍然调 play_animation_once
_pea_attrs = _attrs_read(_pea)
_pea_called = [n.func.attr for n in ast.walk(_pea)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
check(u'D6 Ralsei 老路径没被拆：仍然写 `_expr_anim_at` 且仍然调 `play_animation_once`',
      '_expr_anim_at' in _pea_attrs and 'play_animation_once' in _pea_called,
      repr(sorted(set(_pea_called))))

# 表情动画表：AST 里必须看得见 laugh 与 angry
_ea = _func(dui_tree, 'set_face')            # 只是确认 ClassDef 找得到
_dui_cls = None
for node in dui_tree.body:
    if isinstance(node, ast.ClassDef) and node.name == 'DialogueUI':
        _dui_cls = node
_anim_keys = set()
if _dui_cls is not None:
    for node in _dui_cls.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'EXPRESSION_ANIM':
                    if isinstance(node.value, ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant):
                                _anim_keys.add(k.value)
check(u'D7 表情动画表里有 `laugh`（以前是死键：表里写 happy，规则只会产 laugh）',
      'laugh' in _anim_keys, repr(sorted(_anim_keys)))
check(u'D8 表情动画表里有 `angry`（用户裁定 A 案：五类对齐）',
      'angry' in _anim_keys, repr(sorted(_anim_keys)))
check(u'D9 `happy` 仍保留（兼容 emotion_system / 老调用方）',
      'happy' in _anim_keys, repr(sorted(_anim_keys)))

# ================================================================ E 素材质量契约
print('\n=== E 素材质量契约（在**产物**上重算）===')


def _walk_bbox(cid):
    fr = (frames_man.get(cid) or {}).get('frames') or {}
    d = 'down' if 'down' in fr else (sorted(fr)[0] if fr else None)
    if not d:
        return None, None
    out = []
    for row in fr[d][:4]:
        b = bbox(os.path.join(DR, cid, row['f']))
        if b:
            out.append(b)
    if not out:
        return None, None
    hw = png_hw(os.path.join(DR, cid, fr[d][0]['f']))
    return hw, max(out, key=lambda t: t[2])


_h_bad, _w_bad = [], []
for c, k, d, r in _files:
    hw, base = _walk_bbox(c)
    if hw is None or base is None:
        continue
    p = os.path.join(DR, c, r['f'].replace('/', os.sep))
    b = bbox(p)
    if b is None:
        continue
    # ★ 这里必须拿**画布高度**比画布高度（构建期就是这么设的闸）。
    #   第196轮自己踩过：拿走路帧的**画布**高度去比候选帧的**实心区**高度，
    #   单位不一致 ⇒ 把 king/queen 两张本来合格的帧判成越界（假问题）。
    if abs(hw[1] - png_hw(p)[1]) > 2:
        _h_bad.append((r['f'], png_hw(p)[1], hw[1]))
    if b[0] > 1.45 * base[0]:
        _w_bad.append((r['f'], b[0], base[0]))
check(u'E1 每帧画布高度与该角色走路帧同族（差 ≤2px）',
      not _h_bad, u'%d 个越界 %r' % (len(_h_bad), _h_bad[:3]))
check(u'E2 每帧实心区不过宽（≤1.45× 走路帧实心宽；防夹带道具/第二个人）',
      not _w_bad, u'%d 个越界 %r' % (len(_w_bad), _w_bad[:3]))

_all_ids = sorted(frames_man.keys())
_tok = dict(R.__dict__.get('_TOKEN_FOR_CHECK') or {})
_dup = []
for c, k, d, r in _files:
    name = r.get('src_name') or r['f']
    me = c.lower()
    for o in _all_ids:
        if o == c:
            continue
        if re.search(r'(?<![a-z])%s(?![a-z])' % re.escape(o.lower()), name, re.I):
            # `susiedark` 与原作同 token `susie` 互为别名，不算串味
            if (o == 'susiedark' and 'susie' in name.lower()) or \
                    (c == 'susiedark' and o == 'susie'):
                continue
            _dup.append((c, o, name))
check(u'E3 没有"多人帧"（文件名里不出现别的角色 token）', not _dup,
      u'%d 条 %r' % (len(_dup), _dup[:3]))

_POSE = ('fall', 'kneel', 'sit', 'sleep', 'lying', 'jump', 'racing',
         'ground', 'dead', 'splat')
_pose = []
for c, k, d, r in _files:
    name = (r.get('src_name') or '').lower()
    for w in _POSE:
        if re.search(r'(?:^|_)%s(?:_|\.|$)' % w, name):
            _pose.append((r['src_name'], w))
check(u'E4 没有"整个人换姿势"的帧（摔/跪/坐/躺/骑）', not _pose,
      u'%d 条 %r' % (len(_pose), _pose[:3]))

# ================================================================ F 自检
print('\n=== F 自检 ===')
# A5 + B5 + C12 + D9 + E4 + F1/F2/F3 = 38
EXPECT = 38
check(u'F1 判据条数 == 声明的 %d 条' % EXPECT, (_n['p'] + _n['f']) + 3 == EXPECT,
      u'实跑 %d 条（F1 之前，未计 F1/F2/F3）' % (_n['p'] + _n['f'],))

_writes = []
for node in ast.walk(ast.parse(rd(os.path.abspath(__file__)))):
    if isinstance(node, ast.Call):
        fn = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
        if fn == 'open':
            modes = [a.value for a in node.args
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if any(('w' in m or 'a' in m or '+' in m) for m in modes[1:]):
                _writes.append(getattr(node, 'lineno', -1))
        elif fn in ('write_text', 'dump'):
            _writes.append(getattr(node, 'lineno', -1))
check(u'F2 本套件只读：AST 里没有写模式的 open / dump', not _writes, u'%r' % _writes[:5])

# ★ 这条判据本身差点成为反面教材：第一版把标记字面量写进了**判据名**，
#   于是 `[FAIL] 判据里没有把 \`[PASS]\`/\`[FAIL]\` ...` 这行本身就往 stdout
#   里多打了两个标记 ⇒ `run_all` 的计数当场被污染。
#   ⇒ 标记用**拼接**构造，判据名也不写它们。
_MARK_P = '[' + 'PASS' + ']'
_MARK_F = '[' + 'FAIL' + ']'
_echo = []
for node in ast.walk(ast.parse(rd(os.path.abspath(__file__)))):
    if not (isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'check'):
        continue
    # 只看 name（args[0]）与 extra（args[2]）—— `check` 会把它们打进 stdout
    for a in (list(node.args[:1]) + list(node.args[2:3])):
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            if _MARK_P in a.value or _MARK_F in a.value:
                _echo.append(getattr(node, 'lineno', -1))
check(u'F3 判据名与附加信息里不出现通过/失败标记（否则会污染计数）',
      not _echo, u'%r' % _echo[:5])

print('\nPASS=%d FAIL=%d' % (_n['p'], _n['f']))
sys.exit(0 if _n['f'] == 0 else 1)
