# -*- coding: utf-8 -*-
"""第200轮回归锁 · **外来角色立绘**（54 人上桌，8 人如实登记"没有"）

用户口径
--------
    「都行，还是那句话，mac电脑记得用」
    「素材，还是那句话，从咱游戏的源文件里找」
    「(找不到的) 参考原作……要么原作里有其他移动方式要么就是不动」

它守什么
--------
A 清单/映射表对账 —— 映射表 54 人**全都在**清单里；`no_art` 与 `characters` 不相交；
                    每个"没有立绘"都**带理由**（不是干瘪一串 id）
B 原班冻结       —— dr 原班 18 人 146 帧的 sha256 **逐条未变**（对照开工前的冻结快照）
C 命名/帧序      —— 帧文件一律 `<dir>_<i>.png`、序号 0 起连续、目录无散图、
                    同一方向各帧**尺寸一致**（否则脚底会一跳一跳）
D 三条"看着像其实不是" —— gaster（只有弹幕骷髅头）/ mettaton（只有盒子形态）/
                    bowll（只有没有眼睛的碗身）都不许进 `characters`
E 两处易错裁定   —— `ut_chara` 取 `spr_chara*` 而**不是** `spr_f_mainchar*`
                    （黄发紫条纹衫 = 女性版主角，不是 Chara）
F OneShot 格子   —— 只取有脸的那一行当 down、最后一行当 up；
                    `os_shepherd` 只取第 0 行（第 1~3 行是羊）
G 自检           —— 判据条数 / 判据名不带计数标记 / 无恒真判据

★ 为什么"原班冻结"要用开工前的快照而不是 `git show HEAD`：
  提交之后再跑，`HEAD` 已经是新版 ⇒ 拿新比新 = **恒真判据**（第171轮那条纪律）。
  快照 `_evidence/dr18_before200.json` 是**开工前**从 HEAD 取下来冻住的，提交不会改它。
"""
from __future__ import print_function

import ast
import hashlib
import io
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SPR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites')
DR = os.path.join(SPR, 'dr')
MANIFEST = os.path.join(DR, '_npc_frames.json')
SNAP = os.path.join(ROUND, '_evidence', 'dr18_before200.json')
sys.path.insert(0, HERE)

import pick200 as P             # noqa: E402

_n = {'p': 0, 'f': 0}
DIRS = ('down', 'left', 'right', 'up')


def check(name, ok, extra=u''):
    if ok:
        _n['p'] += 1
        print('[PASS] %s' % name)
    else:
        _n['f'] += 1
        print('[FAIL] %s' % name)
    if extra:
        print('       %s' % extra)


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def sha_file(p):
    return hashlib.sha256(rd(p)).hexdigest()


def pixels(p):
    """解码后的**像素数据**（不比文件字节：PNG 重新编码本来就允许不同）。"""
    from PIL import Image
    im = Image.open(p).convert('RGBA')
    return (im.size, im.tobytes())


MAN = json.loads(rd(MANIFEST).decode('utf-8'))
CHARS = MAN.get('characters') or {}
NO_ART = list(MAN.get('no_art') or [])
REASON = MAN.get('no_art_reason') or {}
SNAPJ = json.loads(rd(SNAP).decode('utf-8'))
OLD_IDS = list(SNAPJ['ids'])
OLD_SHA = SNAPJ['sha']
NEW_IDS = sorted(set(CHARS) - set(OLD_IDS))
MAXFD = int(MAN.get('max_frames_per_dir') or 4)

# ================================================================ A 对账
check('A1 清单 schema 是 v1（第200轮只加人，不改结构）',
      MAN.get('schema_version') == 1, 'schema=%r' % (MAN.get('schema_version'),))

check('A2 本轮新增恰好 54 人（映射表条目数）',
      len(NEW_IDS) == 54 and len(P.MAP) == 54,
      '清单新增=%d 映射表=%d' % (len(NEW_IDS), len(P.MAP)))

_missing = sorted(set(P.MAP) - set(CHARS))
check('A3 映射表里每一条都真的进了清单（不存在"表里有、清单没有"）',
      not _missing, '缺 %r' % (_missing[:5],))

