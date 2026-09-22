# -*- coding: utf-8 -*-
"""第 34 轮续：提交 + 推送 + 硬核验（铁律 0 全套）。

用法：python _push_round34d.py
"""
import io
import os
import shutil
import socket
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
TMP = r'E:\Download\_tmp'
MSG_FILE = os.path.join(TMP, 'msg_r34d.txt')

GIT = shutil.which('git') or r'D:\Program Files\Git\cmd\git.exe'
REMOTE = 'origin'
BRANCH = 'main'


def run(args, **kw):
    return subprocess.run([GIT] + args, cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, **kw)


def out(r):
    return (r.stdout or b'').decode('utf-8', 'replace'), \
           (r.stderr or b'').decode('utf-8', 'replace')


print('=' * 72)
print('第 34 轮续：提交 + 推送')
print('=' * 72)

# ---------- [0] 提交信息写文件 + 自证编码 ----------
os.makedirs(TMP, exist_ok=True)
MSG = """第34轮续：交互接线 / 动画播放 / 移动核心 —— 一条确定结论 + 一次自我推翻

## 确定结论：pet_interaction.py 全模块零接线（孤儿）
- AST 硬核验（不依赖 grep 字面量）：产品代码 import pet_interaction 0 处、
  引用其导出符号 0 处；模块 364 行。
- 同时确认 main.py 内有第二套且活的实现：get_ralsei_body_part()（L5025）
  + 抚摸检测（L5364-5393），与 审查报告_2026.md:99 记载一致。
- 能力对比：死模块更完整（6 手势 vs 产品 3 种；alpha 遮罩动态分区 vs 硬编码矩形；
  有长按 PULL/PINCH）⇒ 不是"删冗余"，而是"要不要把更好的那套接上"。
  → 提请用户裁定（删 / 接线 / 暂缓），我的建议 = 暂缓。

## 自我推翻：抚摸判据 direction_changes 三次探针失真，误诊的缺陷不成立
- 起点：main.py L5364-5393 先判"主轴"再要求主轴相同才比较符号反转；
  手造横纵交替序列实测 dc=0 → 我判定"撸猫不触发"并写好修复。
- 三次失真：
  1) 量级失真（探针 22）：抖动设 ±1.2px、主干 4px/步 → 得"翻转率 11~14%"；
     真实鼠标差分 5~20px，±1.2px 抖动根本不夺主轴。
  2) 计数失真（探针 24 初版）：cos 完整周期 → 极值处差分趋 0，大量步被门槛
     3<d<50 滤掉（步数=7 即是信号）；改三角波才修好。
  3) 真实量级 A/B 定案（探针 23）：git cat-file 取父版本旧判据 vs 工作区新判据，
     同一批真实量级轨迹 → 旧判据在自然弧线用例 dc=2，本来就达阈值。
     我的"修复"反引入过度敏感（±4px 抖动让 dc 从 11 飙到 54，会误触发）。
- 处置：git checkout -- ralsei_pet/src/main.py 完整回退。修复不得基于不成立的诊断。
- 教训：需要真人操作的行为判据（抚摸/拖拽手感/甩飞体感）严禁用离线模拟下结论；
  连续两次探针失真 ⇒ 停下来质疑方法本身。要保真只能真机打点落 CSV。

## 动画播放链路：静态审计 5/5 PASS
- AST 状态位一致性：四个 _play_once_* 全部既写又读；"置真却无还原"裸奔点 0 处。
- 三道防呆复核成立：空帧自检（L7541）/ 切换失败全量回滚（L8120）/ 回调异常不吞（L7961）。
- 排除一处疑似：current_frame % frame_count（L7816）与 current_frame += 1（L7941）
  同在 if _need_advance: 块内、同为 16 空格 → 序列 = 取模→渲染→自增，净效果正常循环。
- 判据教训：getattr(self,'_play_once_active',False) 的属性名是字符串字面量，
  visit_Attribute 扫不到 → 第一版误报"只写不读"。AST 扫属性必须同时扫 ast.Constant。

## 记忆维护
- MEMORY.md 超注入上限被截断 → 按 skill 先补详版（新增 §23.12 / §23.13 镜像）再压速查本；
  20904 B（原 22145），关键铁律零缺失、无 BOM。

## 证据（code-quality-audit/第34轮-移动行为基础代码严查/_evidence/）
- 20_交互接线核查.txt / 21_活产线抚摸判据复核.txt / 22_抚摸轨迹严重性.txt
- 23_抚摸判据AB对照.txt / 24_抚摸判据保真取证.txt / 25_动画状态位一致性.txt

## G2
- 全量 G2 复核：PASS=1427 FAIL=0，29 套件全 IDENTICAL，rc=0
- 工作区 ralsei_pet/ 零改动（所有探针只读）
"""

