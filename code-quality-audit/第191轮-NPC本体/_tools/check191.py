# -*- coding: utf-8 -*-
u"""第191轮 · NPC 本体（素材落地 + 渲染层 + 一视同仁接线）。

## 这一轮要证明的事

用户口径（2026-11-16，两条）：

  ① 素材不在的问题被当场推翻 —— 原话
     `在场的人？咱不是全部都做吗，而且，素材在原作游戏里面都有啊，你用就好`
     ⇒ 素材就在 `项目文件夹/deltarune/`，不是"没图"，是我**查错了范围**。
  ② `一视同仁，不再是主体为ralsei的项目了`（第190轮定的，本轮继续生效）
  ③ 找不到走路帧的人：`参考原作，应为找不到走路帧那就意味着要么原作里
     有其他移动方式要么就是不动`
  ④ 非人站位（sign / dumpster / …）：`先留着并登记`

## 关键设计（判据就是为了钉住这三条）

**遮挡契约按「屏幕 Y」排序 ⇒ 一个人一个小窗口，不能是一张全屏画布。**
一张全屏透明画布只有**一个** z 序：要么全体压在所有窗口之上、要么全在之下，
两种都不对。桌宠自己就是"一个窗口 + 按脚底 Y 插进 z 序"
（`main._apply_pet_z_order` → `floor_manager.pick_insert_after_by_foot_y`），
所以 NPC 走**同一条路径**才叫一视同仁 —— 这正是 D6 与 C6 要钉的。

**脚底锚点必须与 z 序锚点是同一处。** `Body.x/y` 是全项目的"身体中心"
（`_npc_interact_candidates` 用 `b.x/b.y ± ACTOR_HALF_W/H` 当命中框），
而遮挡排序用脚底。若窗口按中心摆、"插到某人之后"按脚底算，两者会在
"身高差 2px 的两个人"上给出相反答案 ⇒ C3/C4/C6 三条一起钉住这条链。

**像素倍率用 `camera.scale`，不是 `_cached_scale_factor`。** 后者 =
`camera.scale × pet_scale`，而 `pet_scale` 是用户调**桌宠一个**的旋钮；
拿它放大 NPC 会让"我把 Ralsei 调大"变成"整条街的人都变大了"。
默认 `pet_scale = 1.0` 时两者数值相同，所以这是一个**只在用户动过旋钮后**
才显形的偏差 —— 机器不容易抓到，只能靠 D4 从代码上钉。

## 分段

A 清单↔磁盘对账 14 · B 取帧 13 · C 窗口/锚点/z 序 21 · D 接线（AST）13 ·
E 一视同仁 5 · F 自检 3 = **69 条**

## 本套件自己踩过的三个坑（都留在对应判据的注释里）

1. **A9b 判据过宽**：第一版断言"`stand` 类方向数不许 >2"，实测 `lancer` 就是
   四方向各 1 帧（站着也能转身看你，原作行为）⇒ 误报。改成"不许**多方向 + 多帧**"。
2. **D4 是纯文本扫出来的假象**：`_npc_body_scale` 的 **docstring 第一句**就是
   「★ 为什么不是 `_cached_scale_factor`」，按字符串位置比出来的是"注释谁写在
   前面"，与代码顺序无关（判据恒假，且假得很像真的）⇒ 改走 AST 字面量行号。
3. **A0b 只在 except 里发** ⇒ 条数随环境变（正常时少一条）。改成恒发。

## 两条"负控制"（不配对就等于没测）

· C2/C6 —— 无立绘的人**不建窗口**；有立绘的人 z 序回调拿到的必须是**脚底**
  （拿中心也能"通过"，只要判据写松了就看不出来）。
· D9/D12 —— `_scene_topmost_targets_ordered` 里 NPC 与桌宠**混排**；
  而老函数 `_scene_topmost_targets` 里**不许**出现 `visible_windows`
  （成对：证明新函数不是把老函数悄悄改成一样）。
"""
import ast
import hashlib
import io
import json
import os
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(REPO, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
RENDER_PY = os.path.join(MODS, 'npc_body_render.py')
SPRITES = os.path.join(PET, 'assets', 'sprites', 'dr')
MANIFEST = os.path.join(SPRITES, '_npc_frames.json')

# ★ 本套件要建 QLabel / QPixmap，必须有 QApplication；用 offscreen 保证
#   跑在无显示器的环境里也一致（`run_all` 里该套件也标了 offscreen=True）。
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, PET)
sys.path.insert(0, MODS)

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def lf(s):
    """CRLF → LF。★ 锚点必须先归一：`main.py` 盘上是 CRLF，
    按 `\\n` 写的锚点 `old in s` **恒假**（第185轮 M11~M15 五条假绿）。"""
    return s.replace('\r\n', '\n').replace('\r', '\n')