check('A4 映射表与 `no_art` 不相交（同一个人不能既"有图"又"没图"）',
      not (set(P.MAP) & set(NO_ART)), '交集 %r' % sorted(set(P.MAP) & set(NO_ART)))

_no_reason = sorted(k for k in P.NO_ART if not (REASON.get(k) or u'').strip())
check('A5 ★ 每个"没有立绘"的人都带一句**理由**（不是干瘪一串 id）',
      not _no_reason, '缺理由 %r' % (_no_reason[:5],))

check('A6 本轮登记为"没有"的 8 人，全在清单 `no_art` 里',
      set(P.NO_ART) <= set(NO_ART),
      '漏登 %r' % sorted(set(P.NO_ART) - set(NO_ART)))

_bad_cnt = []
for nid in NEW_IDS:
    for d, rows in (CHARS[nid].get('frames') or {}).items():
        if not (1 <= len(rows) <= MAXFD):
            _bad_cnt.append('%s/%s=%d' % (nid, d, len(rows)))
check('A7 新增每方向帧数在 1..max_frames_per_dir 之间',
      not _bad_cnt, 'max=%d 越界 %r' % (MAXFD, _bad_cnt[:3]))

# ================================================================ B 原班冻结
_gone = sorted(set(OLD_IDS) - set(CHARS))
check('B1 dr 原班 18 人一个都没被删', not _gone, '缺 %r' % (_gone,))

_changed, _lost = [], []
for key, sha in OLD_SHA.items():
    nid, fn = key.split('/', 1)
    p = os.path.join(DR, nid, fn)
    if not os.path.isfile(p):
        _lost.append(key)
    elif sha_file(p) != sha:
        _changed.append(key)
check('B2 ★ 原班 146 帧的 sha256 **逐条未变**（第200轮只许新增）',
      not _changed, '变了 %d 帧 %r' % (len(_changed), _changed[:3]))
check('B3 原班 146 帧的文件都还在磁盘上', not _lost,
      '丢了 %d %r' % (len(_lost), _lost[:3]))

# ================================================================ C 命名与帧序
_bad_name, _bad_seq, _orphan = [], [], []
for nid in NEW_IDS:
    d = os.path.join(DR, nid)
    # ★ 目录不在 ⇒ 记一笔就走，**不许抛异常**：判据要"红"，不能"崩"
    #   （崩了 run_all 只看到"跑不起来"，红数反而无法计入）
    if not os.path.isdir(d):
        _orphan.append('%s 没有目录' % nid)
        continue
    listed = set()
    for dr, rows in (CHARS[nid].get('frames') or {}).items():
        idxs = []
        for row in rows:
            fn = row.get('f') or u''
            listed.add(fn)
            base, ext = os.path.splitext(fn)
            want = u'%s_' % dr
            if ext != '.png' or not base.startswith(want):
                _bad_name.append('%s/%s' % (nid, fn))
                continue
            tail = base[len(want):]
            if not tail.isdigit():
                _bad_name.append('%s/%s' % (nid, fn))
                continue
            idxs.append(int(tail))
        if idxs != list(range(len(idxs))):
            _bad_seq.append('%s/%s=%r' % (nid, dr, idxs))
    have = set(f for f in os.listdir(d) if f.lower().endswith('.png'))
    if have != listed:
        _orphan.append('%s 多 %r 少 %r'
                       % (nid, sorted(have - listed)[:2], sorted(listed - have)[:2]))

check('C1 新增帧文件一律归一化成 `<方向>_<序号>.png`', not _bad_name,
      '%d 处 %r' % (len(_bad_name), _bad_name[:3]))
check('C2 每个方向的序号从 0 起**连续**（渲染层按下标取帧，跳号会取错人）',
      not _bad_seq, '%r' % (_bad_seq[:3],))
check('C3 目录与清单双向对账（防"复制了但没登记" / "登记了但文件不在"）',
      not _orphan, '%r' % (_orphan[:2],))