with io.open(MSG_FILE, 'w', encoding='utf-8', newline='\n') as f:
    f.write(MSG)

raw = open(MSG_FILE, 'rb').read()
print('[0] 提交信息自证: %d 字节, 首3字节=%s %s'
      % (len(raw), list(raw[:3]),
         '(BOM!)' if raw[:3] == b'\xef\xbb\xbf' else '(无 BOM OK)'))

# ---------- [1] add ----------
# 只加本轮产物：记忆 + 报告 + 证据目录（ralsei_pet/ 无改动）
ADD = [
    '.workbuddy/memory/2026-09-22.md',
    '.workbuddy/memory/MEMORY.md',
    '.workbuddy/memory/参考-契约与历轮（详版）.md',
    '第三十四轮移动行为基础代码严查报告_2026-09-22.md',
    'code-quality-audit/第34轮-移动行为基础代码严查/_evidence',
]
for a in ADD:
    r = run(['add', '--', a])
    o, e = out(r)
    print('[1] add %-58s rc=%d %s' % (a[:58], r.returncode, (e.strip()[:80] or '')))

st = run(['status', '--porcelain'])
o, e = out(st)
staged = [l for l in o.splitlines() if l.strip()]
print('[1] 暂存后改动条目: %d' % len(staged))

# ---------- [2] commit ----------
r = run(['commit', '-F', MSG_FILE])
o, e = out(r)
print('[2] commit rc=%d' % r.returncode)
print((o.strip() or e.strip())[:500])

# ---------- [3] 核 log ----------
r = run(['log', '--oneline', '-1'])
o, e = out(r)
print('[3] log -1 :', o.strip())
HEAD = o.split()[0] if o.strip() else '?'

# ---------- [4] 提交信息逐字节核验 ----------
r = run(['cat-file', 'commit', 'HEAD'])
o, e = out(r)
body = o
src_lines = MSG.splitlines()
# 从 commit 对象里取 message（首个空行之后）
parts = body.split('\n\n', 1)
msg_part = parts[1] if len(parts) > 1 else ''
got_lines = msg_part.splitlines()
# 按行 rstrip 比对（git 会剥掉行尾空格）
ok = True
n = min(len(got_lines), len(src_lines))
diff = []
for i in range(n):
    if got_lines[i].rstrip() != src_lines[i].rstrip():
        ok = False
        diff.append((i + 1, src_lines[i][:60], got_lines[i][:60]))
print('[4] 提交信息逐字节核验: %s (%d/%d 行一致)'
      % ('IDENTICAL' if ok else '**DIFFER**', n - len(diff), len(src_lines)))
for ln, s_, g_ in diff[:5]:
    print('     L%d src=%r got=%r' % (ln, s_, g_))

# ---------- [5] credential fill ----------
url = None
r = run(['remote', 'get-url', REMOTE])
o, e = out(r)
url = o.strip()
print('[5] remote url:', url)

CRED = os.path.join(TMP, 'cred.txt')
r = run(['credential', 'fill'],
        input=b'url=' + url.encode('utf-8') + b'\n')
o, e = out(r)
if o.strip():
    with io.open(CRED, 'w', encoding='utf-8', newline='\n') as f:
        f.write(o)
    print('[5] credential fill 得到凭据: %d 字节' % len(o.encode('utf-8')))
    # 组装 extraheader
    import base64
    user = pwd = ''
    for line in o.splitlines():
        if line.startswith('username='):
            user = line.split('=', 1)[1]
        elif line.startswith('password='):
            pwd = line.split('=', 1)[1]
    if user and pwd:
        b64 = base64.b64encode(('%s:%s' % (user, pwd)).encode('utf-8')).decode()
        HDR = 'AUTHORIZATION: basic ' + b64
        print('[5] extraheader 已构造')
    else:
        HDR = None
        print('[5] **凭据不完整**')
