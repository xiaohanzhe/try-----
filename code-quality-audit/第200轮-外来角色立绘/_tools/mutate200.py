# -*- coding: utf-8 -*-
"""第200轮 · 变异测试（判据能红吗）

规矩（第198轮定下，照抄不改）
  · 每次只破坏**一个**性质，红数必须 **>0 且 < 总数**（全红＝判据在互相兜，等于没测）
  · 必带一条**无害变异**，它必须红 **0**（否则判据是"任何改动都红"）
  · 改完**按字节还原**并核 sha256 —— 一个字节都不能差

被测物有两块
------------
① `dr/_npc_frames.json`（数据：帧表、尺寸、sha、no_art、理由）
② `dr/<id>/*.png`（磁盘：切出来的帧本身）
只改其中一块，另一块保持真实 —— 这样"清单说 A、磁盘是 B"这类错才真能被抓到。
"""
from __future__ import print_function

import hashlib
import io
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
DR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites', 'dr')
MAN = os.path.join(DR, '_npc_frames.json')
CHECK = os.path.join(HERE, 'check200.py')
PY = r'C:\Python311\python.exe'

SUM_RE = re.compile(r'(\d+)\s+PASS\s*/\s*(\d+)\s+FAIL')
_p = {'n': 0, 'ok': 0}


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def wr(p, b):
    tmp = p + '.mut.tmp'
    with open(tmp, 'wb') as f:
        f.write(b)
    os.replace(tmp, p)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run_check():
    r = subprocess.run([PY, CHECK], capture_output=True)
    out = (r.stdout or b'').decode('utf-8', 'replace')
    m = SUM_RE.search(out)
    if not m:
        return None, out
    return (int(m.group(1)), int(m.group(2))), out


def mut_json(fn):
    """在清单上做一处改动，返回 (路径, 原字节, 新字节)。"""
    orig = rd(MAN)
    d = json.loads(orig.decode('utf-8'))
    fn(d)
    txt = json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + u'\n'
    return MAN, orig, txt.encode('utf-8')


# ---------------------------------------------------------------- 变异
def m_orphan_frame(d):
    """把一个帧改成清单里没有对应文件的名字 ⇒ C3 双向对账 / C2 序号必须红。"""
    rows = d['characters']['ut_sans']['frames']['down']
    rows[-1]['f'] = 'down_9.png'


def m_drop_sha(d):
    """删掉一条帧记录的 sha256 ⇒ F2 四件套必须红。"""
    d['characters']['ot_sans']['frames']['down'][0].pop('sha256')


def m_shepherd_left(d):
    """给 `os_shepherd` 补一个 left 方向 ⇒ E1（只许 down）必须红。

    ★ 这是本轮最容易犯的错：那张表第 1~3 行是**羊**，谁"手滑补齐"就会把羊当人画。
    """
    fr = d['characters']['os_shepherd']['frames']
    src = fr['down'][0]
    fr['left'] = [dict(src, f='left_0.png')]


def m_niko_up_down():
    """把 `dr/os_niko/up_0.png` 换成原表**第 0 行**（有脸那行）的内容
    ⇒ E3（背面 = 第 3 行）必须红。

    ★ 第一版只改清单不动文件 ⇒ E3 拿**磁盘像素**比对，认不出清单被改
      —— 变异红 0，等于这条判据没被测到。改文件才是"真的把行序搞反"。
    """
    from PIL import Image
    dst = os.path.join(DR, 'os_niko', 'up_0.png')
    orig = rd(dst)
    src = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites', 'os', 'niko.png')
    CW, CH = Image.open(dst).size
    im = Image.open(src).convert('RGBA')
    buf = io.BytesIO()
    im.crop((0, 0, CW, CH)).save(buf, format='PNG')
    return dst, orig, buf.getvalue()


def m_gaster_back(d):
    """把 `ut_gaster` 塞回 characters（只有弹幕骷髅头）⇒ D1 必须红。"""
    d['characters']['ut_gaster'] = {'kind': 'stand', 'frames': {}}


def m_src_leak(d):
    """给一条帧记录塞施工期字段 `src` ⇒ F1 必须红。"""
    d['characters']['hy_ace']['frames']['down'][0]['src'] = 'D:/somewhere.png'


def m_size_jitter(d):
    """把某一帧的 w 改大 1 ⇒ C4（同方向尺寸一致）必须红。"""
    rows = d['characters']['hy_mooch']['frames']['down']
    rows[1]['w'] = rows[1]['w'] + 1


