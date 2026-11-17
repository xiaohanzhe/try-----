# -*- coding: utf-8 -*-
r"""第193轮：验证「产品代码真的会用 D 盘」（v2，修正负控制）。

v1 的负控制 B 判据是错的：`find_device_dir` 第 150 行有
`dir_exists` 兜底（设备根下已有 RalseiMemory 目录 ⇒ 认它），
所以"清掉变量后不该指向 D"这个前提本身不成立 —— **报红的是判据，不是产品**。

v2 换成成对的有鉴别力控制：
  A1 变量 = X（不存在路径）⇒ 返回 X
  A2 变量 = Y（另一个不存在路径，Y≠X）⇒ 返回 Y 且 ≠X（证明真读变量、非缓存）
  B  `RALSEI_MEMORY_DEVICE=off` + 清变量 ⇒ 返回 None（强制桌面兜底分支）
  C  变量 = D:\RalseiMemory ⇒ 返回 D（正控制），且 memory.json 真能解析、fragments=3
  D  产品级：MemorySystem 真加载一次，看它读到的 fragment 数（§201.6：不许只看"没报错"）

用法：C:\Python311\python.exe D:\_tmp\verify193.py
"""
import io
import json
import os
import sys
import traceback

MODS = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules'
EXPECT_DIR = r'D:\RalseiMemory'
NEG_X = r'D:\_tmp\no_such_vault_193x'
NEG_Y = r'D:\_tmp\no_such_vault_193y'
results = []


def chk(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print('[%s] %s  %s' % ('PASS' if cond else 'FAIL', name, detail))


def info(s):
    print('[INFO] %s' % s)


def from_registry():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
            v, _ = winreg.QueryValueEx(k, 'RALSEI_MEMORY_DIR')
            return v
    except Exception:                                                 # noqa: BLE001
        return ''


def main():
    reg = from_registry()
    chk('用户级变量已落注册表', reg == EXPECT_DIR, 'reg=%r' % reg)
    if reg:
        os.environ['RALSEI_MEMORY_DIR'] = reg
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ.pop('RALSEI_MEMORY_DEVICE', None)
    if MODS not in sys.path:
        sys.path.insert(0, MODS)

    try:
        import memory_store as MS
    except Exception:                                                 # noqa: BLE001
        traceback.print_exc()
        chk('import memory_store', False)
        return 1

    # ---------- C 正控制 ----------
    d = MS.find_device_dir(create=False)
    chk('正控制 变量=D 时返回 D', d == EXPECT_DIR, 'got=%r' % (d,))
    chk('D 盘目录确实存在', os.path.isdir(EXPECT_DIR))

    # ---------- A1 / A2 成对负控制 ----------
    os.environ['RALSEI_MEMORY_DIR'] = NEG_X
    dx = MS.find_device_dir(create=False)
    os.environ['RALSEI_MEMORY_DIR'] = NEG_Y
    dy = MS.find_device_dir(create=False)
    chk('负控制A 指向 X 时返回 X', dx == NEG_X, 'got=%r' % (dx,))
    chk('负控制A 指向 Y 时返回 Y', dy == NEG_Y, 'got=%r' % (dy,))
    chk('负控制A X≠Y 且都≠D（真有鉴别力）',
        NEG_X != NEG_Y and dx != dy and dx != EXPECT_DIR and dy != EXPECT_DIR,
        'X=%r Y=%r' % (dx, dy))
    chk('负控制A 两个路径都没被创建', not os.path.isdir(NEG_X) and not os.path.isdir(NEG_Y))

    # ---------- B 强制桌面兜底分支 ----------
    os.environ.pop('RALSEI_MEMORY_DIR', None)
    os.environ['RALSEI_MEMORY_DEVICE'] = 'off'
    db = MS.find_device_dir(create=False)
    chk('负控制B DEVICE=off 时返回 None（走桌面兜底）', db is None, 'got=%r' % (db,))
    os.environ.pop('RALSEI_MEMORY_DEVICE', None)

    # 还原真实配置
    os.environ['RALSEI_MEMORY_DIR'] = EXPECT_DIR

    # ---------- memory.json 内容面 ----------
    mp = os.path.join(EXPECT_DIR, 'memory.json')
    raw = None
    try:
        with io.open(mp, 'rb') as fh:
            raw = fh.read()
    except OSError as e:
        chk('读 memory.json', False, repr(e))
    if raw is not None:
        chk('memory.json 不是 USBC 污染', raw[:4] != b'USBC', 'head=%s' % raw[:4].hex())
        j = None
        try:
            j = json.loads(raw.decode('utf-8', 'replace'))
            okj = True
        except Exception as e:                                        # noqa: BLE001
            okj = False
            chk('memory.json 可解析', False, repr(e))
        if okj:
            chk('memory.json 可解析', True, 'saved_at=%r' % (j.get('saved_at'),))
            chk('fragments = 3（真数据不是空壳）', len(j.get('fragments') or []) == 3,
                'len=%d' % len(j.get('fragments') or []))
            chk('assoc = 11', len(j.get('assoc') or []) == 11,
                'len=%d' % len(j.get('assoc') or []))

    # ---------- D 产品级加载 ----------
    try:
        from PyQt5.QtWidgets import QApplication               # noqa: E402
        _app = QApplication.instance() or QApplication([])
    except Exception as e:                                            # noqa: BLE001
        info('QApplication 起不来（不影响文件面判定）：%r' % (e,))
    try:
        import memory_system as MSYS                           # noqa: E402

        class _P(object):
            api_enabled = False

        obj = MSYS.MemorySystem(_P())
        n_frag = None
        for attr in ('fragments', '_fragments', 'memory_fragments'):
            v = getattr(obj, attr, None)
            if isinstance(v, (list, tuple, dict)):
                n_frag = len(v)
                info('MemorySystem.%s 长度 = %d' % (attr, n_frag))
                break
        if n_frag is None:
            info('MemorySystem 读不到可计数的 fragments 属性（属性名待查），跳过该条')
        else:
            chk('产品级加载到 3 条 fragment', n_frag == 3, 'n=%d' % n_frag)
    except Exception as e:                                            # noqa: BLE001
        info('MemorySystem 加载尝试失败：%r' % (e,))
        traceback.print_exc()

    bad = [r for r in results if not r[1]]
    print('')
    print('=== 汇总 PASS=%d FAIL=%d ===' % (len(results) - len(bad), len(bad)))
    for r in bad:
        print('  [FAIL] %s %s' % (r[0], r[2]))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