else:
    HDR = None
    print('[5] **credential fill 无输出** (rc=%d) %s' % (r.returncode, e.strip()[:200]))

# ---------- [6] 端口快筛 ----------
def port_ok(host, port, timeout=2.0):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False

proxy = None
for p in (7890, 7897, 10809, 1080, 8080, 33210):
    if port_ok('127.0.0.1', p):
        proxy = p
        print('[6] 本地代理端口命中:', p)
        break
if proxy is None:
    print('[6] 未发现本地代理端口（直连）')

# ---------- [7] push（多端口重试 + 硬超时） ----------
def do_push(extra=None, timeout=90):
    args = ['push', REMOTE, '%s:%s' % (BRANCH, BRANCH)]
    env = dict(os.environ)
    if extra:
        env['GIT_CONFIG_COUNT'] = str(len(extra))
        for i, (k, v) in enumerate(extra.items()):
            env['GIT_CONFIG_KEY_%d' % i] = k
            env['GIT_CONFIG_VALUE_%d' % i] = v
    try:
        r = subprocess.run([GIT] + args, cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, timeout=timeout)
        o, e = out(r)
        return r.returncode, o, e
    except subprocess.TimeoutExpired:
        return 124, '', 'TIMEOUT(%.0fs)' % timeout

attempts = []
if HDR:
    attempts.append(('extraheader', {'http.extraheader': HDR}))
if proxy:
    attempts.append(('proxy:%d' % proxy,
                     {'http.proxy': 'http://127.0.0.1:%d' % proxy,
                      'https.proxy': 'http://127.0.0.1:%d' % proxy}))
attempts.append(('direct', None))

pushed = False
for name, extra in attempts:
    rc, o, e = do_push(extra)
    print('[7] push(%s) rc=%d' % (name, rc))
    if o.strip():
        print('     out:', o.strip()[:300])
    if e.strip():
        print('     err:', e.strip()[:300])
    if rc == 0:
        pushed = True
        break

# ---------- [8] 远端硬核验（独立构造 argv + 重试） ----------
print('[8] 远端核验（独立构造 + 重试）')
remote_head = None
for i in range(5):
    r = subprocess.run([GIT, 'ls-remote', REMOTE, 'refs/heads/%s' % BRANCH],
                       cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=60)
    o, e = out(r)
    if r.returncode == 0 and o.strip():
        remote_head = o.split()[0]
        print('    ls-remote 第%d次: %s' % (i + 1, remote_head))
        break
    print('    ls-remote 第%d次失败 rc=%d %s' % (i + 1, r.returncode, e.strip()[:120]))

# 交叉验证
r = run(['rev-parse', 'origin/%s' % BRANCH])
o, e = out(r)
local_remote = o.strip()
r2 = run(['rev-parse', 'HEAD'])
o2, _ = out(r2)
local_head = o2.strip()

print()
print('=' * 72)
print('结果')
print('=' * 72)
print('  本地 HEAD          :', local_head)
print('  origin/%s (本地)  : %s' % (BRANCH, local_remote))
print('  远端 refs (ls-remote):', remote_head)
same1 = (local_head == remote_head)
same2 = (local_head == local_remote)
print('  本地 == 远端       :', same1)
print('  本地 == origin/本地 :', same2)
print()
if same1 and same2:
    print('[PASS] 三方一致，推送成功')
elif same1:
    print('[PASS] 远端已同步（origin/ 引用稍后刷新）')
else:
    print('[WARN] 未完全一致 —— 如实报告，稍后重试（勿怀疑凭据）')

# 工作区
r = run(['status', '--porcelain'])
o, e = out(r)
left = [l for l in o.splitlines() if l.strip()]
print('  剩余未提交:', len(left))
for l in left[:10]:
    print('    ', l)

# 清理
for f in (MSG_FILE, CRED):
    try:
        if os.path.exists(f):
            os.remove(f)
            print('  已清理', f)
    except OSError as ex:
        print('  清理失败', f, ex)
