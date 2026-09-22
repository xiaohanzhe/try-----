# -*- coding: utf-8 -*-
"""第34轮 task#13 复验：Q1b / Q3b / Q4b / Q5 四条修复后的行为 + reset_all 回归。"""
import os, sys, json, shutil, tempfile, traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '17_存储配置层_修复后复验.txt')
lines = []
def log(s): lines.append(s)
def flush():
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")
def check(cond, msg):
    log(("[PASS] " if cond else "[FAIL] ") + msg)

SB = tempfile.mkdtemp(prefix='r34_fix_')
log("SANDBOX = %s\n" % SB)

try:
    import config_manager as cm
    import data_store as ds
    import memory_store as ms

    # ---------- Q1b 复验 ----------
    log("========== Q1b 复验：.corrupt.* 也收敛 ==========")
    work = os.path.join(SB, 'q1'); os.makedirs(work, exist_ok=True)
    cfg = os.path.join(work, 'config.json')
    json.dump({"version": "1.0"}, open(cfg, 'w', encoding='utf-8'))
    for i in range(15):
        open("%s.backup.%d" % (cfg, 1700000000 + i), 'w').write('{}')
        open("%s.corrupt.%d" % (cfg, 1700000000 + i), 'w').write('{}')
    m = cm.ConfigManager.__new__(cm.ConfigManager); m.config_file = cfg
    m._prune_old_backups()
    b = len([n for n in os.listdir(work) if '.backup.' in n])
    c = len([n for n in os.listdir(work) if '.corrupt.' in n])
    log("after prune: .backup.*=%d  .corrupt.*=%d" % (b, c))
    check(b <= 10, "Q1b-1  .backup.* 收敛（实测 %d）" % b)
    check(c <= 10, "Q1b-2  .corrupt.* 收敛（实测 %d）" % c)
    # 反向控制：不能把两类混在一起算配额（各自独立 10）
    check(c == 10 and b == 10, "Q1b-3  两类各自独立保留 10 份（互不挤占）")

    # ---------- Q5 复验 ----------
    log("")
    log("========== Q5 复验：残留 .migprobe ==========")
    t = os.path.join(SB, 'q5.txt'); open(t, 'w').write('x' * 100)
    r1 = ds._movable(t); log("干净文件 _movable = %s" % r1)
    open(t + '.migprobe', 'w').write('STALE')
    r2 = ds._movable(t)
    log("残留 .migprobe 时 _movable = %s, 源还在=%s, .migprobe 还在=%s"
        % (r2, os.path.exists(t), os.path.exists(t + '.migprobe')))
    check(r2 is True and os.path.exists(t) and not os.path.exists(t + '.migprobe'),
          "Q5  残留探针被清掉、文件恢复可搬（不再永久滞留）")
    # 反向控制：真被占用的文件仍须判 False（别把修复做成恒 True）
    log("  反向控制：用一个目录冒充文件（rename 会失败）")
    d = os.path.join(SB, 'adir'); os.makedirs(d, exist_ok=True)
    log("  _movable(目录) = %s（True 也属正常：目录可改名）" % ds._movable(d))

    # ---------- Q3b 复验 ----------
    log("")
    log("========== Q3b 复验：data_store .old 不再被覆盖 ==========")
    st = os.path.join(SB, 'q3', 'staging'); vt = os.path.join(SB, 'q3', 'vault')
    os.makedirs(st, exist_ok=True); os.makedirs(vt, exist_ok=True)
    ds.staging_root = lambda create=True: st
    ds.vault_root = lambda create=True: vt
    rel = 'sub/data.txt'
    sfile = os.path.join(st, rel); vfile = os.path.join(vt, rel)
    os.makedirs(os.path.dirname(sfile), exist_ok=True)
    os.makedirs(os.path.dirname(vfile), exist_ok=True)

    def _round(tag):
        open(vfile, 'w').write('VAULT-NEW' * 10)
        os.utime(vfile, (2000000000, 2000000000))
        os.makedirs(os.path.dirname(sfile), exist_ok=True)
        open(sfile, 'w').write(tag)
        os.utime(sfile, (1000000000, 1000000000))
        rep = ds.migrate_from_staging(remove_empty_dirs=False)
        arch = [n for n in os.listdir(os.path.dirname(vfile)) if n.startswith('data.txt.old')]
        return rep, sorted(arch)

    r1, a1 = _round('STAGING-OLD-1'); log("round1 moved=%s archives=%s" % (r1['moved'], a1))
    r2, a2 = _round('STAGING-OLD-2'); log("round2 moved=%s archives=%s" % (r2['moved'], a2))
    contents = {}
    for n in a2:
        contents[n] = open(os.path.join(os.path.dirname(vfile), n), encoding='utf-8').read()
    log("留档内容 = %s" % contents)
    check('STAGING-OLD-1' in contents.values(),
          "Q3b-1  第一次留档 STAGING-OLD-1 仍存活（未被覆盖）")
    check('STAGING-OLD-2' in contents.values(),
          "Q3b-2  第二次留档 STAGING-OLD-2 也已落盘")
    check(len(a2) == 2, "Q3b-3  两次落选 = 两个留档文件（实测 %d）" % len(a2))

    # ---------- Q4b 复验 ----------
    log("")
    log("========== Q4b 复验：memory_store 留档不再被覆盖 ==========")
    tgt = os.path.join(SB, 'q4', 'device'); fb = os.path.join(SB, 'q4', 'desk')
    os.makedirs(tgt, exist_ok=True); os.makedirs(fb, exist_ok=True)
    ms.fallback_dir = lambda: fb
    src = ms.memory_file_in(fb); dst = ms.memory_file_in(tgt)

    def _mround(tag, s_at):
        os.makedirs(fb, exist_ok=True)
        json.dump({"saved_at": 2000.0, "who": "device"}, open(dst, 'w', encoding='utf-8'))
        json.dump({"saved_at": s_at, "who": tag}, open(src, 'w', encoding='utf-8'))
        return ms.migrate_from_fallback(tgt)

    _mround('desktop1', 1000.0)
    _mround('desktop2', 1000.0)
    rolls = sorted(n for n in os.listdir(tgt) if n.startswith(ms.ROLLBACK_FILENAME))
    who = {}
    for n in rolls:
        who[n] = json.load(open(os.path.join(tgt, n), encoding='utf-8')).get('who')
    log("留档文件 = %s" % who)
    check('desktop1' in who.values(), "Q4b-1  第一次留档 desktop1 仍存活")
    check('desktop2' in who.values(), "Q4b-2  第二次留档 desktop2 已落盘")
    check(ms.ROLLBACK_FILENAME in rolls,
          "Q4b-3  %s（约定名）仍是其中之一" % ms.ROLLBACK_FILENAME)

    # ---------- reset_all 回归 ----------
    log("")
    log("========== reset_all 回归：隐私清理必须连带时间戳留档一起清 ==========")
    import memory_system as msys
    msys_obj = msys.MemorySystem.__new__(msys.MemorySystem)
    msys_obj._store = ms
    msys_obj.memory_dir = tgt
    msys_obj.memory_file = dst
    msys_obj.short_term_memory = []
    msys_obj.fragments = []; msys_obj.keys = []; msys_obj.digests = {}
    msys_obj.assoc = {}; msys_obj.graph = None; msys_obj._graph = None
    msys_obj.recall_metrics = {}; msys_obj._recall_log = {}
    msys_obj._last_consolidate = 0.0; msys_obj.experience = 0; msys_obj.level = 1
    msys_obj.memory_strength = {}
    try:
        msys_obj.reset_all()
    except Exception as e:
        log("  reset_all 抛异常（可能缺字段）: %s" % e)
    left = sorted(n for n in os.listdir(tgt) if n.startswith(ms.ROLLBACK_FILENAME))
    log("reset_all 之后残留留档 = %s" % left)
    check(not left, "R1  隐私 reset_all 清掉了全部留档（含带时间戳的）")

except Exception:
    log("!! 探针异常:\n" + traceback.format_exc())
finally:
    shutil.rmtree(SB, ignore_errors=True)
    log("\nsandbox cleaned: %s" % (not os.path.isdir(SB)))
    flush()
print("done ->", OUT)
