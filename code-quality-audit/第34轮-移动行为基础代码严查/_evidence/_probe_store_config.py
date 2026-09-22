# -*- coding: utf-8 -*-
"""第34轮 task#13 探针：存储/配置层疑点核验（全部调产品真函数，本地 NTFS %TEMP% 沙箱）

核验清单：
  Q1  config_manager：_prune_old_backups 是否清理 .corrupt.* 备份（应与 .backup.* 同等收敛）
  Q2  data_store.migrate_from_staging：目标更旧时 `copy2(dst, dst+'.old')` 留档**未校验长度**
  Q3  data_store.migrate_from_staging：`.old` 留档是固定名 → 二次搬运会**静默覆盖**上一次留档
  Q4  memory_store.migrate_from_fallback：ROLLBACK_FILENAME 固定名 → 同样覆盖问题
  Q5  data_store._movable()：`.migprobe` 已存在时的行为
  Q6  config_manager：.tmp 残留
"""
import os, sys, json, shutil, tempfile, traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '16_存储配置层探针.txt')
lines = []
def log(s):
    lines.append(s)
def flush():
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")
def check(cond, msg):
    log(("[PASS] " if cond else "[FAIL] ") + msg)

SANDBOX = tempfile.mkdtemp(prefix='r34_store_')
log("SANDBOX = %s" % SANDBOX)
log("")

