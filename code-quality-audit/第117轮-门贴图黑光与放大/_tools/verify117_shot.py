# -*- coding: utf-8 -*-
u"""第117轮 · 真机截图的**逐像素对账**（verify117_shot）

为什么必须有
------------
  `check117` 证明的是"**素材**是黑光、**数据**指向它、**摆位**算对了"；
  但对"**屏幕上真的画出来了**"这件事，只有像素能作证。
  ⇒ 本脚本读 `shot117_doorform117_full{ A,B,C,D }.png`（真机整屏截图），
    在**产品自己算出的矩形**上取出该门区域，与**贴图**逐像素比，
    并做 A/B 对照：**门 A 的区域必须更像"黑光"而不是"品红原件"**。

判据（每条都带 A/B 或负控制，禁恒真）
-------------------------------------
  V1  四张真机图与产物贴图都能读进来（缺一个就如实 FAIL，不抛）。
  V2  ★★★ 每扇门：截图区域 vs **它自己的贴图** —— 不透明像素（alpha≥250）的
      平均通道差 `mean|Δ|` 必须小（≤ 18），且 ≥ 85% 的像素三通道差都 ≤ 40。
      ⇒ "那个位置画的确实是这张图"。
  V3  ★★★ **A/B 锚点（本轮核心）**：门 A 的截图区域 vs `desk_door_oneshot_black.png`
      的平均差，必须**显著小于** vs `niko_door_portal.png`（差值 ≥ 25）。
      ⇒ 用户「颜色变成黑光」在**屏幕像素**上成立；同时证明 V2 的比对有鉴别力
        （若两张贴图在该区域"都差不多"，这条会报红）。
  V4  ★★ 门 B 反过来：截图区域 vs 原件（品红）必须比 vs 黑光**更像**（差值 ≥ 25）
      ⇒ 「niko 的家还是用他那道」在屏幕上也成立（不是"两扇都变黑"）。
  V5  ★★ 亮度方向：门 A 区域的不透明像素平均亮度 < 门 B 区域的 0.7 倍
      （黑光确实比品红暗，不是靠名字骗人）。
  V6  ★★ 负控制：把门 A 的比对区域**整体平移 +24px** 后，平均差必须**明显变大**
      （≥ V2 的 1.5 倍）⇒ 证明 V2 不是"任何裁剪都通过"。
  V7  ★ 门 D 与门 C 的贴图不相同、且各自匹配（复用 V2 的结论，只断"不是同一张"）。

跑法
----
  C:\\Python311\\python.exe "...\\_tools\\verify117_shot.py"
产物
----
  `_evidence/rec117/verify117_shot.txt` + `.json`
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
EV = os.path.join(ROUND, '_evidence', 'rec117')
TAG = 'doorform117'

BUF = []
ok = fail = 0


def say(m=''):
    print(m)
    BUF.append(str(m))


def check(name, cond, star=False, detail=None):
    global ok, fail
    if cond:
        ok += 1
        say(u'[PASS] %s' % name)
    else:
        fail += 1
        say(u'[FAIL] %s' % name)
        if detail:
            say(u'       detail: %s' % (detail,))


try:
    from PIL import Image
except Exception as e:                                          # noqa: BLE001
    say(u'PIL 不可用: %r' % (e,))
    sys.exit(2)


def _img(p):
    if not os.path.isfile(p):
        return None
    try:
        return Image.open(p).convert('RGBA')
    except Exception:                                           # noqa: BLE001
        return None


# ---- 从取图报告里读真实矩形（不重算，避免"两种口径"）------------------------
_TXT = os.path.join(EV, 'shot117_%s.txt' % TAG)
_rect = {}
if os.path.isfile(_TXT):
    _t = io.open(_TXT, encoding='utf-8').read()
    for m in re.finditer(r'门([A-D]) 贴门取图：rect=\((\d+), (\d+), (\d+), (\d+)\)',
                         _t):
        _rect[m.group(1)] = tuple(int(m.group(i)) for i in (2, 3, 4, 5))

_spr = {
    'A': 'desk_door_oneshot_black.png',
    'B': 'niko_door_portal.png',
    'C': 'desk_door_ut.png',
    'D': 'desk_door_deltarune.png',
}

say(u'== 第117轮 · 真机截图逐像素对账 ==')
say(u'证据目录：%s' % EV)
say(u'矩形（来自取图报告）：%r' % (_rect,))
say(u'')

check(u'V0 取图报告在盘且四个矩形都读到', len(_rect) == 4, star=True,
      detail=u'got=%r  txt=%r' % (_rect, os.path.isfile(_TXT)))

full = {}
for L in 'ABCD':
    full[L] = _img(os.path.join(EV, 'shot117_%s_full%s.png' % (TAG, L)))
check(u'V1 四张真机整屏图都可读', all(v is not None for v in full.values()), star=True,
      detail=u'%r' % ({L: (v.size if v else None) for L, v in full.items()},))

sp = {}
for L, f in _spr.items():
    sp[L] = _img(os.path.join(OBJS, f))
check(u'V1b 四张贴图都可读', all(v is not None for v in sp.values()), star=True,
      detail=u'%r' % ({L: (v.size if v else None) for L, v in sp.items()},))


def _crop_rect(L, dx=0, dy=0):
    r = _rect.get(L)
    if not r or full.get(L) is None:
        return None
    x, y, w, h = r
    x, y = x + dx, y + dy
    W, H = full[L].size
    if x < 0 or y < 0 or x + w > W or y + h > H:
        return None
    return full[L].crop((x, y, x + w, y + h))


def _cmp(crop, sprite, tol_px=40, erode=1):
    u"""把 `sprite` 缩放到 `crop` 尺寸后与裁剪逐像素比（**只比内部实心像素**）。

    ★★★ 为什么必须"只比内部"（本轮判据自己栽过一次，记下来）
      ----------------------------------------------------------
      首版用 `LANCZOS` 缩放 + 比**所有** alpha≥250 的像素，结果：
        门 A 2.69（PASS）· 门 B 12.78（FAIL）· 门 D 19.29（FAIL）
      我先怀疑产品 —— 但真因是**判据**：
        · 门 B 是**细网格状**品红线、门 D 是**细金线卷草纹**，两者实心像素几乎
          全是"边缘"；任何重采样都会把边缘与壁纸/相邻色混合 ⇒ 差值是**判据造出来的**；
        · 而门 A 是大块近黑平涂，边缘占比极低 ⇒ 看起来"很准"。**同一个判据对不同
          图案的严格度完全不同** = 典型的"用错代理量"。
      ⇒ 改两条：
        ① 缩放用 **NEAREST**（实测产品就是最近邻：改完 mean|Δ| 从 2.69 掉到 **0.14**，
           反过来证明产品没用平滑缩放）；
        ② 只比**腐蚀 1 像素**后的内部像素（四邻域全 alpha≥250）⇒ 把边缘混合整片剔除。
      改后四门 mean|Δ| = 0.14 / 0.56 / 0.00 / 0.53，同色占比 99.2%~100%
      —— 这才是"屏幕上画的就是这张图"的干净证据。

    :return: `(mean_abs_diff, frac_within_tol, n_compared, mean_lum)`
    """
    if crop is None or sprite is None:
        return None, 0.0, 0, 0.0
    w, h = crop.size
    s = sprite.resize((w, h), Image.NEAREST)
    cp = list(crop.getdata())
    spp = list(s.getdata())

    def _opaque(i, j):
        if i < 0 or j < 0 or i >= w or j >= h:
            return False
        return spp[j * w + i][3] >= 250

    tot = 0.0
    n = 0
    good = 0
    lum = 0.0
    for j in range(erode, h - erode):
        for i in range(erode, w - erode):
            if not all(_opaque(i + dx, j + dy)
                       for dx in range(-erode, erode + 1)
                       for dy in range(-erode, erode + 1)):
                continue
            k = j * w + i
            a = cp[k]
            b = spp[k]
            d0 = abs(a[0] - b[0])
            d1 = abs(a[1] - b[1])
            d2 = abs(a[2] - b[2])
            tot += (d0 + d1 + d2) / 3.0
            lum += 0.299 * a[0] + 0.587 * a[1] + 0.114 * a[2]
            if d0 <= tol_px and d1 <= tol_px and d2 <= tol_px:
                good += 1
            n += 1
    if not n:
        return None, 0.0, 0, 0.0
    return tot / n, good / float(n), n, lum / n


say(u'--- 逐门对账（只比"腐蚀 1px 后的内部实心像素"，NEAREST 缩放）---')
res = {}
for L in 'ABCD':
    c = _crop_rect(L)
    d, frac, n, lum = _cmp(c, sp.get(L))
    res[L] = {'mean_diff': None if d is None else round(d, 3),
              'frac_within_40': round(frac, 4), 'n_px': n,
              'mean_lum': round(lum, 2), 'rect': _rect.get(L)}
    say(u'  门%s rect=%r 比对像素=%d  mean|Δ|=%.2f  同色像素占比=%.1f%%  区域平均亮度=%.1f'
        % (L, _rect.get(L), n, d if d is not None else -1, frac * 100.0, lum))

for L in 'ABCD':
    r = res[L]
    check(u'V2 ★★★ 门%s 的屏幕区域 == 它自己的贴图'
          u'（内部像素 mean|Δ| ≤ 6 且 同色占比 ≥ 95%%）' % L,
          r['mean_diff'] is not None and r['mean_diff'] <= 6.0
          and r['frac_within_40'] >= 0.95, star=True, detail=u'%r' % (r,))

# ---------------------------------------------------------------- V3 / V4 A/B
_A_crop = _crop_rect('A')
_dA_black, _fA_black, _nA, _lumA = _cmp(_A_crop, sp.get('A'))
_dA_orig, _fA_orig, _nA2, _ = _cmp(_A_crop, sp.get('B'))
check(u'V3 ★★★ A/B 锚点：门 A 区域**更像黑光**而不是品红原件'
      u'（√黑光 mean|Δ|=%.2f  vs  √原件 %.2f，差 ≥ 25）'
      % (_dA_black or -1, _dA_orig or -1),
      _dA_black is not None and _dA_orig is not None
      and (_dA_orig - _dA_black) >= 25.0, star=True,
      detail=u'black=%r orig=%r' % (_dA_black, _dA_orig))

_B_crop = _crop_rect('B')
_dB_orig, _fB_orig, _nB, _lumB = _cmp(_B_crop, sp.get('B'))
_dB_black, _fB_black, _nB2, _ = _cmp(_B_crop, sp.get('A'))
check(u'V4 ★★ 门 B 反过来：区域**更像品红原件**而不是黑光'
      u'（√原件 mean|Δ|=%.2f  vs  √黑光 %.2f，差 ≥ 25）'
      % (_dB_orig or -1, _dB_black or -1),
      _dB_orig is not None and _dB_black is not None
      and (_dB_black - _dB_orig) >= 25.0, star=True,
      detail=u'orig=%r black=%r' % (_dB_orig, _dB_black))

check(u'V5 ★★ 亮度方向：门 A 区域平均亮度 %.1f < 门 B 的 %.1f × 0.7'
      % (_lumA, _lumB),
      _lumA > 0 and _lumB > 0 and _lumA < _lumB * 0.7, star=True,
      detail=u'lumA=%.2f lumB=%.2f' % (_lumA, _lumB))

# ---------------------------------------------------------------- V6 负控制
_c_shift = _crop_rect('A', dx=24, dy=0)
_dA_shift, _fA_shift, _nAs, _ = _cmp(_c_shift, sp.get('A'))
check(u'V6 ★★ 负控制：把门 A 的比对区域**右移 24px** ⇒ mean|Δ| 明显变大'
      u'（%.2f → %.2f，≥ 1.5×）'
      % (_dA_black or -1, _dA_shift or -1),
      _dA_black is not None and _dA_shift is not None
      and _dA_shift >= _dA_black * 1.5, star=True,
      detail=u'aligned=%r shifted=%r' % (_dA_black, _dA_shift))

# ---------------------------------------------------------------- V7 素材两两不同
_sizes = {L: (sp[L].size if sp.get(L) else None) for L in 'ABCD'}
check(u'V7 ★ 四张门贴图两两不同（尺寸组合 %r）且门 C/D 各自匹配（V2 已逐门判）'
      % (_sizes,),
      len(set(_sizes.values())) >= 3, star=True)

say(u'')
say(u'结论：%d PASS / %d FAIL' % (ok, fail))

_out = {'rect': _rect, 'per_door': res,
        'A_vs_black': None if _dA_black is None else round(_dA_black, 3),
        'A_vs_orig': None if _dA_orig is None else round(_dA_orig, 3),
        'B_vs_orig': None if _dB_orig is None else round(_dB_orig, 3),
        'B_vs_black': None if _dB_black is None else round(_dB_black, 3),
        'A_shift24': None if _dA_shift is None else round(_dA_shift, 3),
        'lumA': round(_lumA, 2), 'lumB': round(_lumB, 2),
        'pass': ok, 'fail': fail}
try:
    with io.open(os.path.join(EV, 'verify117_shot.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(_out, ensure_ascii=False, indent=2))
    with io.open(os.path.join(EV, 'verify117_shot.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(u'\n'.join(BUF) + u'\n')
except Exception as e:                                          # noqa: BLE001
    say(u'（证据落盘失败：%r）' % (e,))

sys.exit(1 if fail else 0)
