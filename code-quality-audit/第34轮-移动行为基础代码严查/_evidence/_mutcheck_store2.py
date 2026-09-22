# -*- coding: utf-8 -*-
"""鉴别力体检 v2 —— 修掉 v1 的"还原判定自己说谎"，改用「先落快照再来回」策略。

v1 的教训：finally 里用同一个 `src` 字符串写回后立刻 sha 比对，理论上应一致却报了 False。
不纠结判据细节 —— 换成**绝对可信的参照系**：体检前把三份文件原样备份到临时目录，
每轮回退/还原都拿**备份副本**做逐字节比对（而不是拿内存字符串）。
"""
import os, subprocess, hashlib, shutil, tempfile, sys

REPO = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PY = r"C:\Python311\python.exe"
BASE = os.path.join(REPO, "code-quality-audit", "第34轮-移动行为基础代码严查")
SUITE = os.path.join(BASE, "verify_round34_store_config.py")
OUT = os.path.join(BASE, "_evidence", "18_鉴别力体检_store.txt")

FILES = {
    "config_manager": os.path.join(REPO, "ralsei_pet", "modules", "config_manager.py"),
    "data_store":     os.path.join(REPO, "ralsei_pet", "modules", "data_store.py"),
    "memory_store":   os.path.join(REPO, "ralsei_pet", "modules", "memory_store.py"),
}

MUTS = [
    ("回退 A：config_manager 只剪 .backup.（原缺陷）", "config_manager",
     '        for tag in (\'.backup.\', \'.corrupt.\'):\n            self._prune_by_prefix(f"{self.config_file}{tag}", keep)',
     '        self._prune_by_prefix(f"{self.config_file}.backup.", keep)'),
    ("回退 B：data_store 不预清残留 .migprobe（原缺陷）", "data_store",
     "    if os.path.exists(probe):\n        try:\n            os.remove(probe)\n        except OSError:\n            return False      # 连残留都清不掉（被占用/无权限）→ 保守判为不可搬\n",
     ""),
    ("回退 C：data_store 用固定名 .old（原缺陷）", "data_store",
     "                            _arch = _archive_name(dst)\n                            shutil.copy2(src, _arch)",
     "                            _arch = dst + '.old'\n                            shutil.copy2(src, _arch)"),
    ("回退 D：memory_store 用固定名留档（原缺陷）", "memory_store",
     "            if not _copy_verified(src, _rollback_path(target_dir)):",
     "            if not _copy_verified(src, os.path.join(target_dir, ROLLBACK_FILENAME)):"),
]

SNAP = tempfile.mkdtemp(prefix="r34_snap_")
for k, p in FILES.items():
    shutil.copy2(p, os.path.join(SNAP, k + ".py"))

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def restore(k):
    """从快照副本还原（最硬的参照系）"""
    shutil.copy2(os.path.join(SNAP, k + ".py"), FILES[k])

def run_suite():
    p = subprocess.run([PY, SUITE], cwd=REPO, capture_output=True, timeout=180)
    out = p.stdout.decode("utf-8", "replace")
    fails = [l for l in out.splitlines() if l.startswith("[FAIL]")]
    summ = [l for l in out.splitlines() if l.startswith("SUITE_SUMMARY")]
    return p.returncode, fails, (summ[0] if summ else "?")

L = []
def log(s): L.append(s)

snap_sha = {k: sha(os.path.join(SNAP, k + ".py")) for k in FILES}
log("=== 鉴别力体检 v2：round34_store_config ===")
log("快照 sha256: %s\n" % {k: v[:12] for k, v in snap_sha.items()})

rc, fails, summ = run_suite()
log("[基线] rc=%d %s" % (rc, summ))
assert rc == 0 and not fails, "基线不绿，体检无意义"

for name, key, old, new in MUTS:
    p = FILES[key]
    src = open(p, encoding="utf-8").read()
    if old not in src:
        log("\n[跳过] %s —— 锚点未命中" % name); continue
    try:
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(src.replace(old, new, 1))
        rc, fails, summ = run_suite()
        log("\n[%s] rc=%d %s" % (name, rc, summ))
        for f_ in fails:
            log("   " + f_)
        log("   => 抓破坏：%s" % ("YES" if (rc != 0 and fails) else "NO（锁无鉴别力！）"))
    finally:
        restore(key)
        ok = (sha(p) == snap_sha[key])
        log("   还原逐字节一致：%s" % ok)

rc, fails, summ = run_suite()
log("\n[终检] rc=%d %s  FAIL=%d" % (rc, summ, len(fails)))
allok = all(sha(FILES[k]) == snap_sha[k] for k in FILES)
log("三文件全部还原到快照：%s" % allok)
shutil.rmtree(SNAP, ignore_errors=True)
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("done ->", OUT)