def png_size(path):
    """只读 PNG 的 IHDR 拿宽高 —— **不经过 Qt**，这样"清单说多大"与
    "文件真实多大"才是两条独立来源（都走 QPixmap 就是自己证自己）。"""
    try:
        with io.open(path, 'rb') as f:
            head = f.read(33)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        return None
    return struct.unpack('>I', head[16:20])[0], struct.unpack('>I', head[20:24])[0]


def sha_file(path):
    h = hashlib.sha256()
    try:
        with io.open(path, 'rb') as f:
            for blk in iter(lambda: f.read(65536), b''):
                h.update(blk)
    except OSError:
        return None
    return h.hexdigest()


def pngs_in(dirpath):
    try:
        return sorted(n for n in os.listdir(dirpath) if n.lower().endswith('.png'))
    except OSError:
        return []


# ================================================================ A 清单 ↔ 磁盘
print(u'=== A 清单与磁盘对账（两条独立来源）===')
check(u'A0 清单文件存在', os.path.isfile(MANIFEST), MANIFEST)

MAN = {}
_man_err = u''
try:
    MAN = json.loads(rd(MANIFEST))
except Exception as e:                                   # noqa: BLE001
    _man_err = u'%s' % (e,)
check(u'A0b 清单能解析成 JSON', not _man_err, _man_err)
# ★ 这两条**恒发**（第一版把 A0b 写在 except 里 ⇒ 正常时少一条，条数随环境变，
#   与第171轮"判据条数不随环境变"同一条纪律）。

CHARS = MAN.get('characters') or {}
NO_ART = list(MAN.get('no_art') or [])
NOT_A_PERSON = list(MAN.get('not_a_person') or [])

check(u'A1 清单是第191轮的产物（schema/round 对得上）',
      MAN.get('schema_version') == 1 and MAN.get('round') == 191,
      u'schema=%r round=%r' % (MAN.get('schema_version'), MAN.get('round')))

check(u'A2 角色数只增不减（历史段冻结口径，不写死随轮次增长的数）',
      len(CHARS) >= 18, u'%d 人' % len(CHARS))

# ---- A3/A4/A5：逐角色、逐帧三条独立核对（目录存在 / 尺寸 / sha256）----
_missing_dir, _bad_size, _bad_sha, _orphans, _n_frames = [], [], [], [], 0
for nid in sorted(CHARS):
    d = os.path.join(SPRITES, nid)
    if not os.path.isdir(d):
        _missing_dir.append(nid)
        continue
    listed = set()
    for dr, rows in sorted((CHARS[nid].get('frames') or {}).items()):
        for row in rows:
            fn = row.get('f')
            if not fn:
                continue
            listed.add(fn)
            _n_frames += 1
            p = os.path.join(d, fn)
            real = png_size(p)
            if real != (row.get('w'), row.get('h')):
                _bad_size.append('%s/%s 清单%s 实际%s'
                                 % (nid, fn, (row.get('w'), row.get('h')), real))
            if sha_file(p) != row.get('sha256'):
                _bad_sha.append('%s/%s' % (nid, fn))
    extra = [n for n in pngs_in(d) if n not in listed]
    if extra:
        _orphans.append('%s: %r' % (nid, extra))

check(u'A3 每个角色目录都真实存在', not _missing_dir, u'缺 %r' % (_missing_dir,))
check(u'A4 清单尺寸 == PNG 真实尺寸（IHDR 直读，不经 Qt）',
      not _bad_size, u'%d 处不符 %r' % (len(_bad_size), _bad_size[:3]))
check(u'A5 清单 sha256 == 磁盘 sha256（运行期零猜解的前提：清单就是事实）',
      not _bad_sha, u'%d 处不符 %r' % (len(_bad_sha), _bad_sha[:3]))
check(u'A6 目录里没有清单外的散图（双向对账：防止"复制了但没登记"）',
      not _orphans, u'%r' % (_orphans[:3],))

# ---- A7/A8：kind 与帧数 ----
_bad_kind = [nid for nid in CHARS
             if CHARS[nid].get('kind') not in ('walk', 'stand')]
MAXFD = int(MAN.get('max_frames_per_dir') or 4)
_bad_cnt = []
for nid in sorted(CHARS):
    for dr, rows in (CHARS[nid].get('frames') or {}).items():
        if not (1 <= len(rows) <= MAXFD):
            _bad_cnt.append('%s/%s=%d' % (nid, dr, len(rows)))
check(u'A7 每个角色都标了 kind（walk / stand，取值只在枚举里）',
      not _bad_kind, u'异常 %r' % (_bad_kind,))
check(u'A8 每方向帧数在 1..max_frames_per_dir 之间（原作者就是 4 帧一轮）',
      not _bad_cnt, u'max=%d 越界 %r' % (MAXFD, _bad_cnt[:3]))

