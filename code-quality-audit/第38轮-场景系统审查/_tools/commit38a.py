# -*- coding: utf-8 -*-
"""第 38 轮开局：提交（+尝试推送一次）。

按 skill `win-git-utf8-push`：
  · 提交信息用 Write 写 UTF-8 **无 BOM** 文件 + `git commit -F`
  · 提交前看 `git diff --cached --numstat`，**出现 >1000 行 deletions 立刻停手**
  · 推送**只试一次**（绝不循环 —— 循环会反复弹 CredentialHelper GUI 骚扰用户）
"""
import io
import os
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MSG = r'E:\Download\_tmp\commit_msg_38a.txt'
PROXY = 'http://127.0.0.1:7897'
CA = r'E:/Download/_tmp/win_ca.pem'

TEXT = """场景系统：审查已写代码 + 抓出"场景数只有原作的 8%"这个 P0

用户口径（第 38 轮）：
  「那就正式开始构建咱那个场景系统吧，不过，在此之前，一定确保已编写的代码没错并且贴合功能要求哦」
  「你room太少了吧，5章加起来少说都要700左右」   ← 关键指正，成立

一、已写代码的正确性 —— 通过
  · 只读审查 21 项全 PASS（索引自洽 / 路由逐条体检 / 规则可达性 / bg 声明 vs 磁盘 /
    三处接线 / 宿主字段预声明完整）
  · 三层设计纪律均已落地：零依赖、算不出一律 None、坏规则跳过+未知键放行、双向转发双白名单

二、贴合功能要求 —— 不通过（用户指正成立，且比 700 更多）
  · 原作五章 data.win 实有 room 1,251（147/278/246/328/252）
  · 筛掉引擎占位/测试/调试/空房后"可当场景" = 1,032
  · 我们只登记了 87 ⇒ 覆盖 8.4%
  · 87 的来历（本轮反编译实证）：_original_rooms.json 是原作 scr_roomname() 的忠实转写，
    而 scr_roomname 只是"存档点地点名"函数，仅 20/20/9/20/26 = 95 条（含 5 个 --- ⇒ 90 个地点）
  · 逐 id 比对另抓到两个数据缺陷：
      ch2 多登记 2 条（id 199/200，无 scr_roomname 支持）
      ch5 漏登记 5 条（id 205/222/224/225/230，含 Top of Castle - Beginning 等关键地点）

三、P0 尚未接线（已知，P1 前必修）
  · 产品进程内实测 _scene_loaded=False、current_scene=None、self.scene.ready=False
  · main.py 里 self.scene.<方法>() 的调用点 = 0 ⇒ load() 从未被产品调用

四、复检（用户要求）
  · _tools/recheck38.py 六类判据 36 项全 PASS，证据落 _evidence/复检_第38轮开局.txt
  · 复检自身抓到 1 个真 bug（目录名拼错 ch2_windows）+ 3 个假红（判据自己说谎），
    全部按"先怀疑判据、再怀疑被测物"处置并留痕

本轮产物（全部只读审查，未改任何产品文件）：
  code-quality-audit/第38轮-场景系统审查/_tools/     8 个脚本（含复检脚本）
  code-quality-audit/第38轮-场景系统审查/_evidence/  11 份证据
  .workbuddy/memory/2026-09-23.md                    第 38 轮工作日志
"""

with io.open(MSG, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(TEXT)
raw = open(MSG, 'rb').read()
assert raw[:3] != b'\xef\xbb\xbf', 'BOM!'
print('msg bytes =', len(raw), 'bom =', raw[:3] == b'\xef\xbb\xbf')


def run(args, **kw):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, **kw)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), \
        r.stderr.decode('utf-8', 'replace')


rc, so, se = run(['git', 'add', '-A'])
print('add rc =', rc, se[:300])

rc, so, se = run(['git', 'diff', '--cached', '--numstat'])
print('--- staged numstat ---')
print(so)
tot_del = 0
for ln in so.splitlines():
    p = ln.split('\t')
    if len(p) >= 3 and p[1].isdigit():
        tot_del += int(p[1])
print('total deletions =', tot_del)
if tot_del > 1000:
    print('!!! 停手：deletions > 1000，见铁律 !!!')
    sys.exit(2)

rc, so, se = run(['git', 'commit', '-F', MSG])
print('commit rc =', rc, so[:400], se[:400])

rc, so, se = run(['git', 'log', '--oneline', '-1'])
print('HEAD =', so.strip())

# --- 推送：只试一次（超时即放弃，绝不循环）---
try:
    rc, so, se = run(['git', '-c', 'http.proxy=' + PROXY,
                      '-c', 'https.proxy=' + PROXY,
                      '-c', 'http.sslBackend=openssl',
                      '-c', 'http.sslCAInfo=' + CA,
                      '-c', 'http.version=HTTP/1.1', 'push', 'origin', 'main'],
                     timeout=180)
    print('push rc =', rc)
    print('push out:', so[:600])
    print('push err:', se[:600])
except subprocess.TimeoutExpired:
    print('push TIMEOUT(180s) —— 按铁律 7.0：不重试，直接如实报告')
except Exception as e:
    print('push 异常:', type(e).__name__, e)

rc, so, se = run(['git', 'log', '--oneline', '-3'])
print('--- 最近 3 条 ---')
print(so)

