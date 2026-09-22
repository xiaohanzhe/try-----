# -*- coding: utf-8 -*-
"""第34轮补充提交（记忆同步）+ push + 三方核验"""
import os, sys, re, base64, socket, subprocess, traceback

REPO = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
URL  = "https://github.com/xiaohanzhe/try-----.git"
MSG  = r"E:\Download\_tmp\_commit_msg_34c.md"
OUT  = r"E:\Download\_tmp\_push_result_34c.txt"

buf = []
def flush():
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(buf) + "\n")
def log(s):
    buf.append(s); flush()
def run(args, timeout=90, **kw):
    try:
        p = subprocess.run(args, cwd=REPO, capture_output=True, timeout=timeout, **kw)
        return (p.returncode, p.stdout.decode("utf-8","replace"), p.stderr.decode("utf-8","replace"))
    except subprocess.TimeoutExpired:
        return -999, "", "TIMEOUT after %ss" % timeout
    except Exception:
        return -998, "", traceback.format_exc()

try:
    log("[0] msg first3=%s" % list(open(MSG, "rb").read()[:3]))
    rc, o, e = run(["git", "add", "-A"])
    log("[1] add rc=%d err=%s" % (rc, e.strip()[:300]))
    rc, o, e = run(["git", "commit", "-F", MSG])
    log("[2] commit rc=%d out=%s err=%s" % (rc, o.strip()[:400], e.strip()[:300]))
    rc, o, e = run(["git", "log", "--oneline", "-1"])
    log("[3] HEAD=%s" % o.strip())
    local = run(["git", "rev-parse", "HEAD"])[1].strip()
    log("[3b] local=%s" % local)

    cred = None
    try:
        p = subprocess.run("git credential fill", cwd=REPO, shell=True, capture_output=True,
                           timeout=60, input=b"url=" + URL.encode() + b"\n\n")
        cred = p.stdout.decode("utf-8", "replace")
    except Exception:
        log("!! 取凭据失败:\n" + traceback.format_exc())
    usr = pw = ""
    if cred:
        for ln in cred.splitlines():
            if ln.startswith("username="): usr = ln[9:]
            elif ln.startswith("password="): pw = ln[9:]
    log("[5] cred user=%r pw_len=%d" % (usr, len(pw)))
    if not pw:
        log("!! 无凭据 → 跳过 push"); flush(); sys.exit(2)
    b64 = base64.b64encode(("%s:%s" % (usr, pw)).encode("ascii")).decode("ascii")

    cands = []
    for k in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
        m = re.search(r"127\.0\.0\.1:(\d+)", os.environ.get(k, ""))
        if m and m.group(1) not in cands: cands.append(m.group(1))
    if "7897" not in cands: cands.append("7897")
    try:
        p = subprocess.run("netstat -ano", shell=True, capture_output=True, timeout=30)
        for m in re.finditer(r"127\.0\.0\.1:(\d+)\s+\S+\s+LISTENING", p.stdout.decode("utf-8","replace")):
            if m.group(1) not in cands: cands.append(m.group(1))
    except Exception: pass
    alive = []
    for port in cands:
        try:
            s = socket.create_connection(("127.0.0.1", int(port)), timeout=1.5); s.close(); alive.append(port)
        except Exception: pass
    log("[5b] alive(first 6)=%s" % alive[:6])
    if not alive:
        log("!! 无可用代理 → 跳过 push"); flush(); sys.exit(3)

    pushed = False
    for port in alive:
        px = "http://127.0.0.1:" + port
        common = ["-c","credential.helper=","-c","http.proxy="+px,"-c","https.proxy="+px,
                  "-c","http.extraheader=Authorization: Basic "+b64]
        for i in range(1, 4):
            rc, o, e = run(["git"]+common+["push","origin","main"], timeout=90)
            log("[6] push port=%s #%d rc=%d out=%s err=%s" % (port,i,rc,o.strip()[:200],e.strip()[:300]))
            if rc == 0:
                pushed = True; break
        if pushed: break

    match_remote = "NO"; remote_line = ""
    for port in alive:
        px = "http://127.0.0.1:" + port
        common = ["-c","credential.helper=","-c","http.proxy="+px,"-c","https.proxy="+px,
                  "-c","http.extraheader=Authorization: Basic "+b64]
        for i in range(1, 6):
            rc, o, e = run(["git"]+common+["ls-remote","origin","refs/heads/main"], timeout=60)
            ln = o.strip()
            log("[7] ls-remote port=%s #%d rc=%d out=%s" % (port,i,rc,ln[:200]))
            if ln:
                remote_line = ln
                if local and local in ln: match_remote = "YES"
                break
        if match_remote == "YES": break
    log("[8b] MATCH(ls-remote)=%s  remote=%s" % (match_remote, remote_line))
    rc, o, e = run(["git", "rev-parse", "origin/main"])
    log("[9b] MATCH(rev-parse)=%s" % ("YES" if o.strip() == local else "NO"))
    rc, o, e = run(["git", "status", "--porcelain"])
    log("[10] final status=%r" % o.strip()[:1200])
except Exception:
    log("!! 脚本异常:\n" + traceback.format_exc()); flush(); raise
finally:
    flush()