# ---- A9：walk 类必须有方向；stand 类允许只有 down（= 用户口径③）----
#
# ★ A9b 第一版写的是"stand 类方向数不许 >2"，实测 **lancer** 就是 4 方向 × 1 帧
#   —— 站着的立绘本来就有四个朝向（转身看你是原作的正常行为），那不是"把走路
#   标成了站"。⇒ 判据**过宽**（误报），改成"不许同时多方向 + 多帧"：那才是
#   「一步一顿的走路循环」的特征。真源实测：lancer 4×1 / susiedark 1×4 都合法，
#   没有任何一个是 4×4。
_walk_no_dir, _stand_walklike = [], []
for nid in sorted(CHARS):
    e = CHARS[nid]
    dirs = e.get('frames') or {}
    if e.get('kind') == 'walk' and len(dirs) < 3:
        _walk_no_dir.append('%s=%r' % (nid, sorted(dirs)))
    if e.get('kind') == 'stand':
        _mx = max([len(v) for v in dirs.values()] or [0])
        if len(dirs) >= 3 and _mx >= 3:
            _stand_walklike.append('%s=%d向×%d帧' % (nid, len(dirs), _mx))
check(u'A9 `walk` 类至少 3 个方向（缺方向的走路人必然是选错族了）',
      not _walk_no_dir, u'%r' % (_walk_no_dir,))
check(u'A9b `stand` 类不许"多方向 + 多帧"（那才是走路循环的特征；'
      u'但四方向各 1 帧合法 —— 站着也能转身看你）',
      not _stand_walklike, u'%r' % (_stand_walklike,))

# ---- A10/A11：登记口径自洽 ----
check(u'A10 `no_art` 与 `characters` 不相交（同一个人不能既"有图"又"没图"）',
      not (set(NO_ART) & set(CHARS)),
      u'交集 %r' % sorted(set(NO_ART) & set(CHARS)))
check(u'A11 `not_a_person` ⊆ `no_art`（不是人 ⇒ 一定没立绘，否则会被画成一个假人）',
      set(NOT_A_PERSON) <= set(NO_ART),
      u'越界 %r' % sorted(set(NOT_A_PERSON) - set(NO_ART)))

# ================================================================ B 取帧
print(u'\n=== B 取帧（清单驱动，运行时零猜解）===')
from PyQt5.QtWidgets import QApplication                     # noqa: E402
_app = QApplication.instance() or QApplication([])

from modules import npc_body_render as R                      # noqa: E402

book = R.NpcFrameBook()
check(u'B1 清单经模块加载后角色数对得上', len(book.ids()) == len(CHARS),
      u'模块 %d / 磁盘 %d' % (len(book.ids()), len(CHARS)))
check(u'B2 `no_art` 如实透出（不静默：缺谁是有据可查的）',
      sorted(book.no_art()) == sorted(NO_ART),
      u'%d 人' % len(book.no_art()))

# ---- B3：全量取帧 —— 硬证据，"难匹配也得匹配"的同款做法（第190轮 E 段）----
_bad_pm, _n_pm = [], 0
for nid in sorted(CHARS):
    for dr in sorted((CHARS[nid].get('frames') or {}).keys()):
        for i in range(len(CHARS[nid]['frames'][dr])):
            _n_pm += 1
            pm = book.frame(nid, dr, i)
            if pm is None or pm.isNull():
                _bad_pm.append('%s/%s/%d' % (nid, dr, i))
            elif (pm.width(), pm.height()) != (CHARS[nid]['frames'][dr][i]['w'],
                                               CHARS[nid]['frames'][dr][i]['h']):
                _bad_pm.append('%s/%s/%d 尺寸不符' % (nid, dr, i))
check(u'B3 清单里登记的每一帧都真能取到非空 QPixmap，且尺寸与清单一致',
      not _bad_pm, u'%d 帧全过 / 坏 %d %r' % (_n_pm, len(_bad_pm), _bad_pm[:3]))

# ---- B4：缺方向回落 ----
_kris = 'kris' if 'kris' in CHARS else sorted(CHARS)[0]
have_k = sorted((CHARS.get(_kris, {}).get('frames') or {}).keys())
check(u'B4 缺某个方向时按 DIR_FALLBACK 回落（kris 没有 up ⇒ 落 down）',
      ('up' not in have_k and book.dir_of(_kris, 'up') == 'down')
      or ('up' in have_k and book.dir_of(_kris, 'up') == 'up'),
      u'%s 有 %r ⇒ up 取到 %r' % (_kris, have_k, book.dir_of(_kris, 'up')))

check(u'B5 左右**不互转**（左右脸不一样，转了就是另一个人）',
      R.DIR_FALLBACK == ('down', 'up', 'left', 'right'), u'%r' % (R.DIR_FALLBACK,))

