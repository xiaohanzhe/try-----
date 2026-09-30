# -*- coding: utf-8 -*-
"""第68轮 · 鉴别力体检（disc68）。

目的：证明**我这两轮改/新增的判据不是恒真**。
  · 目标锁 A = `verify_items68.py`（新套件，22 判据）
  · 目标锁 B = `verify_objects44.py`（第68轮**升级过数据源与锚点形态**）

方法（照抄第48/56轮惯例）：逐例**定点改盘上文件** → 跑目标锁 →
断言"报红集合**精确等于**期望集合（且命中期望 id）" → **还原并核验字节一致**。

★ 每例**只碰一个事实**，且都保证还原（try/finally + sha256 往返核验）。
★ 破坏都是"真落进被测分支"的（不是改注释、不是改名到判据看不见的地方）。
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND68 = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND68, '..', '..'))
PY = r'C:\Python311\python.exe'
EV68 = os.path.join(ROUND68, '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OBJS = os.path.join(SCENES, 'objs')
MODULES = os.path.join(ROOT, 'ralsei_pet', 'modules')

LOCK_A = os.path.join(ROUND68, 'verify_items68.py')
LOCK_B = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻',
                      'verify_objects44.py')

_n_pass = 0
_n_fail = 0


def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()


def run_lock(script):
    r = subprocess.run([PY, script], cwd=ROOT, capture_output=True)
    out = r.stdout.decode('utf-8', 'replace')
    reds = re.findall(r'^\[FAIL\] (\S+)', out, re.M)
    return r.returncode, reds, out


def case(name, script, expect_ids, setup):
    """跑一例：setup() 返回 undo()；断言报红集合 == expect_ids。"""
    global _n_pass, _n_fail
    undo = None
    try:
        undo = setup()
        rc, reds, out = run_lock(script)
        got = set(reds)
        want = set(expect_ids)
        okc = (got == want)
        if okc:
            _n_pass += 1
            print('[PASS] %s  -> 精确报红 %s' % (name, sorted(got)))
        else:
            _n_fail += 1
            print('[FAIL] %s  -> 期望 %s 实得 %s（rc=%d）'
                  % (name, sorted(want), sorted(got), rc))
            for line in out.splitlines():
                if line.startswith('[FAIL]'):
                    print('        %s' % line)
    finally:
        if undo:
            undo()
    return _n_pass, _n_fail


# ---------------------------------------------------------------- 变更原语

def byte_mutate(path, old, new, count=None):
    """字节级替换（保 EOL/编码），返回 undo。

    `count=None` ⇒ 待替换串必须**唯一**（默认）；给数字 ⇒ 必须恰好出现该次数。
    """
    raw = io.open(path, 'rb').read()
    n = raw.count(old)
    assert n >= 1, '待替换串不在文件里：%r' % old[:40]
    if count is None:
        assert n == 1, '待替换串出现 %d 次（不唯一）：%r' % (n, old[:40])
    else:
        assert n == count, '待替换串出现 %d 次（期望 %d）：%r' % (n, count, old[:40])
    io.open(path, 'wb').write(raw.replace(old, new))

    def _undo():
        io.open(path, 'wb').write(raw)
    return _undo


def json_mutate(path, fn):
    """json 读改写（格式随意，锁用 json.load 不吃格式），返回 undo（写回**原字节**）。"""
    raw = io.open(path, 'rb').read()
    d = json.loads(raw.decode('utf-8'))
    fn(d)
    io.open(path, 'w', encoding='utf-8', newline='').write(
        json.dumps(d, ensure_ascii=False, indent=1))

    def _undo():
        io.open(path, 'wb').write(raw)
    return _undo


def rename_mutate(path, newpath):
    assert os.path.isfile(path), path
    assert not os.path.exists(newpath), newpath
    os.rename(path, newpath)

    def _undo():
        os.rename(newpath, path)
    return _undo


def rename_family(folder, pattern, prefix):
    """把 `folder` 里匹配 `pattern` 的一族文件统一加前缀改名（带回滚）。返回 undo。"""
    files = sorted(f for f in os.listdir(folder) if re.match(pattern, f))
    assert files, '找不到匹配 %s 的文件' % pattern
    done = []
    try:
        for f in files:
            nf = prefix + f
            os.rename(os.path.join(folder, f), os.path.join(folder, nf))
            done.append((f, nf))
    except Exception:
        for f, nf in done:
            os.rename(os.path.join(folder, nf), os.path.join(folder, f))
        raise

    def _undo():
        for f, nf in done:
            os.rename(os.path.join(folder, nf), os.path.join(folder, f))
    return _undo


def _first_scene_with(d, pred):
    for sid, raw in (d.get('scenes') or {}).items():
        if isinstance(raw, dict) and pred(raw):
            return raw
    return None


# ---------------------------------------------------------------- 各例

def c1_a1():
    """A1 等价性：把 inst68 里 doorA 的 x 改掉 ⇒ inst68 不再包含 inst42 的那条。"""
    p = os.path.join(EV68, 'inst68.json')
    return byte_mutate(p, b'"obj": "obj_doorA", "x": 155, "y": 230',
                       b'"obj": "obj_doorA", "x": 999, "y": 230')


def c2_b1():
    """B1 素材在位：把 `spr_treasurebox` **整族**帧文件改名（仍 .png，故 B3 不受影响）。

    ★ 首版只改 `_0` 一张 ⇒ B1 **不报红**：该 sprite 是多帧的，
      剩下 `_1`/`_2` 仍提供基名。破坏必须整族做，才真正落进被测分支。
    """
    return rename_family(OBJS, r'^spr_treasurebox_\d+\.png$', 'spr_treasureboxZZ')


def c3_c3():
    """C3 负控制：往产物里塞一条**缺口类**实例 ⇒ 缺口类"产物里有实例"不再为 0。"""
    p = os.path.join(SCENES, '_zone.ch1.castle_town.json')

    def _fn(d):
        raw = _first_scene_with(d, lambda r: r.get('objects'))
        assert raw is not None, '没有带 objects 的场景'
        raw['objects'].insert(0, {'pos': [1, 1], 'sprite': 'objs/spr_fallpaper_0.png',
                                  'src': 'obj_darkfountain_event', 'depth': 0})
    return json_mutate(p, _fn)


def c4_d5():
    """D5 接线：把 item_interact.py 的 INSPECT_KINDS **全名替换** ⇒ 源码里不再有该标识符。

    ★ 首版按"唯一"替换 ⇒ assert 报错：它出现 **2 次**（`INSPECT_KINDS = frozenset(...)`
      定义处 + `elif kind in INSPECT_KINDS:` 引用处）。两处都改才真正落进被测分支。
    """
    p = os.path.join(MODULES, 'item_interact.py')
    return byte_mutate(p, b'INSPECT_KINDS', b'_KINDS_OFF', count=2)


def c5_e1():
    """E1 按章取表：把 ch2 的表名退回 ch1 表 ⇒ 五张表名不齐。"""
    p = os.path.join(HERE, 'gen_objects68.py')
    return byte_mutate(p, b"'chapter2_objmap43.txt'", b"'objmap43.txt'")


def c6_b1b():
    """B1b 锚点集合精确：把 krisroom 的 doorA 坐标改掉。"""
    p = os.path.join(SCENES, 'ch1.kris_room.kris_s_room.json')
    return byte_mutate(p, b'"pos": [155, 230]', b'"pos": [155, 231]')


def c7_c2():
    """C2/C3 守恒：从某场景删掉一条 objects（该场景仍有 objects ⇒ C1 不受影响）。"""
    p = os.path.join(SCENES, '_zone.ch1.castle_town.json')

    def _fn(d):
        raw = _first_scene_with(d, lambda r: len(r.get('objects') or []) >= 2)
        assert raw is not None, '没有 >=2 条 objects 的场景'
        raw['objects'].pop()
    return json_mutate(p, _fn)


def c8_c0():
    """C0 数据源在位：把第68轮 ch1 普查文件改名 ⇒ 独立重算读不到 ⇒ 退化必须被抓。"""
    p = os.path.join(EV68, 'inst68.json')
    return rename_mutate(p, p + '.off')


CASES = [
    ('A1 等价性（改 inst68 一条实例）', LOCK_A, ['A1'], c1_a1),
    ('B1 素材在位（改名一个必需 sprite）', LOCK_A, ['B1'], c2_b1),
    ('C3 负控制（塞一条缺口类实例）', LOCK_A, ['C3'], c3_c3),
    ('D5 接线（去掉 INSPECT_KINDS）', LOCK_A, ['D5'], c4_d5),
    ('E1 按章取表（ch2 表退回 ch1 表）', LOCK_A, ['E1'], c5_e1),
    ('B1b 锚点集合（改 doorA 坐标）', LOCK_B, ['B1b'], c6_b1b),
    ('C2/C3 守恒（删一条 objects）', LOCK_B, ['C2', 'C3'], c7_c2),
    ('C0/C3 数据源在位（改名 ch1 普查）', LOCK_B, ['C0', 'C3'], c8_c0),
]


def main():
    # 体检前记录所有会被碰的文件的 hash（还原后要逐一对上）
    touched = [os.path.join(EV68, 'inst68.json'),
               os.path.join(OBJS, 'spr_treasurebox_0.png'),
               os.path.join(SCENES, '_zone.ch1.castle_town.json'),
               os.path.join(MODULES, 'item_interact.py'),
               os.path.join(HERE, 'gen_objects68.py'),
               os.path.join(SCENES, 'ch1.kris_room.kris_s_room.json')]
    before = {p: sha(p) for p in touched}

    print('== 第68轮鉴别力体检（8 例）==')
    for name, script, expect, setup in CASES:
        case(name, script, expect, setup)

    # 还原核验
    print('')
    print('== 还原核验 ==')
    bad = [p for p in touched if sha(p) != before[p]]
    if bad:
        for p in bad:
            print('[FAIL] 未还原：%s' % p)
    else:
        print('[PASS] 6 个被碰文件全部回到原始字节（sha256 一致）')

    # 体检后两锁必须全绿
    print('')
    print('== 体检后两锁 ==')
    for tag, script in (('items_round68', LOCK_A), ('objects_round44', LOCK_B)):
        rc, reds, out = run_lock(script)
        line = [l for l in out.splitlines() if l.startswith('合计')]
        print('%s: rc=%d %s' % (tag, rc, line[0] if line else '(无汇总)'))

    print('')
    print('体检结果：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
    return 0 if (_n_fail == 0 and not bad) else 1


if __name__ == '__main__':
    sys.exit(main())
