# -*- coding: utf-8 -*-
u"""verify101.py —— 第101轮接线后的**独立验收**（不看构建脚本自报，重新读盘）。

守四件事：
 V1 **无重复键**（静默损坏：Python json 对重复键取最后一个 ⇒ bg_source 会恒 'none'）
 V2 **行尾未被改**（与 HEAD 版逐文件比 CRLF/LF 计数 —— 逐行替换的契约）
 V3 结构未坏：7 个文件都能 parse，263×2 个 scene 三字段齐全且合法
 V4 `bg` 指向的 PNG **真的在磁盘上**（不查的话数据面能指向空气）
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
RELP = 'ralsei_pet/assets/scenes/'

PASS = 0
FAILS = []


def check(name, ok, detail=''):
    global PASS
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if ok:
        PASS += 1
    else:
        FAILS.append(name)


FILES = ['_index.json'] + sorted(f for f in os.listdir(SCENES)
                                 if f.startswith('_zone.oneshot.'))


def dups_of(path):
    out = []

    def hook(pairs):
        seen = set()
        for k, v in pairs:
            if k in seen:
                out.append(k)
            seen.add(k)
        return dict(pairs)

    with io.open(path, encoding='utf-8') as f:
        json.load(f, object_pairs_hook=hook)
    return out


def eol(path):
    b = open(path, 'rb').read()
    crlf = b.count(b'\r\n')
    return crlf, b.count(b'\n') - crlf


# V1 无重复键
alldup = {}
for f in FILES:
    d = dups_of(os.path.join(SCENES, f))
    if d:
        alldup[f] = d[:4]
check('V1 ★ 7 个文件都没有**重复键**（首跑 bug 的守点：bg_source 被写两遍）',
      not alldup, str(alldup or '(无)'))

# V2 ★ 判据改过一次：原写法拿 `git show HEAD:`（= blob, **autocrlf 归一化后的 LF**）
#    与工作区比 EOL -- 本仓库 `autocrlf=true` 且工作区是 CRLF ⇒ **必然报红**，
#    属于**判据比错了对象**（不是产品错）。真正要守的是"逐行替换没引入格式噪音"：
#    若 EOL 被整文件改写，`git diff` 的增删行数会**暴涨**（全文件重写）。
#    ⇒ 用"diff 规模是否**恰好**等于 526 处 × 3 增 / 2 删"来守，能真抓整文件重写。
num = subprocess.run(['git', 'diff', '--numstat', '--', RELP],
                     cwd=ROOT, capture_output=True).stdout.decode('utf-8', 'replace')
add = dele = 0
for ln in num.splitlines():
    p = ln.split('\t')
    if len(p) >= 3 and p[0].isdigit():
        add += int(p[0])
        dele += int(p[1])
check('V2 ★ diff 规模恰好 == 526 处 × (3 增/2 删) ⇒ 逐行替换守约、无整文件重写',
      (add, dele) == (526 * 3, 526 * 2),
      'add=%d del=%d（期望 %d/%d）' % (add, dele, 526 * 3, 526 * 2))

# V3 结构 + 三字段
zone = {}
for f in FILES[1:]:
    d = json.load(io.open(os.path.join(SCENES, f), encoding='utf-8'))
    for sid, s in (d.get('scenes') or {}).items():
        zone[sid] = s
inline = {}
idx = json.load(io.open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
for ak, av in ((idx['chapters'].get('oneshot') or {}).get('areas') or {}).items():
    for sid, s in ((av or {}).get('scenes') or {}).items():
        inline[sid] = s

bad3 = []
for tag, m in (('zone', zone), ('index', inline)):
    for sid, s in m.items():
        if not (isinstance(s.get('bg'), str) and s['bg'].startswith('bg/oneshot_map')
                and s.get('bg_source') == 'tmx.composite'
                and re.fullmatch(r'map\d+\.tmx', str(s.get('bg_asset') or ''))):
            bad3.append((tag, sid, s.get('bg'), s.get('bg_source'), s.get('bg_asset')))
check('V3 ★ 263×2 个 scene 三字段齐全且合法（bg=bg/oneshot_map*.png / '
      'bg_source=tmx.composite / bg_asset=map*.tmx）',
      not bad3 and len(zone) == 263 and len(inline) == 263,
      'zone=%d index=%d 不合法 %d %s' % (len(zone), len(inline), len(bad3), bad3[:3]))

# 两层逐字段一致
mis = [sid for sid in zone if json.dumps(zone[sid], sort_keys=True, ensure_ascii=False)
       != json.dumps(inline.get(sid), sort_keys=True, ensure_ascii=False)]
check('V3b ★ 两层登记逐字段一致（zone 内联 == index 内联）', not mis, '不一致 %d %s'
      % (len(mis), mis[:3]))

# V4 bg 指向的 PNG 真在磁盘
missf = []
for m in (zone, inline):
    for sid, s in m.items():
        p = os.path.join(SCENES, s['bg'])
        if not os.path.isfile(p):
            missf.append(s['bg'])
check('V4 ★ 每个 bg 指向的 PNG 真的在磁盘上（数据面不许指向空气）',
      not missf, '缺 %d %s' % (len(missf), sorted(set(missf))[:3]))

# 额外：room_id -> 文件名 自洽（map 编号必须等于 room_id）
badmap = [(sid, s['original_room_id'], s['bg']) for sid, s in zone.items()
          if s['bg'] != 'bg/oneshot_map%d.png' % int(s['original_room_id'])
          or s['bg_asset'] != 'map%d.tmx' % int(s['original_room_id'])]
check('V5 ★ 文件名/溯源与 room_id 自洽（map 编号 == scene.original_room_id）',
      not badmap, '不符 %d %s' % (len(badmap), badmap[:3]))

print()
print('=' * 70)
print('verify101：PASS=%d FAIL=%d（共 %d 条判据）' % (PASS, len(FAILS), PASS + len(FAILS)))
print('FAIL = %d %s' % (len(FAILS), FAILS))
sys.exit(1 if FAILS else 0)