_na = NO_ART[0] if NO_ART else 'catti'
check(u'B6 没立绘的人 `dir_of` 返回 None（调用方据此不画，而不是画空窗）',
      book.dir_of(_na, 'down') is None, u'%s' % _na)
check(u'B7 没立绘的人 `frame` 返回 None（**不造假帧**）',
      book.frame(_na, 'down', 0) is None, u'%s' % _na)
check(u'B8 没立绘的人 `frame_count` == 0', book.frame_count(_na, 'down') == 0)

# ---- B9：越界不炸 ----
_cnt = book.frame_count(_kris, book.dir_of(_kris, 'down') or 'down')
check(u'B9 帧号越界取模（不 IndexError，也不返回 None）',
      book.frame_name(_kris, 'down', _cnt + 3) == book.frame_name(_kris, 'down', 3 % _cnt),
      u'count=%d' % _cnt)

# ---- B10~B12：缩放缓存（30fps × 24 人，缓存不命中就拖垮主线程）----
s1 = book.scaled(_kris, 'down', 0, 2.0)
s2 = book.scaled(_kris, 'down', 0, 2.0)
check(u'B10 同倍率命中缓存（拿到**同一个** QPixmap 对象）', s1 is s2)
check(u'B11 缩放尺寸 = 原始 × 倍率', s1 is not None
      and abs(s1.width() - round(book.frame(_kris, 'down', 0).width() * 2.0)) <= 1,
      u'%s vs %s' % ((s1.width(), s1.height()) if s1 else None,
                     (book.frame(_kris, 'down', 0).width(),
                      book.frame(_kris, 'down', 0).height())))
s3 = book.scaled(_kris, 'down', 0, 2.0000001)
check(u'B12 浮点噪声（2.0000001）仍命中同一缓存 —— 键是**千分比**不是 float 原值',
      s3 is s1)
_ok_bad = True
for bad in (0, -3, 'x', None):
    try:
        pm = book.scaled(_kris, 'down', 0, bad)
        if pm is None or pm.isNull():
            _ok_bad = False
    except Exception:
        _ok_bad = False
check(u'B12b 坏倍率（0 / 负数 / 字符串 / None）不抛且退回 1.0', _ok_bad)

# ================================================================ C 窗口/锚点/z 序
print(u'\n=== C 窗口池 · 锚点 · z 序 ===')
from PyQt5.QtCore import Qt                                    # noqa: E402

layer = R.NpcBodyLayer(book=book)
_zcalls = []


def fake_z(hwnd, foot_y):
    _zcalls.append((hwnd, float(foot_y)))
    return True


ART = sorted(CHARS)
A1 = ART[0]
A2 = ART[1] if len(ART) > 1 else ART[0]

items = [
    {'id': A1, 'x': 500.0, 'y': 300.0, 'facing': 'down', 'moving': False},
    {'id': _na, 'x': 100.0, 'y': 100.0, 'facing': 'down', 'moving': False},
]
n = layer.sync(items, scale=2.0, now_ms=0, zorder=fake_z, anchor='center')
check(u'C1 无立绘的人被跳过（2 条只显示 1 条）', n == 1, u'n=%r' % (n,))
check(u'C2 负控制：无立绘的人**没有**建窗口（不是建了再藏）',
      layer.window_of(_na) is None)

win = layer.window_of(A1)
check(u'C3 有立绘的人建了窗口', win is not None)
if win is not None:
    _h = win.height()
    check(u'C4 anchor=center ⇒ 窗口 top = 中心 y − 半高（Body.x/y 是中心不是脚底）',
          abs(win.y() - (300.0 - _h / 2.0)) <= 1,
          u'top=%d 期望=%d' % (win.y(), 300.0 - _h / 2.0))
    check(u'C5 窗口 bottom == 脚底 == 中心 y + 半高（遮挡锚点与窗口下沿同一处）',
          abs((win.y() + win.height()) - (300.0 + _h / 2.0)) <= 1,
          u'bottom=%d 期望=%d' % (win.y() + win.height(), 300.0 + _h / 2.0))
    check(u'C6 ★ z 序回调拿到的 foot_y == 窗口 bottom（不是中心 y —— 两者差半高）',
          len(_zcalls) == 1 and abs(_zcalls[0][1] - (win.y() + win.height())) <= 1
          and abs(_zcalls[0][1] - 300.0) > 1,
          u'回调 %r · bottom=%d' % (_zcalls, win.y() + win.height()))
    check(u'C7 水平居中于 x', abs((win.x() + win.width() / 2.0) - 500.0) <= 1,
          u'中心=%s' % (win.x() + win.width() / 2.0))

