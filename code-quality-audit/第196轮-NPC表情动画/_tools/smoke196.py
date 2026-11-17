# -*- coding: utf-8 -*-
"""第196轮 · 冒烟：NPC 表情动画真的能在**他自己那个窗口**里播出来吗。

不构造 `RalseiPet()`（那要起整台机器）；只用 offscreen `QApplication` + 真窗口，
把"开演 → 帧变 → 演完回站姿"整条链路走一遍。

★ 为什么要"看帧变了"而不是"看 play_once 返回 True"：返回 True 只证明状态位写了，
  真正的契约是**屏幕上那一格换了图**。第191轮踩过"`grab()` 能看见、屏幕看不见"。
"""
import io
import json
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)
sys.path.insert(0, os.path.join(PET, 'src'))

from PyQt5.QtWidgets import QApplication          # noqa: E402
from modules import npc_body_render as R          # noqa: E402

_n = {'p': 0, 'f': 0}


def check(name, ok, extra=''):
    if ok:
        _n['p'] += 1
        print('[PASS] %s%s' % (name, ('  ‹%s›' % extra) if extra else ''))
    else:
        _n['f'] += 1
        print('[FAIL] %s%s' % (name, ('  ‹%s›' % extra) if extra else ''))


def _bits(win):
    """窗口当前那张图的像素字节（用于"真的换了图"这种断言）。"""
    pm = None if win is None else win.pixmap()
    if pm is None:
        return b''
    im = pm.toImage()
    return bytes(im.bits().asstring(im.byteCount()))


def main():
    app = QApplication.instance() or QApplication([])
    book = R.NpcFrameBook(root=PET)
    layer = R.NpcBodyLayer(book=book)

    # ---- A 清单 ----
    print('\n=== A 清单 ===')
    man = R.load_anims(PET)
    chars = man.get('characters') or {}
    check('A1 表情动画清单读出来了', bool(chars), '%d 人' % len(chars))
    check('A2 susie 有 happy/sad/angry/surprised 四类',
          set(['happy', 'sad', 'angry', 'surprised']) <= set(book.anim_classes('susie')),
          ','.join(book.anim_classes('susie')))
    check('A3 没有素材的人 anim_classes 为空（不演，不借别人身体）',
          book.anim_classes('addison_tea') == [],
          repr(book.anim_classes('addison_tea')))
    check('A4 清单里每一帧文件都在盘上',
          all(os.path.isfile(os.path.join(PET, 'assets', 'sprites', 'dr', cid,
                                          row['f']))
              for cid, e in chars.items()
              for cls, ds in e.items()
              for dd, rows in ds.items() for row in rows),
          '共 %d 帧' % sum(len(rows) for e in chars.values()
                          for ds in e.values() for rows in ds.values()))

    # ---- B 情绪键解析 ----
    print('\n=== B 情绪键 → 五类 ===')
    check('B1 laugh 归 happy', R.EMOTION_CLASS.get('laugh') == 'happy')
    check('B2 cry 归 sad（NPC 没有 cry 素材）', R.EMOTION_CLASS.get('cry') == 'sad')
    check('B3 smile 故意不映射（微笑不该放大笑）', 'smile' not in R.EMOTION_CLASS)

    # ---- C 行为：真窗口 ----
    print('\n=== C 行为 ===')
    item = {'id': 'susie', 'x': 300.0, 'y': 300.0, 'facing': 'down',
            'moving': False}
    t0 = 1000000
    layer.sync([item], scale=2.0, now_ms=t0, anchor='foot')
    win = layer.window_of('susie')
    check('C1 先站定：窗口建起来了', win is not None and win.isVisible())
    base_size = None if win is None else (win.width(), win.height())
    base_bits = _bits(win)

    ok = layer.play_once('susie', 'laugh', now_ms=t0 + 10)
    check('C2 play_once 接受原始情绪键 laugh', ok is True)
    layer.sync([item], scale=2.0, now_ms=t0 + 20, anchor='foot')
    a_size = (win.width(), win.height())
    # ★ 比**像素**而不是比尺寸：尺寸只差 2px 也可能"图没换"，那不算真演了
    check('C3 开演后**屏幕那一格真的换了图**',
          _bits(win) != base_bits, '尺寸 %r → %r' % (base_size, a_size))

    # 逐帧走完：四帧必须给出**四个不同的画面**（否则是"闪一下"不是"一段动作"）
    shots = []
    for dt in (20, 140, 260, 380):
        layer.sync([item], scale=2.0, now_ms=t0 + dt, anchor='foot')
        st = layer.oneshot_of('susie')
        shots.append((st['emo'] if st else None, _bits(win)))
    check('C4 演的过程中状态一直是 happy(laugh)',
          [s[0] for s in shots] == ['happy'] * 4, repr([s[0] for s in shots]))
    check('C7 四个时间点给出四个不同画面（真在播，不是卡一格）',
          len(set(s[1] for s in shots)) == 4,
          '不同画面 %d 个' % len(set(s[1] for s in shots)))

    # 演完（4 帧 × 120 + 350 hold = 830ms）
    layer.sync([item], scale=2.0, now_ms=t0 + 10 + 830 + 50, anchor='foot')
    check('C5 到点自动清状态（不会卡在表情上）',
          layer.oneshot_of('susie') is None)
    b_size = (win.width(), win.height())
    check('C6 演完回到站姿那一格', b_size == base_size,
          '%r == %r' % (b_size, base_size))

    # ---- D 拒绝路径 ----
    print('\n=== D 拒绝路径（这些必须是真的什么都没做）===')
    check('D1 没素材的人 play_once ⇒ False', layer.play_once('addison_tea', 'laugh') is False)
    check('D1b 而且**没有**留下任何演出状态', layer.oneshot_of('addison_tea') is None)
    check('D2 没有该情绪的人 ⇒ False', layer.play_once('susie', 'hurt') is False)
    check('D2b 也不留状态', layer.oneshot_of('susie') is None)
    check('D3 空 id ⇒ False', layer.play_once('', 'laugh') is False)
    check('D4 不越权：别人的情绪不会借用 susie 的帧',
          layer.play_once('lancer', 'happy') is True
          and layer.oneshot_of('lancer')['emo'] == 'happy')
    check('D4b susie 那边没被顺手点亮', layer.oneshot_of('susie') is None)

    # ---- E 性能 ----
    print('\n=== E 性能 ===')
    import time
    t = time.time()
    for i in range(200):
        for cid in ('susie', 'noelle', 'toriel'):
            b = book.anim_scaled(cid, 'sad', 'down', i % 4, 2.0)
    dt = time.time() - t
    check('E1 600 次取帧 < 0.5s（有缓存）', dt < 0.5, '耗时 %.3fs' % dt)
    check('E2 缩放缓存没有无限膨胀',
          len(book._anim_scaled_cache) < 1200,
          '%d 项' % len(book._anim_scaled_cache))

    # ---- F 自检 ----
    print('\n=== F 自检 ===')
    src = io.open(os.path.abspath(R.__file__), 'r', encoding='utf-8').read()
    check('F1 渲染层里没有任何作者写死的 Ralsei 帧名',
          'spr_ralsei' not in src)
    check('F2 一次性动画有 HOLD（末帧不会一闪而过）',
          R.ANIM_HOLD_MS >= 200, 'HOLD=%dms' % R.ANIM_HOLD_MS)

    print('\nPASS=%d FAIL=%d' % (_n['p'], _n['f']))
    return 0 if _n['f'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