_jitter = []
for nid in NEW_IDS:
    for dr, rows in (CHARS[nid].get('frames') or {}).items():
        sz = set((r.get('w'), r.get('h')) for r in rows)
        if len(sz) > 1:
            _jitter.append('%s/%s=%r' % (nid, dr, sorted(sz)))
check('C4 ★ 同一角色同一方向各帧**尺寸一致**（不一致 = 脚底一跳一跳）',
      not _jitter, '%r' % (_jitter[:3],))

# ================================================================ D 三条"看着像其实不是"
NOT_BODY = ('ut_gaster', 'ut_mettaton', 'hy_bowll')
_in_chars = [k for k in NOT_BODY if k in CHARS]
check('D1 ★ 只有弹幕骷髅头/盒子形态/空碗身的三个人，**没有**被登记成有立绘',
      not _in_chars, '误登 %r' % (_in_chars,))
check('D2 `ut_frisk` 未登记（仓库只有女性版主角素材，选它 = 替角色定性别）',
      'ut_frisk' not in CHARS and 'ut_frisk' in NO_ART,
      'in_chars=%s in_no_art=%s' % ('ut_frisk' in CHARS, 'ut_frisk' in NO_ART))

_chara_p = os.path.join(DR, 'ut_chara', 'down_0.png')
_src_chara = os.path.join(SPR, 'ut', 'spr_charad_0.png')
_src_fem = os.path.join(SPR, 'ut', 'spr_f_maincharad_0.png')
check('D3 ★ `ut_chara` 的 down 帧就是 `spr_charad_0.png`（Chara 本族）',
      os.path.isfile(_chara_p) and os.path.isfile(_src_chara)
      and sha_file(_chara_p) == sha_file(_src_chara),
      'sha 相同=%s' % (os.path.isfile(_chara_p)
                       and sha_file(_chara_p) == sha_file(_src_chara)))
check('D4 负控制：它**不是** `spr_f_maincharad_0.png`（黄发紫条纹衫的女性主角）',
      os.path.isfile(_src_fem) and sha_file(_chara_p) != sha_file(_src_fem),
      '与女性版不同=%s' % (sha_file(_chara_p) != sha_file(_src_fem)))

# ---- D5/D6：`knight` 是**设定层面**不该出现，不是"缺素材" ----
# ★★★ 用户 2026-11-19：「三角符文里**不用出现 knight**，他是目前没有定性的反派」。
#    这两条钉的是"以后别顺手补上"：盘上真有 `spr_roaringknight_*`，
#    下一个人（或下一轮的我）翻到就很容易觉得"这不是有素材吗"。
_kn_reason = REASON.get('knight') or u''
check('D5 ★ `knight` 不登记立绘，且理由是"设定上不出现"（不是"缺素材"）',
      'knight' not in CHARS and 'knight' in NO_ART
      and (u'不出现' in _kn_reason or u'未定性' in _kn_reason),
      'in_chars=%s in_no_art=%s 理由命中=%s'
      % ('knight' in CHARS, 'knight' in NO_ART,
         (u'不出现' in _kn_reason or u'未定性' in _kn_reason)))

_pl_path = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_placement.json')
_pl = json.loads(rd(_pl_path).decode('utf-8'))
_kn_scene = [p for p in (_pl.get('placement') or [])
             if p.get('id') == 'knight' and p.get('scene')]
_kn_desk = 'knight' in ((_pl.get('desktop') or {}).get('allowed') or [])
check('D6 ★ `knight` 也没有任何场景站位、不在桌面名单（三重不出现）',
      not _kn_scene and not _kn_desk,
      '有场景=%d 在桌面名单=%s' % (len(_kn_scene), _kn_desk))

# ================================================================ E OneShot 行序
def _cell(fn, cw, ch, r, c):
    from PIL import Image
    im = Image.open(os.path.join(SPR, 'os', fn)).convert('RGBA')
    return im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))


_sh = sorted((CHARS.get('os_shepherd') or {}).get('frames') or {})
check('E1 ★ `os_shepherd` 只登记 down（那张表的第 1~3 行是**羊**，不是他）',
      _sh == ['down'], '方向=%r' % (_sh,))