# ---- C8/C9：z 序节流 ----
_before = len(_zcalls)
layer.sync(items, scale=2.0, now_ms=10, zorder=fake_z, anchor='center')
check(u'C8 脚底没动 ⇒ 不重复设 z 序（节流生效，否则每帧 24 次 SetWindowPos）',
      len(_zcalls) == _before, u'%d → %d' % (_before, len(_zcalls)))
items_moved = [dict(items[0], y=320.0), items[1]]
layer.sync(items_moved, scale=2.0, now_ms=20, zorder=fake_z, anchor='center')
check(u'C9 脚底移动 ≥2px ⇒ 重排一次', len(_zcalls) == _before + 1,
      u'%d → %d' % (_before, len(_zcalls)))

# ---- C10：空表 ⇒ 全隐藏 ----
layer.sync([], scale=2.0, now_ms=30, zorder=fake_z)
check(u'C10 传入空表 ⇒ 全部隐藏（且 `visible_ids` 清空）',
      layer.visible_ids() == [], u'%r' % (layer.visible_ids(),))

# ---- C11：重复 id 去重 + 上限 ----
layer2 = R.NpcBodyLayer(book=book)
n = layer2.sync([dict(items[0]), dict(items[0])], scale=1.0, now_ms=0, zorder=None)
check(u'C11 同一 id 传两次只画一次（去重）', n == 1, u'n=%r' % (n,))
many = [{'id': A1, 'x': float(i), 'y': float(i), 'facing': 'down', 'moving': False}
        for i in range(R.MAX_BODIES + 7)]
# 同一个 id 会先被去重 ⇒ 用"多人"再验上限：把 no_art 当噪声、有立绘的全排进去
crowd = []
for k, nid in enumerate(ART):
    for j in range(3):
        crowd.append({'id': nid, 'x': float(k), 'y': float(j), 'moving': False})
_prev = R.MAX_BODIES
try:
    R.MAX_BODIES = 3
    lay3 = R.NpcBodyLayer(book=book)
    n3 = lay3.sync(crowd, scale=1.0, now_ms=0, zorder=None)
    check(u'C12 同屏上限生效（改小 MAX_BODIES ⇒ 显示数被截断）', n3 == 3,
          u'n=%r 上限=3' % (n3,))
finally:
    R.MAX_BODIES = _prev
n_many = layer2.sync(many, scale=1.0, now_ms=0, zorder=None)
check(u'C12b 同一 id 铺满上限也不画多份', n_many == 1, u'n=%r' % (n_many,))

# ---- C13：走路帧只在 moving 时轮播 ----
mov = [{'id': A1, 'x': 10.0, 'y': 10.0, 'facing': 'down', 'moving': True}]
_seen = set()
for t in range(0, R.FRAME_MS * 4, R.FRAME_MS):
    layer2.sync(mov, scale=1.0, now_ms=t, zorder=None, anchor='foot')
_w = layer2.window_of(A1)
for t in range(0, R.FRAME_MS * 4, R.FRAME_MS):
    layer2.sync(mov, scale=1.0, now_ms=t, zorder=None, anchor='foot')
    _seen.add(layer2.window_of(A1).pixmap().cacheKey())
_cap = R.NpcFrameBook().frame_count(A1, 'down')
check(u'C13 moving=True ⇒ 四拍里出现多于一帧（真的在播）',
      _cap < 2 or len(_seen) > 1, u'帧型 %d 个 / 该角色 down 有 %d 帧'
      % (len(_seen), _cap))

still = [{'id': A1, 'x': 10.0, 'y': 10.0, 'facing': 'down', 'moving': False}]
_seen2 = set()
for t in range(0, R.FRAME_MS * 4, R.FRAME_MS):
    layer2.sync(still, scale=1.0, now_ms=t, zorder=None, anchor='foot')
    _seen2.add(layer2.window_of(A1).pixmap().cacheKey())
check(u'C13b moving=False ⇒ 钉在首帧（站着的人不抽腿 —— 用户口径③）',
      len(_seen2) == 1, u'帧型 %d 个' % len(_seen2))

# ---- C14：窗口标志（加了 topmost 就等于毁掉遮挡契约）----
_flags = int(win.windowFlags()) if win is not None else 0
check(u'C14 ★★ 本体窗口**不带** WindowStaysOnTopHint（带了遮挡就彻底失效）',
      not (_flags & int(Qt.WindowStaysOnTopHint)), u'flags=0x%x' % _flags)
check(u'C14b 本体窗口是 Tool + 无边框 + 不抢焦点（不进任务栏 / 不吃点击）',
      bool(_flags & int(Qt.Tool)) and bool(_flags & int(Qt.FramelessWindowHint))
      and bool(_flags & int(Qt.WindowDoesNotAcceptFocus)), u'flags=0x%x' % _flags)