try:
    # ============ Q1 ============
    log("========== Q1: config_manager 是否清理 .corrupt.* 备份 ==========")
    import config_manager as cm

    work = os.path.join(SANDBOX, 'q1')
    os.makedirs(work, exist_ok=True)
    cfg = os.path.join(work, 'config.json')
    json.dump({"version": "1.0"}, open(cfg, 'w', encoding='utf-8'))

    # 造 15 个 .backup.* 和 15 个 .corrupt.*（时间戳递增，保证排序稳定）
    base = 1700000000
    for i in range(15):
        open("%s.backup.%d" % (cfg, base + i), 'w').write('{}')
        open("%s.corrupt.%d" % (cfg, base + i), 'w').write('{}')

    m = cm.ConfigManager.__new__(cm.ConfigManager)
    m.config_file = cfg
    m._prune_old_backups()   # 调产品真函数

    backup_left = [n for n in os.listdir(work) if '.backup.' in n]
    corrupt_left = [n for n in os.listdir(work) if '.corrupt.' in n]
    log("after prune: .backup.*=%d  .corrupt.*=%d  (MAX_CONFIG_BACKUPS=%d)"
        % (len(backup_left), len(corrupt_left), cm.ConfigManager.MAX_CONFIG_BACKUPS))
    check(len(backup_left) <= cm.ConfigManager.MAX_CONFIG_BACKUPS,
          "Q1a  .backup.* 已被收敛到 <= %d（实测 %d）"
          % (cm.ConfigManager.MAX_CONFIG_BACKUPS, len(backup_left)))
    check(len(corrupt_left) <= cm.ConfigManager.MAX_CONFIG_BACKUPS,
          "Q1b  .corrupt.* 也已收敛到 <= %d（实测 %d）"
          % (cm.ConfigManager.MAX_CONFIG_BACKUPS, len(corrupt_left)))

    # ============ Q5: _movable ============
    log("")
    log("========== Q5: data_store._movable 探针行为 ==========")
    import data_store as ds
    t = os.path.join(SANDBOX, 'q5.txt')
    open(t, 'w').write('x' * 100)
    r1 = ds._movable(t)
    log("第一次 _movable(干净文件) = %s, 文件还在=%s" % (r1, os.path.exists(t)))
    # 造一个残留 .migprobe
    open(t + '.migprobe', 'w').write('STALE')
    r2 = ds._movable(t)
    log("残留 .migprobe 存在时 _movable = %s" % r2)
    log("  源文件还在=%s, .migprobe 内容=%r" % (
        os.path.exists(t), open(t + '.migprobe', encoding='utf-8').read() if os.path.exists(t + '.migprobe') else '(gone)'))
    check(r2 is True and os.path.exists(t),
          "Q5  .migprobe 残留不破坏后续 _movable（源文件保全）"

          if (r2 is True and os.path.exists(t)) else
          "Q5  .migprobe 残留导致 _movable=%s（源还在=%s）—— 需人工判读"
          % (r2, os.path.exists(t)))

    # ============ Q2/Q3: migrate_from_staging ============
    log("")
    log("========== Q2/Q3: migrate_from_staging 留档是否校验/覆盖 ==========")
    st = os.path.join(SANDBOX, 'q23', 'staging')
    vt = os.path.join(SANDBOX, 'q23', 'vault')
    os.makedirs(st, exist_ok=True); os.makedirs(vt, exist_ok=True)

    # 打桩：让 staging_root/vault_root 指向沙箱
    ds.staging_root = lambda create=True: st
    ds.vault_root = lambda create=True: vt

    rel = 'sub/data.txt'
    sfile = os.path.join(st, rel)
    vfile = os.path.join(vt, rel)
    os.makedirs(os.path.dirname(sfile), exist_ok=True)
    os.makedirs(os.path.dirname(vfile), exist_ok=True)

    # 情形：目标(vault)更新 → 源(staging)落选 → 应留档成 .old
    open(vfile, 'w').write('VAULT-NEW' * 10)
    os.utime(vfile, (2000000000, 2000000000))
    open(sfile, 'w').write('STAGING-OLD')
    os.utime(sfile, (1000000000, 1000000000))

    rep = ds.migrate_from_staging(remove_empty_dirs=False)
    log("round1 moved=%s skipped=%s errors=%s" % (rep['moved'], rep['skipped'], rep['errors']))
    old1 = vfile + '.old'
    c1 = open(old1, encoding='utf-8').read() if os.path.exists(old1) else '(none)'
    log("  .old 内容 = %r" % c1)
    check(c1 == 'STAGING-OLD', "Q3a  落选者（staging 旧版）被正确留档到 .old")

    # 第二次搬运：再造一个不同的落选者，看 .old 是否被**静默覆盖**
    open(sfile, 'w').write('STAGING-OLD-2')
    os.utime(sfile, (1000000000, 1000000000))
    rep2 = ds.migrate_from_staging(remove_empty_dirs=False)
    log("round2 moved=%s errors=%s" % (rep2['moved'], rep2['errors']))
    c2 = open(old1, encoding='utf-8').read() if os.path.exists(old1) else '(none)'
    log("  .old 内容（第二次后） = %r" % c2)
    check(c2 == 'STAGING-OLD',
          "Q3b  .old 保留了**第一次**的留档（未被第二次静默覆盖）")
    log("  → 若 Q3b FAIL：固定名 .old 被覆盖，第一次留档永久丢失")

    # ============ Q4: memory_store 留档固定名 ============
    log("")
    log("========== Q4: memory_store 留档固定名 ==========")
    import memory_store as ms
    tgt = os.path.join(SANDBOX, 'q4', 'device')
    fb  = os.path.join(SANDBOX, 'q4', 'desktop_memory')
    os.makedirs(tgt, exist_ok=True); os.makedirs(fb, exist_ok=True)
    ms.fallback_dir = lambda: fb
    src = ms.memory_file_in(fb)
    dst = ms.memory_file_in(tgt)

    # 设备版更新 → 桌面版落选 → 留档成 memory.old.json
    json.dump({"saved_at": 2000.0, "who": "device"}, open(dst, 'w', encoding='utf-8'))
    json.dump({"saved_at": 1000.0, "who": "desktop1"}, open(src, 'w', encoding='utf-8'))
    r1 = ms.migrate_from_fallback(tgt)
    log("round1 = %s" % {k: r1[k] for k in ('moved', 'kept', 'removed_fallback_file')})
    roll = os.path.join(tgt, ms.ROLLBACK_FILENAME)
    v1 = json.load(open(roll, encoding='utf-8')) if os.path.exists(roll) else None
    log("  留档 = %s" % v1)
    check(v1 and v1.get('who') == 'desktop1', "Q4a  落选者 desktop1 被正确留档")

    # round1 成功后 fallback_dir 被清空并**删掉了空目录**（行为正确）→ 重建再写
    os.makedirs(fb, exist_ok=True)
    json.dump({"saved_at": 1000.0, "who": "desktop2"}, open(src, 'w', encoding='utf-8'))
    r2 = ms.migrate_from_fallback(tgt)
    v2 = json.load(open(roll, encoding='utf-8')) if os.path.exists(roll) else None
    log("round2 = %s" % {k: r2[k] for k in ('moved', 'kept')})
    log("round2 留档 = %s" % v2)
    check(v2 and v2.get('who') == 'desktop1',
          "Q4b  留档保留了**第一次**的 desktop1（未被 desktop2 静默覆盖）")
    log("  → 若 Q4b FAIL：固定名 @%s 被覆盖，第一次留档永久丢失" % ms.ROLLBACK_FILENAME)

    # ---- Q4c：正确行为对照（留档名带时间戳时应两个都在）----
    log("")
    log("Q4c 结论：memory_store 的留档路径 = %s（固定名）" % ms.ROLLBACK_FILENAME)

except Exception:
    log("!! 探针异常:\n" + traceback.format_exc())
finally:
    try:
        shutil.rmtree(SANDBOX, ignore_errors=True)
        log("")
        log("sandbox cleaned: %s" % (not os.path.isdir(SANDBOX)))
    except Exception:
        pass
    flush()
print("done ->", OUT)
