# -*- coding: utf-8 -*-
"""铁律 0：一个 Python 脚本跑完 add/commit/push/ls-remote，每步都硬核验。"""
import io, os, subprocess, sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
MSG = os.path.join(ROOT, "_tmp_cmsg.txt")
PROXY = "http://127.0.0.1:64676"
REMOTE = "https://github.com/xiaohanzhe/try-----.git"

log = []


def run(args, **kw):
    p = subprocess.run(args, cwd=ROOT, capture_output=True, **kw)
    out = (p.stdout or b"").decode("utf-8", "replace").strip()
    err = (p.stderr or b"").decode("utf-8", "replace").strip()
    return p.returncode, out, err


# 1) git add -A
rc, o, e = run(["git", "add", "-A"])
log.append("[1] add rc=%d %s %s" % (rc, o[:200], e[:200]))

# 2) 取凭据（非交互 GCM）
cred_in = "url=https://github.com/xiaohanzhe/try-----.git\n\n"
p = subprocess.run(["git", "credential", "fill"], cwd=ROOT,
                   input=cred_in.encode(), capture_output=True)
cred = p.stdout.decode("utf-8", "replace")
user = pw = ""
for ln in cred.split("\n"):
    if ln.startswith("username="):
        user = ln[len("username="):]
    elif ln.startswith("password="):
        pw = ln[len("password="):]
log.append("[2] cred user=%s pw_len=%d" % (user, len(pw)))
if not user or not pw:
    log.append("!! 取不到凭据，中止")
    io.open(os.path.join(ROOT, "_tmp_git_log.txt"), "w", encoding="utf-8").write("\n".join(log))
    sys.exit(1)

# 3) commit -F（UTF-8 文件，无 BOM）
rc, o, e = run(["git", "-c", "user.name=xiaohanzhe",
                "-c", "user.email=xiaohanzhe@users.noreply.github.com",
                "commit", "-F", MSG])
log.append("[3] commit rc=%d\n%s\n%s" % (rc, o[:400], e[:400]))

# 4) 核验提交真的发生
rc, o, e = run(["git", "log", "--oneline", "-1"])
log.append("[4] HEAD = %s" % o)

# 5) push（带凭据头 + 代理）
import base64
b64 = base64.b64encode(("%s:%s" % (user, pw)).encode("ascii")).decode("ascii")
PUSH_ARGS = ["git",
             "-c", "credential.helper=",
             "-c", "http.proxy=" + PROXY,
             "-c", "https.proxy=" + PROXY,
             "-c", "http.extraheader=Authorization: Basic " + b64,
             "push", "origin", "main"]
pushed = False
for attempt in range(1, 6):
    rc, o, e = run(PUSH_ARGS)
    log.append("[5.%d] push rc=%d out=%s err=%s" % (attempt, rc, o[:300], e[:300]))
    if rc == 0:
        pushed = True
        break

# 6) 独立核验：ls-remote（另起命令，不复用上面的 argv）+ rev-parse
LS_ARGS = ["git",
           "-c", "credential.helper=",
           "-c", "http.proxy=" + PROXY,
           "-c", "https.proxy=" + PROXY,
           "-c", "http.extraheader=Authorization: Basic " + b64,
           "ls-remote", "origin", "refs/heads/main"]
ls_ok = False
for attempt in range(1, 6):
    rc, o, e = run(LS_ARGS)
    log.append("[6.%d] ls-remote rc=%d out=%s err=%s" % (attempt, rc, o[:300], e[:200]))
    if rc == 0 and o:
        ls_ok = True
        remote_sha = o.split("\t")[0].strip()
        break

rc, local_sha, e = run(["git", "rev-parse", "HEAD"])
local_sha = local_sha.strip()
log.append("[7] local HEAD = %s" % local_sha)

rc, op, e = run(["git", "rev-parse", "origin/main"])
log.append("[7b] origin/main = %s" % op.strip())

log.append("")
log.append("== 结论 ==")
log.append("pushed=%s ls_ok=%s" % (pushed, ls_ok))
if ls_ok:
    log.append("remote_sha=%s" % remote_sha)
    log.append("MATCH=%s" % ("YES" if remote_sha == local_sha else "NO"))
if pushed and ls_ok and remote_sha == local_sha:
    log.append("*** 提交与推送均已核实 ***")
else:
    log.append("*** 需人工复核 ***")

io.open(os.path.join(ROOT, "_tmp_git_log.txt"), "w", encoding="utf-8").write("\n".join(log))
print("\n".join(log))