# ---- C15：visible_windows 按脚底 Y 升序（成组置顶要用的口径）----
lay4 = R.NpcBodyLayer(book=book)
lay4.sync([{'id': ART[0], 'x': 0.0, 'y': 900.0, 'moving': False},
           {'id': ART[1], 'x': 0.0, 'y': 100.0, 'moving': False},
           {'id': ART[2], 'x': 0.0, 'y': 500.0, 'moving': False}],
          scale=1.0, now_ms=0, zorder=None, anchor='foot')
_vw = lay4.visible_windows()
_ys = [t[2] for t in _vw]
check(u'C15 `visible_windows` 按脚底 Y **升序**（= 从后到前，与桌面 z 序同一条口径）',
      len(_vw) == 3 and _ys == sorted(_ys), u'脚底 Y %r' % (_ys,))

# ---- C16：窗口复用（隐藏后再出现不新建）----
_w_before = lay4.window_of(ART[0])
lay4.sync([], scale=1.0, now_ms=0, zorder=None)
lay4.sync([{'id': ART[0], 'x': 0.0, 'y': 900.0, 'moving': False}],
          scale=1.0, now_ms=0, zorder=None, anchor='foot')
check(u'C16 隐藏后重新出现**复用**同一个窗口（不每帧新建 → 不漏句柄）',
      lay4.window_of(ART[0]) is _w_before)

# ---- C17：`hide_all` 真的清状态 ----
# ★ 为什么单列一条：`sync([])` 走的是 sync 内部的隐藏分支，而 `hide_all()` 是
#   **另一条路径**（`_npc_body_tick` 在「开关关掉」和「没人可画」时调它）。
#   M20 变异（hide_all 不清 `_visible`）第一版**红 0** —— 就是因为它没被覆盖。
lay5 = R.NpcBodyLayer(book=book)
lay5.sync([{'id': ART[0], 'x': 5.0, 'y': 5.0, 'moving': False}],
          scale=1.0, now_ms=0, zorder=None)
_before_ids = lay5.visible_ids()
lay5.hide_all()
check(u'C17 `hide_all` 之后：可见集合清空 + 窗口不可见 + `visible_windows` 为空',
      _before_ids != [] and lay5.visible_ids() == []
      and lay5.visible_windows() == []
      and not lay5.window_of(ART[0]).isVisible(),
      u'之前 %r → 之后 %r' % (_before_ids, lay5.visible_ids()))

# ---- C18：`destroy_all` 之后池子空了（否则析构后引用还在）----
lay6 = R.NpcBodyLayer(book=book)
lay6.sync([{'id': ART[0], 'x': 5.0, 'y': 5.0, 'moving': False}],
          scale=1.0, now_ms=0, zorder=None)
lay6.destroy_all()
check(u'C18 `destroy_all` 之后窗口池与可见集合都空（不留悬空句柄）',
      lay6.count_windows() == 0 and lay6.visible_ids() == [],
      u'池=%d' % lay6.count_windows())

# ================================================================ D 接线（AST）
print(u'\n=== D 接线（AST，不 import main：import 会构造真机）===')
MSRC = lf(rd(MAIN_PY))
MTREE = ast.parse(MSRC)
RSRC = lf(rd(RENDER_PY))
RTREE = ast.parse(RSRC)


def funcs(tree):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(node.name, []).append(node)
    return out


MF = funcs(MTREE)


def body_src(node):
    return lf(ast.get_source_segment(MSRC, node) or u'')


def calls_of(tree, name):
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == name):
            out.append(node.lineno)
    return sorted(out)


check(u'D1 `main.py` import 了本体渲染模块',
      u'import npc_body_render' in MSRC, u'from modules import npc_body_render')
check(u'D2 开关常量存在（`NPC_BODY_RENDER` 可关 ⇒ 关掉立刻隐藏全部窗口）',
      u'NPC_BODY_RENDER' in MSRC and u'NPC_BODY_MAX' in MSRC)

_tick = calls_of(MTREE, '_npc_body_tick')
_upd = calls_of(MTREE, '_update_scene_layer')
check(u'D3 ★ 每帧调用**恰好一次**，且排在 `_update_scene_layer()` **之后**'
      u'（房间本体要先读到这一帧刚算好的相机与画布偏移）',
      len(_tick) == 1 and len(_upd) >= 1 and _tick[0] > _upd[-1],
      u'本体@%r / 场景@%r' % (_tick, _upd))

_sc = MF.get('_npc_body_scale') or []


def _get_linenos(node, names):
    """`self.__dict__.get('xxx')` 的字面量取值行号（只认 **AST 调用**）。

    ★ 为什么不用 `src.index('_cached_scale_factor')`：那个函数的 **docstring
      第一句**就是「★ 为什么不是 `_cached_scale_factor`」⇒ 字符串位置落在注释里，
      比出来的是"注释谁写在前面"，与代码顺序无关（判据**恒假**，且假得很像真的）。
      这正是第85/129轮那条「纯文本扫 API ＝ 假象」的同款。
    """
    out = {}
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr == 'get':
            for a in sub.args:
                if isinstance(a, ast.Constant) and a.value in names:
                    out.setdefault(a.value, sub.lineno)
    return out


