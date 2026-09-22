# -*- coding: utf-8 -*-
"""第 34 轮回归锁 · 第 29 套件：存储/配置层（task #13）
================================================================
覆盖用户第 34 轮主指令「你自己严查一下咱现在这些基础代码有没有纰漏」在
**生命周期 / 存储 / 配置线**上的 4 条真缺陷（Q1b/Q3b/Q4b/Q5）+ 1 条隐私回归（R1）。

全部调用**产品真函数**（config_manager / data_store / memory_store / memory_system），
沙箱一律用本地 NTFS 的 tempfile.mkdtemp()（E 盘 exFAT 不能当探针沙箱）。

判据风格：正/负控制成对；断行为不断写法；不打印绝对行号。
输出字面量 `[PASS]` / `[FAIL]`（run_all.py 的正则只认这两个词）。
"""
import os
import sys
import json
import shutil
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

_pass = 0
_fail = 0
_msgs = []


def check(cond, msg):
    global _pass, _fail
    if cond:
        _pass += 1
        _msgs.append("[PASS] %s" % msg)
    else:
        _fail += 1
        _msgs.append("[FAIL] %s" % msg)


SB = tempfile.mkdtemp(prefix='r34_suite_store_')

try:
    import config_manager as cm
    import data_store as ds
    import memory_store as ms

    # ==================== [A] Q1b：.corrupt.* 备份必须收敛 ====================
    work = os.path.join(SB, 'A')
    os.makedirs(work, exist_ok=True)
    cfg = os.path.join(work, 'config.json')
    with open(cfg, 'w', encoding='utf-8') as f:
        json.dump({"version": "1.0"}, f)
    for i in range(15):
        open("%s.backup.%d" % (cfg, 1700000000 + i), 'w').write('{}')
        open("%s.corrupt.%d" % (cfg, 1700000000 + i), 'w').write('{}')

    _m = cm.ConfigManager.__new__(cm.ConfigManager)
    _m.config_file = cfg
    _m._prune_old_backups()

    _nb = len([n for n in os.listdir(work) if '.backup.' in n])
    _nc = len([n for n in os.listdir(work) if '.corrupt.' in n])
    _keep = cm.ConfigManager.MAX_CONFIG_BACKUPS
    check(_nb <= _keep, "A1 .backup.* 收敛到 <= %d（实测 %d）" % (_keep, _nb))
    check(_nc <= _keep, "A2 .corrupt.* 也收敛到 <= %d（实测 %d）—— 原先一份都不清"
          % (_keep, _nc))
    # 负控制：两类必须**各自独立**计数（不能把 corrupt 挤掉 backup 或反之）
    check(_nb == _keep and _nc == _keep,
          "A3 两类各自独立保留 %d 份、互不挤占（backup=%d corrupt=%d）"
          % (_keep, _nb, _nc))
    # 负控制：最新的一份必须还在（别把"保留最近"写成"留最旧"）
    check(os.path.exists("%s.corrupt.%d" % (cfg, 1700000014)),
          "A4 最新 corrupt 备份被保留（收敛不是清光）")

    # ==================== [B] Q5：残留 .migprobe 不得把文件永久钉住 ====================
    t = os.path.join(SB, 'B', 'f.txt')
    os.makedirs(os.path.dirname(t), exist_ok=True)
    open(t, 'w').write('x' * 64)
    check(ds._movable(t) is True and os.path.exists(t),
          "B1 干净文件：_movable=True 且源完好（正控制）")

    open(t + '.migprobe', 'w').write('STALE')
    _r = ds._movable(t)
    check(_r is True and os.path.exists(t) and not os.path.exists(t + '.migprobe'),
          "B2 残留探针：被清掉、文件恢复可搬（原先恒 False → 永久滞留）")

    # 负控制：真正不可搬（父目录不存在）必须仍返回 False
    check(ds._movable(os.path.join(SB, 'B', 'nope', 'x.txt')) is False,
          "B3 真不可搬（父目录不存在）仍返回 False（修复没做成恒 True）")

    # ==================== [C] Q3b：data_store 留档名不得撞车 ====================
    st = os.path.join(SB, 'C', 'staging')
    vt = os.path.join(SB, 'C', 'vault')
    os.makedirs(st, exist_ok=True)
    os.makedirs(vt, exist_ok=True)

    _orig_staging = ds.staging_root
    _orig_vault = ds.vault_root
    ds.staging_root = lambda create=True: st
    ds.vault_root = lambda create=True: vt
    try:
        rel = 'sub/data.txt'
        sfile = os.path.join(st, rel)
        vfile = os.path.join(vt, rel)
        os.makedirs(os.path.dirname(sfile), exist_ok=True)
        os.makedirs(os.path.dirname(vfile), exist_ok=True)
        _d = os.path.dirname(vfile)

        def _one_round(tag):
            with open(vfile, 'w') as f:
                f.write('VAULT' * 20)
            os.utime(vfile, (2000000000, 2000000000))
            os.makedirs(os.path.dirname(sfile), exist_ok=True)
            with open(sfile, 'w') as f:
                f.write(tag)
            os.utime(sfile, (1000000000, 1000000000))
            ds.migrate_from_staging(remove_empty_dirs=False)

        _one_round('OLD-1')
        _one_round('OLD-2')
        _arch = [n for n in os.listdir(_d) if n.startswith('data.txt.old')]
        _body = {}
        for n in _arch:
            _body[n] = open(os.path.join(_d, n), encoding='utf-8').read()
        check('OLD-1' in _body.values(),
              "C1 第一次留档 OLD-1 仍存活（固定名 .old 原先会被覆盖）")
        check('OLD-2' in _body.values(), "C2 第二次留档 OLD-2 也已落盘")
        check(len(_arch) == 2, "C3 两次落选 = 两份留档（实测 %d）" % len(_arch))
        # 负控制：约定名 .old 仍存在（不能被改成只写时间戳名）
        check(any(n == 'data.txt.old' for n in _arch),
              "C4 约定名 data.txt.old 仍在（用户可见命名不破坏）")
    finally:
        ds.staging_root = _orig_staging
        ds.vault_root = _orig_vault

    # ==================== [D] Q4b：memory_store 留档名不得撞车 ====================
    tgt = os.path.join(SB, 'D', 'device')
    fb = os.path.join(SB, 'D', 'desk')
    os.makedirs(tgt, exist_ok=True)
    os.makedirs(fb, exist_ok=True)
    _orig_fb = ms.fallback_dir
    ms.fallback_dir = lambda: fb
    try:
        src = ms.memory_file_in(fb)
        dst = ms.memory_file_in(tgt)

        def _mround(tag):
            os.makedirs(fb, exist_ok=True)
            with open(dst, 'w', encoding='utf-8') as f:
                json.dump({"saved_at": 2000.0, "who": "device"}, f)
            with open(src, 'w', encoding='utf-8') as f:
                json.dump({"saved_at": 1000.0, "who": tag}, f)
            return ms.migrate_from_fallback(tgt)

        r1 = _mround('desktop1')
        r2 = _mround('desktop2')
        check(r1.get('moved') and r2.get('moved'), "D1 两轮搬运都成功（正控制）")

        _rolls = sorted(n for n in os.listdir(tgt) if n.startswith(ms.ROLLBACK_FILENAME))
        _who = {}
        for n in _rolls:
            try:
                _who[n] = json.load(open(os.path.join(tgt, n), encoding='utf-8')).get('who')
            except Exception:
                _who[n] = None
        check('desktop1' in _who.values(),
              "D2 第一次留档 desktop1 仍存活（每次启动都会调，原先必被覆盖）")
        check('desktop2' in _who.values(), "D3 第二次留档 desktop2 已落盘")
        check(ms.ROLLBACK_FILENAME in _rolls,
              "D4 约定名 %s 仍在（模块文档写明的可见名）" % ms.ROLLBACK_FILENAME)
    finally:
        ms.fallback_dir = _orig_fb

    # ==================== [E] R1：隐私 reset_all 必须连带时间戳留档一起清 ====================
    import memory_system as msys

    _o = msys.MemorySystem.__new__(msys.MemorySystem)
    _o._store = ms
    _o.memory_dir = tgt
    _o.memory_file = os.path.join(tgt, ms.MEMORY_FILENAME)
    _o.short_term_memory = []
    _o.fragments = []
    _o.keys = []
    _o.digests = {}
    _o.assoc = {}
    _o.graph = None
    _o._graph = None
    _o.recall_metrics = {}
    _o._recall_log = {}
    _o._last_consolidate = 0.0
    _o.experience = 0
    _o.level = 1
    _o.memory_strength = {}

    _before = [n for n in os.listdir(tgt) if n.startswith(ms.ROLLBACK_FILENAME)]
    _o.reset_all()
    _after = [n for n in os.listdir(tgt) if n.startswith(ms.ROLLBACK_FILENAME)]
    check(len(_before) >= 2, "E1 前置：reset 前确有 2 份留档（实测 %d）" % len(_before))
    check(not _after,
          "E2 隐私 reset_all 后留档清零（含带时间戳的，实测剩 %d）" % len(_after))

except Exception:
    _fail += 1
    _msgs.append("[FAIL] 套件异常:\n" + traceback.format_exc())
finally:
    shutil.rmtree(SB, ignore_errors=True)

for _m in _msgs:
    print(_m)
print("SUITE_SUMMARY pass=%d fail=%d" % (_pass, _fail))
sys.exit(0 if _fail == 0 else 1)
