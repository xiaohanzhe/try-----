# -*- coding: utf-8 -*-
"""鉴别力体检：逐条回退 4 处修复，看第 29 套件是否报红。每轮改完必须还原（逐字节校验）。"""
import os, subprocess, sys, hashlib, shutil

REPO = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PY = r"C:\Python311\python.exe"
SUITE = os.path.join(REPO, "code-quality-audit", "第34轮-移动行为基础代码严查",
                     "verify_round34_store_config.py")
OUT = os.path.join(REPO, "code-quality-audit", "第34轮-移动行为基础代码严查",
                   "_evidence", "18_鉴别力体检_store.txt")

TARGETS = [
    (os.path.join(REPO, "ralsei_pet", "modules", "config_manager.py"),
     '        for tag in (\'.backup.\', \'.corrupt.\'):\n            self._prune_by_prefix(f"{self.config_file}{tag}", keep)',
     '        self._prune_by_prefix(f"{self.config_file}.backup.", keep)',
     "回退 A：只剪 .backup.（原缺陷）"),
    (os.path.join(REPO, "ralsei_pet", "modules", "data_store.py"),
     "    if os.path.exists(probe):\n        try:\n            os.remove(probe)\n        except OSError:\n            return False      # 连残留都清不掉（被占用/无权限）→ 保守判为不可搬\n",
     "",
     "回退 B：不预先清残留 .migprobe（原缺陷）"),
    (os.path.join(REPO, "ralsei_pet", "modules", "data_store.py"),
     "                            _arch = _archive_name(dst)\n                            shutil.copy2(src, _arch)",
     "                            _arch = dst + '.old'\n                            shutil.copy2(src, _arch)",
     "回退 C：data_store 用固定名 .old（原缺陷）"),
    (os.path.join(REPO, "ralsei_pet", "modules", "memory_store.py"),
     "            if not _copy_verified(src, _rollback_path(target_dir)):",
     "            if not _copy_verified(src, os.path.join(target_dir, ROLLBACK_FILENAME)):",
     "回退 D：memory_store 用固定名留档（原缺陷）"),
]

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def run_suite():
    p = subprocess.run([PY, SUITE], cwd=REPO, capture_output=True, timeout=180)
    out = p.stdout.decode("utf-8", "replace")
    fails = [l for l in out.splitlines() if l.startswith("[FAIL]")]
    summ = [l for l in out.splitlines() if l.startswith("SUITE_SUMMARY")]
    return p.returncode, fails, (summ[0] if summ else "?")

lines = []
def log(s):
    lines.append(s)

log("=== 鉴别力体检：第 29 套件 round34_store_config ===")
base = {p: sha(p) for p, _, _, _ in TARGETS}
log("基线 sha256: %s\n" % {os.path.basename(k): v[:12] for k, v in base.items()})

rc, fails, summ = run_suite()
log("[基线] rc=%d %s  FAIL 数=%d" % (rc, summ, len(fails)))
assert rc == 0 and not fails, "基线必须是全绿，否则体检无意义"

for path, old, new, name in TARGETS:
    src = open(path, encoding="utf-8").read()
    if old not in src:
        log("\n[跳过] %s —— 锚点未命中（源码可能已变）" % name)
        continue
    try:
        open(path, "w", encoding="utf-8", newline="").write(src.replace(old, new, 1))
        rc, fails, summ = run_suite()
        log("\n[%s] rc=%d %s" % (name, rc, summ))
        for f in fails:
            log("   " + f)
        log("   => 抓破坏：%s" % ("YES" if rc != 0 and fails else "NO（锁无鉴别力！）"))
    finally:
        open(path, "w", encoding="utf-8", newline="").write(src)
        ok = (sha(path) == base[path])
        log("   还原逐字节一致：%s" % ok)
        if not ok:
            log("   !!! 还原失败，立即中止 !!!")
            break

rc, fails, summ = run_suite()
log("\n[终检] rc=%d %s  FAIL 数=%d" % (rc, summ, len(fails)))
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("done ->", OUT)
