#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 探针 E：真机自检 —— 起 App、抓输出、杀干净。

为什么必须真机：本项目多次证明"函数写对了 ≠ 产品用上了"，
只有真的把 `src/main.py` 跑起来才能看到
  · import 期崩溃 / 缺素材
  · 建窗口、建 NPC 服务、建场景系统时的异常
  · 静默降级告警（"xxx 不可用"）

口径（沿用 desktop-app-live-verification + 本项目铁律）：
  · 输出落 `%TEMP%`（**不落 E 盘**：本次普查实测 E 盘重定向会间歇性 OSError）
  · 用后即杀，且**只杀 cmdline 命中 src\\main.py 的进程**，绝不误杀本探针自己
  · 判据必须是"产物"而非"源码"：看真实 stdout/stderr 里有没有 Traceback

用法：C:\\Python311\\python.exe probe_live60.py [等待秒数]
"""
import io
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
PET = os.path.join(REPO, 'ralsei_pet')
SCRIPT = os.path.join(PET, 'src', 'main.py')
PY = r'C:\Python311\python.exe'
WAIT = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0


def check(cond, msg):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', msg))
    return bool(cond)


def C(*cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace')


def find_running():
    """只找 cmdline 命中 main.py 的 python 进程。"""
    try:
        import psutil
    except Exception:
        out = C('wmic', 'process', 'where', "name='python.exe'", 'get',
                'ProcessId,CommandLine', '/format:list').stdout or ''
        pids = []
        cur = {}
        for ln in out.splitlines():
            ln = ln.strip()
            if not ln:
                if cur.get('cmd', '').replace('/', '\\').endswith('src\\main.py'):
                    pids.append(cur.get('pid'))
                cur = {}
                continue
            if ln.startswith('CommandLine='):
                cur['cmd'] = ln.split('=', 1)[1]
            elif ln.startswith('ProcessId='):
                cur['pid'] = ln.split('=', 1)[1]
        return [p for p in pids if p]
    pids = []
    for pr in psutil.process_iter(['pid', 'cmdline']):
        try:
            cl = ' '.join(pr.info.get('cmdline') or [])
        except Exception:
            continue
        if cl.replace('/', '\\').endswith('src\\main.py'):
            pids.append(pr.info['pid'])
    return pids


def kill(pids):
    if not pids:
        return
    try:
        import psutil
        for pid in pids:
            try:
                psutil.Process(pid).terminate()
            except Exception:
                pass
        gone, alive = psutil.wait_procs(
            [psutil.Process(p) for p in pids if psutil.pid_exists(p)], timeout=8)
        for pr in alive:
            try:
                pr.kill()
            except Exception:
                pass
        return
    except Exception:
        pass
    for pid in pids:
        C('taskkill', '/PID', str(pid), '/T', '/F')


def main():
    tmp = tempfile.gettempdir()
    outf = os.path.join(tmp, 'ralsei_live60.out.txt')
    errf = os.path.join(tmp, 'ralsei_live60.err.txt')
    print('=' * 72)
    print('探针 E —— 真机自检（起 App / 抓输出 / 杀干净）')
    print('脚本 %s' % SCRIPT)
    print('输出落 %s（不落 E 盘）' % tmp)
    print('=' * 72)

    ok = True
    ok &= check(os.path.isfile(SCRIPT), 'E1 入口脚本存在：%s' % SCRIPT)
    if not ok:
        return 1

    stale = find_running()
    print('      开跑前发现的在跑实例：%s' % (stale or '无'))
    if stale:
        kill(stale)
        time.sleep(1.5)
        ok &= check(not find_running(), 'E2 旧实例已清干净（单实例锁不会被旧进程占住）')

    fo = io.open(outf, 'wb')
    fe = io.open(errf, 'wb')
    t0 = time.time()
    proc = subprocess.Popen([PY, SCRIPT], cwd=PET, stdout=fo, stderr=fe,
                            stdin=subprocess.DEVNULL, env=dict(
                                os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1'))
    print('      已启动 pid=%s，等待 %.0fs …' % (proc.pid, WAIT))
    time.sleep(WAIT)

    alive = proc.poll() is None
    if alive:
        # 正常情况：GUI 事件循环还在跑 ⇒ 活着才对
        kill([proc.pid])
    fo.close()
    fe.close()
    time.sleep(0.5)

    out = io.open(outf, encoding='utf-8', errors='replace').read()
    err = io.open(errf, encoding='utf-8', errors='replace').read()
    dur = time.time() - t0
    print('      运行 %.1fs；退出码=%s（None=被我们主动结束）' % (dur, proc.poll()))
    print('      stdout %d 字符 / stderr %d 字符' % (len(out), len(err)))

    def has_trace(t):
        return ('Traceback (most recent call last)' in t) or ('Traceback' in t and 'File "' in t)

    if out.strip():
        print('      ---- stdout 尾部 ----')
        for ln in out.strip().splitlines()[-20:]:
            print('      | %s' % ln[:160])
    if err.strip():
        print('      ---- stderr 尾部 ----')
        for ln in err.strip().splitlines()[-20:]:
            print('      | %s' % ln[:160])

    ok &= check(not has_trace(out), 'E3 stdout 里没有 Traceback')
    ok &= check(not has_trace(err), 'E4 stderr 里没有 Traceback')
    ok &= check(alive, 'E5 存活到我们主动结束（提前退出往往意味着启动即崩）')
    ok &= check(len(out) > 0 or len(err) > 0,
                'E6 有输出（0 输出=没真跑起来，是"假绿"的典型）')

    # ★★ 第60轮补：只看 Traceback 是**判据过窄** —— 本探针 v1 就是这样放过了一批
    #    `[ERROR] 保存配置文件失败: [WinError 5] 拒绝访问` 的（App 照跑，但状态没落盘）。
    #    "进程还活着" ≠ "功能正常"。
    err_lines = [ln for ln in (out + '\n' + err).splitlines()
                 if '[ERROR]' in ln or 'Traceback' in ln or 'WinError' in ln
                 or 'Errno 13' in ln or 'Permission denied' in ln]
    print('      ---- 硬错误行（[ERROR]/WinError/Errno13）共 %d 条 ----' % len(err_lines))
    for ln in err_lines[:12]:
        print('      ! %s' % ln[:170])
    ok &= check(not err_lines,
                'E7 运行期没有硬错误日志（实际 %d 条）—— 「进程活着」不等于「功能正常」'
                % len(err_lines))

    os.makedirs(os.path.join(ROUND, '_evidence'), exist_ok=True)
    dst = os.path.join(ROUND, '_evidence', 'live60.txt')
    with io.open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write('=== 真机自检 raw ===\n')
        f.write('exit=%s dur=%.1fs\n' % (proc.poll(), dur))
        f.write('--- stdout ---\n%s\n--- stderr ---\n%s\n' % (out, err))
    print('      证据：%s' % dst.replace('\\', '/'))
    print('=' * 72)
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