def m_drop_noart_reason(d):
    """删掉一个人的"没有立绘"理由 ⇒ A5 必须红。"""
    d['no_art_reason'].pop('hy_bowll', None)


def m_frisk_back(d):
    """把 `ut_frisk` 从 no_art 里拿掉 ⇒ D2 必须红（只有女性版素材）。"""
    d['no_art'] = [x for x in d['no_art'] if x != 'ut_frisk']


def m_dup_seq(d):
    """把某方向两个帧的序号改成同一个 ⇒ C2（0 起连续）必须红。"""
    rows = d['characters']['ut_papyrus']['frames']['down']
    rows[2]['f'] = rows[1]['f']


def m_harmless(d):
    """无害变异：只改清单里的说明文字 ⇒ 必须红 0。

    ★ 这条是**负控制**：证明上面那一堆判据不是在"只要文件变了就红"。
    """
    d['how'] = d['how'] + u'（无害变异：只动说明文字）'


# ---- 动磁盘的两个（改清单抓不到，必须改文件才叫"真的换了一个人"）----
def m_chara_to_female():
    """把 `dr/ut_chara/down_0.png` 换成女性版主角 ⇒ D3/D4 必须红。"""
    dst = os.path.join(DR, 'ut_chara', 'down_0.png')
    src = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites', 'ut',
                       'spr_f_maincharad_0.png')
    orig = rd(dst)
    return dst, orig, rd(src)


def m_drop_old_frame():
    """删掉原班一帧 ⇒ B2/B3（原班冻结）必须红。"""
    dst = os.path.join(DR, 'kris', 'down_0.png')
    orig = rd(dst)
    return dst, orig, b''          # 空文件：既"还在"又 sha 不符 ⇒ 只 B2 红


MUTANTS = [
    ('M1 孤儿帧名', m_orphan_frame),
    ('M2 删掉 sha256', m_drop_sha),
    ('M3 shepherd 补 left', m_shepherd_left),
    ('M4 niko up=第0行', m_niko_up_down),
    ('M5 gaster 塞回清单', m_gaster_back),
    ('M6 帧记录漏 src 字段', m_src_leak),
    ('M7 同方向尺寸不一', m_size_jitter),
    ('M8 删掉一条"没有"的理由', m_drop_noart_reason),
    ('M9 frisk 从 no_art 拿掉', m_frisk_back),
    ('M10 两帧序号撞车', m_dup_seq),
    ('M11 chara 换成女性版', m_chara_to_female),
    ('M12 原班帧被清空', m_drop_old_frame),
    ('M13 无害（只改说明文字）', m_harmless),
]


def main():
    base, out = run_check()
    if base is None:
        print('[失败] 基线跑不起来：\n%s' % out[-800:])
        return 2
    tot = base[0] + base[1]
    print('基线：PASS=%d FAIL=%d（总数 %d）' % (base[0], base[1], tot))
    if base[1] != 0:
        print('[失败] 基线不是全绿，先修基线')
        return 2

    bad = []
    for name, fn in MUTANTS:
        try:
            # 按**形参个数**分派：无参 = 直接改磁盘文件；带 `d` = 改清单
            if fn.__code__.co_argcount == 0:
                p, orig, mut = fn()
            else:
                p, orig, mut = mut_json(fn)
        except Exception as e:                       # noqa: BLE001
            print('[失败] %-26s 变异构造失败：%s' % (name, e))
            bad.append(name)
            continue
        h0 = sha(orig)
        wr(p, mut)
        try:
            got, _o = run_check()
        finally:
            wr(p, orig)
        if got is None:
            print('[失败] %-26s 变异后判据跑不起来' % name)
            bad.append(name)
            continue
        if sha(rd(p)) != h0:
            print('[严重] %-26s 还原后 sha 不一致！' % name)
            bad.append(name)
            continue
        nf = got[1]
        good = (nf == 0) if '无害' in name else (0 < nf < tot)
        _p['n'] += 1
        _p['ok'] += 1 if good else 0
        if not good:
            bad.append(name)
        print('%s %-26s 红数 %d %s' % ('[ok]' if good else '[NG]', name, nf,
                                      '（无害变异应红 0）' if '无害' in name else ''))

    print('\n=== 结论 ===')
    print('变异 %d/%d 达到预期' % (_p['ok'], _p['n']))
    if bad:
        print('未达标：%s' % bad)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