_nk_d = os.path.join(DR, 'os_niko', 'down_0.png')
_nk_u = os.path.join(DR, 'os_niko', 'up_0.png')
check('E2 ★ `os_niko` down_0 == 原表**第 0 行**第 0 格（有脸那一行）',
      os.path.isfile(_nk_d)
      and pixels(_nk_d) == (tuple(_cell('niko.png', 24, 32, 0, 0).size),
                            _cell('niko.png', 24, 32, 0, 0).tobytes()),
      '逐像素相同')
check('E3 ★ `os_niko` up_0 == 原表**第 3 行**第 0 格（背面那一行，行序没搞反）',
      os.path.isfile(_nk_u)
      and pixels(_nk_u) == (tuple(_cell('niko.png', 24, 32, 3, 0).size),
                            _cell('niko.png', 24, 32, 3, 0).tobytes()),
      '逐像素相同')

check('E4 `os_watcher` 只登记 down（那张表只有第 0 行有内容）',
      sorted((CHARS.get('os_watcher') or {}).get('frames') or {}) == ['down'],
      '方向=%r' % (sorted((CHARS.get('os_watcher') or {}).get('frames') or {}),))

_one = {k: CHARS[k]['frames'] for k in ('os_magpie', 'os_mason', 'ut_napstablook')
        if k in CHARS}
_bad_one = [k for k, fr in _one.items()
            if len(fr) != 4 or any(len(v) != 1 for v in fr.values())]
check('E5 "四方向各 1 帧"的三个人没有被塞成多帧（表里就那一格）',
      not _bad_one, '异常 %r' % (_bad_one,))

# ================================================================ F 清单洁净
_bad_abs, _bad_key, _bad_row = [], [], []
for nid in NEW_IDS:
    for dr, rows in (CHARS[nid].get('frames') or {}).items():
        for row in rows:
            for k in ('src', 'cut'):
                if k in row:
                    _bad_key.append('%s/%s:%s' % (nid, dr, k))
            for k in ('w', 'h', 'sha256', 'f'):
                if k not in row:
                    _bad_row.append('%s/%s 缺 %s' % (nid, dr, k))
            f = row.get('f') or u''
            if f.startswith('/') or (len(f) > 1 and f[1] == ':'):
                _bad_abs.append('%s/%s' % (nid, f))
check('F1 帧条目里没有 `src`/`cut` 这类施工期字段（清单只留运行时需要的）',
      not _bad_key, '%r' % (_bad_key[:3],))
check('F2 每条帧记录都带 `f`/`w`/`h`/`sha256` 四件套',
      not _bad_row, '%r' % (_bad_row[:3],))
check('F3 帧文件名里没有绝对路径（运行时不许依赖外部盘）',
      not _bad_abs, '%r' % (_bad_abs[:3],))

# ================================================================ G 自检
_src = rd(os.path.abspath(__file__)).decode('utf-8')
_tree = ast.parse(_src)
_calls = [n for n in ast.walk(_tree)
          if isinstance(n, ast.Call) and getattr(n.func, 'id', u'') == 'check']
_names = [c.args[0].value for c in _calls
          if c.args and isinstance(c.args[0], ast.Constant)
          and isinstance(c.args[0].value, str)]
check('G1 判据名里没有自带的计数标记（防污染 run_all 计数）',
      bool(_names) and len(_names) == len(_calls)
      and not any('[PASS]' in x or '[FAIL]' in x for x in _names),
      '判据名=%d 命中=%d' % (len(_names), len(_calls)))

_trivial = [c for c in _calls
            if len(c.args) > 1 and isinstance(c.args[1], ast.Constant)
            and c.args[1].value is True]
check('G2 无恒真判据（第二实参不许是字面量 True）',
      not _trivial, 'check()=%d 恒真=%d' % (len(_calls), len(_trivial)))

check('G3 判据条数经 check() 记账（加判据时同步改这里）', len(_calls) == 31,
      'check()=%d' % len(_calls))

print('\n' + '=' * 70)
print('check200  结论：%d PASS / %d FAIL' % (_n['p'], _n['f']))
sys.exit(1 if _n['f'] else 0)
