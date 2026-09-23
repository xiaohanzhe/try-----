import os, io, sys, subprocess, re

REPO = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
MEM  = os.path.join(REPO, ".workbuddy", "memory", "MEMORY.md")
DET  = os.path.join(REPO, ".workbuddy", "memory", "参考-契约与历轮（详版）.md")

def js_len(t):
    return len(t.strip().encode("utf-16-le")) // 2

def rd(p):
    with open(p, "rb") as f:
        return f.read()

out = []
def P(s):
    out.append(s)
    print(s)

P("=" * 70)
P("【1】体积判据（上限 10,000 字符 = JS content.length）")
b = rd(MEM)
t = b.decode("utf-8")
jl = js_len(t); pyc = len(t.strip()); lines = t.count("\n")
cap = 10000
P("  MEMORY.md: js_len=%d  py_chars=%d  bytes=%d  lines=%d" % (jl, pyc, len(b), lines))
P("  => %s (余量 %d)" % ("OK" if jl <= cap else "!!! 超限 %d" % (jl - cap), cap - jl))

P("")
P("【2】编码 / EOL")
P("  BOM=%s  fffd=%d  CRLF=%d  LF=%d  结尾换行=%s" % (
    b[:3] == b"\xef\xbb\xbf", t.count("\ufffd"), t.count("\r\n"), t.count("\n"), t.endswith("\n")))

P("")
P("【3】结构自检（## N. 标题）")
heads = re.findall(r"(?m)^##\s+(\d+)\.", t)
P("  标题: %s" % ",".join(heads))
glued = re.findall(r"(?m)^##\s+\d+\.[^\n]*\S##", t)
P("  glued=%s" % glued)

P("")
P("【4】逐令牌回验（旧版 HEAD 的令牌 vs 新速查本 ∪ 详版）")
try:
    old = subprocess.run(["git", "-C", REPO, "show", "HEAD:.workbuddy/memory/MEMORY.md"],
                         capture_output=True)
    oldt = old.stdout.decode("utf-8", "replace")
except Exception as e:
    oldt = ""
    P("  git show 失败: %r" % e)
det = rd(DET).decode("utf-8", "replace")

tokpat = re.compile(r"(§\d+(?:\.\d+)*|[0-9a-f]{7,40}|[A-Za-z_][A-Za-z0-9_\.]{6,}|[0-9]{3,})")
toks = sorted(set(tokpat.findall(oldt)))
missing = [x for x in toks if x not in t and x not in det]
P("  旧版候选令牌 %d 个；新速查本∪详版 中缺失 %d 个" % (len(toks), len(missing)))
P("  missing=%s" % missing)

P("")
P("【5】新速查本独有令牌（详版没有）")
toks2 = sorted(set(tokpat.findall(t)))
only = [x for x in toks2 if x not in det]
P("  新速查本令牌 %d 个；详版缺 %d 个" % (len(toks2), len(only)))
P("  only=%s" % only)

P("")
P("【6】工作区状态")
st = subprocess.run(["git", "-C", REPO, "status", "--porcelain"], capture_output=True)
P(st.stdout.decode("utf-8", "replace").strip() or "  (干净)")

P("")
P("【7】各段体积")
secs = re.split(r"(?m)^(##\s+\d+\..*)$", t)
if secs and secs[0].strip():
    P("  前言: %d" % js_len(secs[0]))
for i in range(1, len(secs) - 1, 2):
    P("  %-30s %d" % (secs[i].strip()[:30], js_len(secs[i] + secs[i + 1])))
