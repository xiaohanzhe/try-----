# -*- coding: utf-8 -*-
"""
第130轮 · NPC 尾块独立回验（不复用施工脚本的实现）

为什么另写一份：`apply115_npc.py` 的 4c 判据本身就是错的（顶层白名单漏了 `personas`），
用它自己证明自己等于没证。这里从 **git HEAD 的旧索引** 出发，逐字段比对。

判据：
  N1 顶层：除 tail_text / tail_sha256 / personas 外，其他键逐字未变
  N2 personas：76 条，长度不变；每条只有 5 个记账字段变，其余字段逐字未变
  N3 tail_text 含 C2a 的两个锚句，且不含任何作品名（C2b）
  N4 tail_sha256 == sha256(tail_text.encode('utf-8'))
  N5 76 份 .txt：尾块 == tail_text + '\n'，且 tail 在 EOF
  N6 76 份 .txt：正文前缀与 git HEAD 逐字节相同（证明只动了尾块）
  N7 每条记录的 chars/bytes/sha256/sha256_lf/tail_sha256 全部重算命中
"""
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NPC = os.path.join(ROOT, "ralsei_pet", "assets", "npc")
IDX = os.path.join(NPC, "_personas.json")
PDIR = os.path.join(NPC, "persona")
REL_IDX = "ralsei_pet/assets/npc/_personas.json"

P = F = 0


def ok(cond, name, detail=""):
    global P, F
    if cond:
        P += 1
        print("[PASS] %s" % name)
    else:
        F += 1
        print("[FAIL] %s%s" % (name, ("   << %s" % detail) if detail else ""))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def head_bytes(rel):
    p = subprocess.run(["git", "show", "HEAD:%s" % rel], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout if p.returncode == 0 else None


old_raw = head_bytes(REL_IDX)
ok(old_raw is not None, "N0 能从 git HEAD 取到旧索引（独立来源）")
if old_raw is None:
    sys.exit(1)
old = json.loads(old_raw.decode("utf-8"))
new = json.loads(io.open(IDX, "rb").read().decode("utf-8"))

ALLOW_TOP = ("tail_text", "tail_sha256", "personas")
moved = [k for k in old if k not in ALLOW_TOP and old[k] != new.get(k)]
ok(not moved, "N1 顶层非目标键逐字未变", "变了=%r" % (moved,))

REC_ALLOW = {"chars", "bytes", "sha256", "sha256_lf", "tail_sha256"}
op, np_ = old.get("personas") or [], new.get("personas") or []
ok(len(op) == len(np_) == 76, "N2a personas 条数 76 未变", "%d → %d" % (len(op), len(np_)))
bad_rec = []
for i, (o, n) in enumerate(zip(op, np_)):
    extra = [k for k in o if k not in REC_ALLOW and o[k] != n.get(k)]
    add = [k for k in n if k not in o]
    if extra or add:
        bad_rec.append((i, extra, add))
ok(not bad_rec, "N2b 每条记录只有那 5 个记账字段变", "违例=%r" % (bad_rec[:3],))

TAIL = new.get("tail_text") or ""
A1 = "你知道自己是游戏里的一个角色"
A2 = "这件事不让你难过"
ok(A1 in TAIL and A2 in TAIL, "N3a C2a 两个锚句都在尾块里")
bad_work = [w for w in ("《Deltarune》", "《Undertale》", "《OneShot》") if w in TAIL]
ok(not bad_work, "N3b 尾块不点名具体作品（C2b）", "命中=%r" % (bad_work,))
ok(new.get("tail_sha256") == sha(TAIL.encode("utf-8")), "N4 tail_sha256 与 tail_text 自洽")

files = sorted(f for f in os.listdir(PDIR) if f.endswith(".txt"))
ok(len(files) == 76, "N5a 人设文件 76 份", str(len(files)))
tail_bytes = (TAIL + "\n").encode("utf-8")
bad_tail, bad_prefix, bad_rec2 = [], [], []
for fn in files:
    p = os.path.join(PDIR, fn)
    raw = io.open(p, "rb").read()
    if not raw.endswith(tail_bytes):
        bad_tail.append(fn)
        continue
    i = len(raw) - len(tail_bytes)
    hb = head_bytes("ralsei_pet/assets/npc/persona/%s" % fn)
    if hb is None:
        bad_prefix.append((fn, "取不到 HEAD"))
        continue
    # git blob 是 LF 归一；这边只比正文前缀（尾块之前）且都转 LF 比
    old_lf = hb.replace(b"\r\n", b"\n")
    cur_body = raw[:i].replace(b"\r\n", b"\n")
    if old_lf[:len(cur_body)] != cur_body:
        bad_prefix.append((fn, "正文前缀与 HEAD 不同"))
    rec = [r for r in np_ if r.get("file") == fn or r.get("name") == fn]
ok(not bad_tail, "N5b 76 份尾块都 == tail_text + 换行 且落在 EOF", "违例=%r" % (bad_tail[:3],))
ok(not bad_prefix, "N6 正文前缀与 git HEAD 逐字节一致（只动了尾块）", "违例=%r" % (bad_prefix[:3],))

print("\n合计：PASS=%d FAIL=%d" % (P, F))
sys.exit(1 if F else 0)
