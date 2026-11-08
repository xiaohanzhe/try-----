# -*- coding: utf-8 -*-
u"""第175轮变异：证明 `check175.py` 的每条判据不是摆设。

规矩（与 173/174 轮同）
----------------------
  ① **先备份再改**（第一版"先改再备份"等于没恢复，sha1 还是绿的 = 假安全）；
  ② 每个变异跑完**立即**恢复并按 sha1 核对字节还原；
  ③ 「红在哪几条」按**实测**记，不按我期望记 —— 判据抓到 ≠ 我猜对是哪条；
  ④ 备份落 `D:\\_tmp\\mut175\\`（不在工作区，免得 `git add -A` 把它记成删除）。

用法：python mutate175.py
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
CHECK = os.path.join(HERE, 'check175.py')
BAK = 'D:\\_tmp\\mut175'

T1 = 'ch1.card_castle.card_castle_1f.json'      # rid=114
T2 = 'ch2.cyber_city.cyber_city_entrance.json'  # 另一章
DESK = 'desktop.json'


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def wr(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sha(p):
    return hashlib.sha1(rd(p).encode('utf-8')).hexdigest()


def run_check():
    r = subprocess.run([sys.executable, CHECK], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    reds = [ln.split('] ', 1)[1].split(u'    ')[0].strip()
            for ln in out.splitlines() if ln.startswith('[FAIL]')]
    codes = []
    for ln in reds:
        codes.append(ln.split(u' ')[0].strip())
    return r.returncode, codes


# ---------------------------------------------------------------------------
def m1_edit_value():
    """把一个房间号改错（114 -> 115）。"""
    p = os.path.join(SCENES, T1)
    s = rd(p)
    return p, s.replace(u'"original_room_id": 114,', u'"original_room_id": 115,', 1)


def m2_drop_field():
    """把一行整条删掉（模拟"没补"）。"""
    p = os.path.join(SCENES, T1)
    s = rd(p)
    return p, s.replace(u'  "original_room_id": 114,\r\n', u'', 1)


def m3_str_type():
    """值改成字符串（类型漂移）。"""
    p = os.path.join(SCENES, T1)
    s = rd(p)
    return p, s.replace(u'"original_room_id": 114,', u'"original_room_id": "114",', 1)


def m4_move_order():
    """键挪到 `objects` 之前（顺序真的错位，内容一字不变）。

    ★ 第一版把锚点写成 `"bg": `，结果**没红** —— 因为 `bg` 在文件里本来就
      紧跟 `area_name`，插到 `bg` 前等于没动顺序。**夹具不保真 = 报假问题**，
      改成插到 `objects` 前面（中间隔着 bg/bg_source/bgm 等好几行）。
    """
    p = os.path.join(SCENES, T1)
    s = rd(p)
    s2 = s.replace(u'  "original_room_id": 114,\r\n', u'', 1)
    assert s2 != s, u'没删掉 rid 行'
    s3 = s2.replace(u'  "objects": [', u'  "original_room_id": 114,\r\n  "objects": [', 1)
    assert s3 != s2, u'没插到 objects 前'
    return p, s3


def m5_touch_body():
    """改 objects 里的内容（其余字段被动了）。"""
    p = os.path.join(SCENES, T1)
    d = json.loads(rd(p))
    d['objects'][0]['_mut'] = 1
    return p, json.dumps(d, ensure_ascii=False, indent=2) + '\r\n'


def m6_desktop():
    """desktop 的房间号被改（-1 -> 0）。"""
    p = os.path.join(SCENES, DESK)
    s = rd(p)
    return p, s.replace(u'"original_room_id": -1,', u'"original_room_id": 0,', 1)


def m7_extra_line():
    """多插一个空行（行数/字节错了，JSON 仍合法）。"""
    p = os.path.join(SCENES, T2)
    s = rd(p)
    return p, s.replace(u'{\r\n', u'{\r\n\r\n', 1)


def m8_swap_real():
    """改成同章另一个**真实**房间号（不越界、不编造，但串行）。"""
    p = os.path.join(SCENES, T2)
    d = json.loads(rd(p))
    old = d['original_room_id']
    return p, rd(p).replace(u'"original_room_id": %d,' % old,
                            u'"original_room_id": %d,' % (old + 1), 1)


CASES = [
    ('M1 改错房间号 114->115', m1_edit_value),
    ('M2 整行删掉（模拟没补）', m2_drop_field),
    ('M3 值改成字符串 "114"', m3_str_type),
    ('M4 键挪到 objects 之前', m4_move_order),
    ('M5 顺手改了 objects 内容', m5_touch_body),
    ('M6 desktop 的 -1 改成 0', m6_desktop),
    ('M7 多插一个空行', m7_extra_line),
    ('M8 换成同章另一个真实房间号', m8_swap_real),
]


def main():
    os.makedirs(BAK, exist_ok=True)
    os.system('')
    rc, base = run_check()
    print(u'基线：rc=%d 红项=%r' % (rc, base))
    if rc != 0:
        print(u'★ 基线不绿，先修判据再跑变异。')
        return 2

    hit = 0
    for name, fn in CASES:
        p, new = fn()
        before = rd(p)
        h0 = sha(p)
        b = os.path.join(BAK, os.path.basename(p) + '.bak')
        shutil.copy2(p, b)
        try:
            wr(p, new)
            rc, reds = run_check()
            ok = rc != 0 and reds
            hit += 1 if ok else 0
            print(u'%-34s rc=%d 红=%r %s' % (name, rc, reds, u'✔' if ok else u'✘ 没抓到'))
        finally:
            shutil.copy2(b, p)
        h1 = sha(p)
        assert h1 == h0, u'%s 恢复失败 %s != %s' % (p, h1, h0)
        assert rd(p) == before, u'%s 字节没还原' % p

    print('')
    print('=' * 70)
    print(u'变异：%d/%d 被抓' % (hit, len(CASES)))
    rc, again = run_check()
    print(u'还原后复跑：rc=%d 红项=%r' % (rc, again))
    print('=' * 70)
    return 0 if hit == len(CASES) and rc == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