_gl = _get_linenos(_sc[0], ('_scene_camera', '_cached_scale_factor')) if _sc else {}
check(u'D4 ★★ 倍率**优先**用 `camera.scale`，`_cached_scale_factor` 只做兜底'
      u'（后者含 `pet_scale`，那是用户调桌宠一个的旋钮 —— 拿它放大 NPC，'
      u'「我把 Ralsei 调大」就变成「整条街的人都变大了」）',
      '_scene_camera' in _gl and '_cached_scale_factor' in _gl
      and _gl['_scene_camera'] < _gl['_cached_scale_factor'],
      u'camera@%r / cached@%r'
      % (_gl.get('_scene_camera'), _gl.get('_cached_scale_factor')))

_zo = MF.get('_npc_body_zorder') or []
_zo_src = body_src(_zo[0]) if _zo else u''
check(u'D5 ★ 置顶态下早退（置顶带内的前后关系没法用"插到某人之后"表达，'
      u'与 `_apply_pet_z_order` 同一条理由）',
      u'_scene_topmost_on' in _zo_src and u'return' in _zo_src,
      u'形参=%r' % ([a.arg for a in (_zo[0].args.args if _zo else [])],))
check(u'D6 ★★★ z 序走 `floor_manager` **同一条路径**（一视同仁的落地）',
      u'get_insert_after_hwnd' in _zo_src and u'foot_y' in _zo_src
      and u'set_window_behind' in _zo_src,
      u'get_insert_after_hwnd=%s / set_window_behind=%s'
      % (u'get_insert_after_hwnd' in _zo_src, u'set_window_behind' in _zo_src))

_it = MF.get('_npc_body_items') or []
_it_src = body_src(_it[0]) if _it else u''
check(u'D7 ★ 两套空间分开算：桌面直接用、房间走 `cam.to_view(...) × scale`'
      u'（混了就是"人站在屏幕外/比房间大五倍"）',
      u'DESKTOP_SCENE' in _it_src and u'to_view' in _it_src
      and u'_scene_output_offset' in _it_src,
      u'DESKTOP_SCENE=%s to_view=%s off=%s'
      % (u'DESKTOP_SCENE' in _it_src, u'to_view' in _it_src,
         u'_scene_output_offset' in _it_src))

_anchor_ok = False
for node in ast.walk(MTREE):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == 'sync':
        for kw in node.keywords:
            if kw.arg == 'anchor' and isinstance(kw.value, ast.Constant) \
                    and kw.value.value == 'center':
                _anchor_ok = True
check(u'D8 调用方传 `anchor="center"`（中心→脚底的换算只在渲染层做一次）',
      _anchor_ok)

_ord = MF.get('_scene_topmost_targets_ordered') or []
_ord_src = body_src(_ord[0]) if _ord else u''
_base = MF.get('_scene_topmost_targets') or []
_base_src = body_src(_base[0]) if _base else u''
check(u'D9 ★★★ 新排序函数真的把 NPC 和桌宠**混在一起**按脚底 Y 排'
      u'（不是"NPC 追加在桌宠后面"——那样站在 Ralsei 前面的人会反被他盖住）',
      u'visible_windows' in _ord_src and u'people.sort' in _ord_src,
      u'visible_windows=%s sort=%s'
      % (u'visible_windows' in _ord_src, u'people.sort' in _ord_src))
check(u'D9b ★ 负控制：老函数 `_scene_topmost_targets` 里**没有** NPC 逻辑'
      u'（成对 —— 证明新函数不是把老的悄悄改成了同一份）',
      u'visible_windows' not in _base_src and u'_npc_body' not in _base_src,
      u'老函数长度 %d' % len(_base_src))
check(u'D10 画布仍第一（最底）、灵魂/幽灵仍最后（最上）—— 极性没被重排破坏',
      u"canvas + " in _ord_src and u"+ top" in _ord_src,
      u'canvas 首=%s top 尾=%s'
      % (_ord_src.find(u'canvas +') >= 0, _ord_src.rfind(u'+ top') >= 0))

_use = []
for name in ('_set_scene_topmost', '_resync_topmost_group'):
    for node in MF.get(name) or []:
        if u'_scene_topmost_targets_ordered' in body_src(node):
            _use.append(name)
check(u'D11 两个用点都换成了 ordered 版本（换了函数却没接线 = 白写）',
      sorted(_use) == ['_resync_topmost_group', '_set_scene_topmost'],
      u'接线点 %r' % (_use,))
_re = MF.get('_resync_topmost_group') or []
_re_src = body_src(_re[0]) if _re else u''
check(u'D12 ★ 新出现一个 NPC 时能重排整组（`_set_scene_topmost` 是幂等的，'
      u'不再翻转 ⇒ 不补这一手，置顶态里新来的人会被画布盖住）',
      u'HWND_TOPMOST' in _re_src and u'_scene_topmost_on' in _re_src)

# ================================================================ E 一视同仁
print(u'\n=== E 一视同仁（用户口径②）===')
_rimports = []
for node in ast.walk(RTREE):
    if isinstance(node, ast.ImportFrom):
        _base = node.module or u''
        _rimports.append(_base)
        # ★★ 必须连 `from X import Y` 的 **Y** 一起收：只取 `node.module` 的话
        #   `from modules import main` 会被看成"导入了 modules"，**名字 main 整个
        #   漏掉** ⇒ 这条判据换个写法就绕过去了（判据**过窄** = 误报的反面）。
        for a in node.names:
            _rimports.append((_base + u'.' + a.name) if _base else a.name)
    elif isinstance(node, ast.Import):
        for a in node.names:
            _rimports.append(a.name)
_BANNED = ('main', 'scene_camera', 'npc_system', 'scene_render',
           'scene_controller', 'floor_manager')
_bad_imp = [m for m in _rimports
            if m in _BANNED or m.split(u'.')[-1] in _BANNED]
check(u'E1 渲染层**不 import main**（防环；层不认识宿主）',
      u'main' not in [m.split(u'.')[-1] for m in _bad_imp],
      u'imports=%r' % (_rimports,))
check(u'E2 渲染层也不认识相机/场景/地板（只吃算好的屏幕坐标 —— 谁算坐标谁负责）',
      not _bad_imp, u'违规 %r' % (_bad_imp,))
check(u'E3 ★ `ralsei` 在 `no_art` 里、**不在** `characters` 里'
      u'（他由老的 `sprite_label` 画；两边都画就是叠两个他）',
      'ralsei' in NO_ART and 'ralsei' not in CHARS,
      u'no_art=%s / characters=%s'
      % ('ralsei' in NO_ART, 'ralsei' in CHARS))
_it_src2 = _it_src
check(u'E4 ★ 宿主**不按 id 白名单**过滤（谁在场谁就画，不搞特殊人）',
      'ralsei' not in _it_src2 and 'DESKTOP_ALLOWED_IDS' not in _it_src2,
      u'`_npc_body_items` 里没有 ralsei 特判')

# ★★ E5 修过两次，两次都是"恒真"：
#   ① 用 `funcs(RTREE)` 找 `BodyWindow` —— 它是 **ClassDef**，`funcs` 只收
#      FunctionDef ⇒ `_bw_src` 是空串 ⇒ `not in ''` **恒真**（M14 变异抓出来的）。
#   ② 就算改成 ClassDef，类的 **docstring 里**本来就写着「★ 为什么**不**加
#      `WindowStaysOnTopHint`」⇒ 字符串扫盘照样恒真。
#   正解：走 AST 找 `Qt.WindowStaysOnTopHint` 的 **Attribute 节点** —— docstring
#   是 Constant，天然不算。
_cls = {}
for node in ast.walk(RTREE):
    if isinstance(node, ast.ClassDef):
        _cls.setdefault(node.name, []).append(node)
_bw = _cls.get('BodyWindow') or []
_staytop = []
if _bw:
    for node in ast.walk(_bw[0]):
        if isinstance(node, ast.Attribute) and node.attr == 'WindowStaysOnTopHint':
            _staytop.append(node.lineno)
check(u'E5 窗口类里没有 `WindowStaysOnTopHint`（AST 查属性节点，与 C14 互补：'
      u'一个查运行时标志、一个查源码；docstring 里提到它**不算**）',
      bool(_bw) and not _staytop,
      u'类节点 %d 个 / 属性节点 %r' % (len(_bw), _staytop))

# ================================================================ F 自检
print(u'\n=== F 自检 ===')
EXPECT = 69
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
        elif fn in ('write_text', 'dump', 'write'):
            _writes.append(getattr(node, 'lineno', -1))
check(u'F2 本套件只读：AST 里没有写模式的 open / dump / write',
      not _writes, u'可疑行 %r' % (_writes,))

_s = rd(os.path.abspath(__file__))
check(u'F3 PASS / FAIL 标记是字面量（`run_all` 才数得到；此处不回显字面量）',
      u"'[PASS] %s%s'" in _s and u"'[FAIL] %s%s'" in _s,
      u'源码两处都在')

print()
print(u'%d PASS / %d FAIL' % (_n['p'], _n['f']))
if _bad:
    print(u'失败项：')
    for b in _bad:
        print(u'  - %s' % b)
sys.exit(0 if _n['f'] == 0 else 1)
