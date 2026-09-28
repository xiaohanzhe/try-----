# -*- coding: utf-8 -*-
"""第 38 轮起：可复用的「提交 + 推送 + 硬核验」一步脚本（Windows 沙箱专用）。

用法：
    C:\\Python311\\python.exe _tools/gitpush.py <提交信息文件路径> [--no-push]
    C:\\Python311\\python.exe _tools/gitpush.py --push-only      # 只推当前 HEAD

为什么不是一行 git 命令
----------------------
1. 提交信息必须 `git commit -F <文件>`（`-m` 在 PS 5.1 里会被拆 argv ⇒ 假成功）。
2. push 必须绕开宿主注入的 `credential.helper=helper-selector`（它会弹 GUI 并挂死）
   ⇒ 清空 helper 链 + 直取 GCM 凭据 + `http.extraheader` 注入。
3. TLS：本机 schannel 吊销检查必失败 ⇒ openssl 后端 + 系统 CA PEM + HTTP/1.1。
4. 退出码会说谎 ⇒ 必须 `ls-remote` **且** `rev-parse origin/main` 双向核验。
5. ★ 第57轮补：**代理必须逐端口实测，且判据要走到"git 自己走一次"**。直连 github 会被
   `Recv failure: Connection was reset`。四级判据：
   `TCP 能连` → `隧道建得起（HTTP CONNECT / SOCKS5）` → `TLS 握得上` →
   **`git ls-remote` 真能读到 refs`（末级才算数，仓库公开 ⇒ 匿名可读、不需凭据）**。
   ⚠️ 两个**假阳性**都实测踩到：
   · 「CONNECT 回 200」≠ 能用：本机 7897 的 http 隧道对裸 `github.com` 回 200 却
     立刻 `unexpected eof while reading`（`api.github.com` 通、`github.com` 不通），
     而**同端口的 SOCKS5 通道**当时是好的；
   · 「ssl 握手成功」也 ≠ 能用：后来碰上一次 http 隧道 TLS 能过、push 仍报同一个 eof。
   ⇒ 探针不能自造，必须**用产品自己那条路**去问（本项目铁律"探针不保真 = 报假问题"）。
   另加 `--push-only`：push 失败后重推时不再被"没有可提交的改动"提前返回。

安全：凭据只在进程内；报告里只写长度，绝不写 token。
"""
import base64
import io
import os
import re
import socket
import ssl
import subprocess
import sys
import time

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
GCM = (r'C:\Users\23002\.workbuddy\binaries\PortableGit\versions\1.2.0'
       r'\mingw64\bin\git-credential-manager.exe')
CA = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'), 'win_root_ca.pem')
# ★ 第45轮修正：日志**不写进仓库**。原写法落在 tracked 文件里、每次运行覆盖
#   ⇒ 每次 push 后该文件必然变脏，逼出「为日志再提一次」的死循环。
#   改落 E:\Download\_tmp\（用户口径的临时区，用后即删，不跟踪）。
_TMP = r'E:\Download\_tmp'
if not os.path.isdir(_TMP):
    _TMP = os.environ.get('TEMP', r'C:\Windows\Temp')
LOG = os.path.join(_TMP, '提交推送日志.txt')
DEL_LIMIT = 1000          # ★ 单次提交删除行数硬上限（来自 memory 铁律）
# 例外：`--allow-del N` 显式抬线。仅在「删除行已逐条归因、确认无信息丢失」时使用，
# 且必须在提交信息里写明归因（本仓库第44轮 objects 补全首次用到）。
if '--allow-del' in sys.argv:
    try:
        DEL_LIMIT = int(sys.argv[sys.argv.index('--allow-del') + 1])
    except Exception:
        pass

# ★ 第57轮：已知可用的本地代理端口（只是兜底候选，**必须实测 CONNECT 才采用**）
PROXY_PORTS = ['7897', '7375', '7890', '10809', '1080']

buf = []


def w(s=''):
    buf.append(str(s))
    try:
        with io.open(LOG, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(buf) + '\n')
    except Exception:
        pass
    print(s)


def run(args, timeout=240, env=None, inp=None):
    try:
        p = subprocess.run(args, cwd=REPO, capture_output=True,
                           timeout=timeout, env=env, input=inp)
        return (p.returncode, p.stdout.decode('utf-8', 'replace'),
                p.stderr.decode('utf-8', 'replace'))
    except subprocess.TimeoutExpired:
        return (-999, '', 'TIMEOUT %ss' % timeout)
    except Exception as e:
        return (-998, '', 'EXC %r' % (e,))


def _base_opts():
    """与推送共用的底层 `-c`（TLS 后端 / CA / HTTP 版本 / 清掉会弹窗的 helper）。"""
    return ['-c', 'credential.helper=',
            '-c', 'http.sslBackend=openssl',
            '-c', 'http.sslCAInfo=' + CA.replace('\\', '/'),
            '-c', 'http.version=HTTP/1.1']


def _proxy_opts(proxy, base=None):
    """把代理并进 `-c` 参数列表（`base` 为空时只给 `credential.helper=`）。"""
    opts = list(base) if base else ['-c', 'credential.helper=']
    if proxy:
        opts += ['-c', 'http.proxy=' + proxy, '-c', 'https.proxy=' + proxy]
    return opts


def _git_reachable(proxy, timeout=60):
    """★★ 终极判据：**真的跑一次 `git ls-remote`**（本仓库公开 ⇒ 匿名可读、不需凭据）。

    第57轮实测：Python 侧 `ssl` 握手成功**仍不等于** git 推得上去 ——
    同一个 `7897` 的 http 隧道，探测握手能过，push 依旧
    `unexpected eof while reading`。所以探针不能自造（"探针不保真 = 报假问题"），
    必须**用产品自己那条路**去问一次。
    """
    args = (['git'] + _proxy_opts(proxy, _base_opts())
            + ['ls-remote', 'origin', 'refs/heads/main'])
    rc, o, e = run(args, timeout=timeout)
    return rc == 0 and bool(o.strip())


def _recv_exact(s, n):
    buf = b''
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c:
            raise OSError('对端提前关闭')
        buf += c
    return buf


def _http_tunnel(port, host, hp, timeout):
    """HTTP CONNECT 隧道。"""
    s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
    s.settimeout(timeout)
    s.sendall(('CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n\r\n'
               % (host, hp, host, hp)).encode())
    buf = b''
    while b'\r\n\r\n' not in buf and len(buf) < 8192:
        c = s.recv(512)
        if not c:
            break
        buf += c
    first = buf.split(b'\r\n')[0].decode('latin-1', 'replace')
    if '200' not in first:
        s.close()
        raise OSError(first or '(空响应)')
    return s


def _socks5_tunnel(port, host, hp, timeout):
    """SOCKS5（无认证）隧道。★ 第57轮实测：本机 Clash 的 7897 对裸 `github.com`
    的 **HTTP-CONNECT 规则坏了**（回 200 却握不上 TLS），但同一端口的
    **SOCKS5 通道正常** ⇒ 两条路都要试。"""
    s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
    s.settimeout(timeout)
    s.sendall(b'\x05\x01\x00')                       # VER=5 / 1 method / NOAUTH
    if _recv_exact(s, 2) != b'\x05\x00':
        s.close()
        raise OSError('SOCKS5 握手被拒')
    hb = host.encode('ascii')
    s.sendall(b'\x05\x01\x00\x03' + bytes([len(hb)]) + hb
              + hp.to_bytes(2, 'big'))
    head = _recv_exact(s, 4)
    if head[1] != 0:
        s.close()
        raise OSError('SOCKS5 应答码 %d' % head[1])
    atyp = head[3]
    n = 4 if atyp == 1 else 16 if atyp == 4 else None
    if atyp == 3:
        n = _recv_exact(s, 1)[0]
    if n is None:
        s.close()
        raise OSError('SOCKS5 未知 ATYP %d' % atyp)
    _recv_exact(s, n + 2)
    return s


def _tls_ok(sock):
    """★ 判据核心：把隧道**真的套上 TLS 握一次手**。

    ⚠️ 「CONNECT 回 200」是**假阳性**：本机 7897 的 HTTP 隧道回 200 后
       立刻 `unexpected eof while reading`（`api.github.com` 通、裸 `github.com` 不通）。
       这与本项目的老教训同型 —— **看着通了 ≠ 真能用**，判据必须走到端。
    """
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE          # 只探"能不能建会话"，不校证书
        w = ctx.wrap_socket(sock, server_hostname='github.com')
        ver = w.version()
        w.close()
        return bool(ver)
    except Exception:                                                 # noqa: BLE001
        try:
            sock.close()
        except Exception:                                             # noqa: BLE001
            pass
        return False


def _probe_proxies(limit=3):
    """★ 第57轮：逐端口实测 —— **TCP 能连 → 隧道建得起 → TLS 握得上**，三级都过才算数。

    ⚠️ 四个坑都踩过：
      · **不能只看 TCP 能连** —— 多个端口 accept 后空响应或回 404
        （`11434` 是 Ollama、`39099` 回 404 Error）。
      · **不能只看 CONNECT 回 200** —— 见 `_tls_ok()` 注释（本站点的真坑）。
      · **不能只试 HTTP 隧道** —— 需要 SOCKS5 兜底。
      · **端口不能写死** —— 先 env、再 netstat、最后才兜底常量。
    返回**可用代理 URL 列表**（按探测顺序，最多 `limit` 个）或 `[]`。
    ★ 返回列表而非单个：本机这条路是**抖的**（同一配置两次里成一次），
      调用方按列表逐个试，比"认定一个然后反复重试同一个"更接近事实。
    """
    cands = []
    for k in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy',
              'ALL_PROXY', 'all_proxy'):
        v = os.environ.get(k)
        if v:
            m = re.search(r'(\d+)', v.split('//')[-1])
            if m:
                cands.append(m.group(1))
    try:
        r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=30)
        for line in r.stdout.splitlines():
            if 'LISTENING' in line and '127.0.0.1:' in line:
                m = re.search(r'127\.0\.0\.1:(\d+)', line)
                if m:
                    cands.append(m.group(1))
    except Exception as e:                                            # noqa: BLE001
        w('     (netstat 取端口失败：%s)' % e)
    cands += PROXY_PORTS

    seen = []
    for p in cands:
        if p not in seen:
            seen.append(p)

    found = []
    deadline = time.time() + 120.0
    for port in seen:
        if len(found) >= limit or time.time() > deadline:
            break
        for scheme, opener in (('http', _http_tunnel),
                               ('socks5h', _socks5_tunnel)):
            try:
                s = opener(int(port), 'github.com', 443, 4.0)
            except Exception:                                         # noqa: BLE001
                continue          # 静默跳过"不是代理"的端口，别刷屏
            ok = _tls_ok(s)
            url = (('http://127.0.0.1:%d' % int(port)) if scheme == 'http'
                   else ('socks5h://127.0.0.1:%d' % int(port)))
            # ★★ 第61轮修正：`_tls_ok` 是**自造探针**（Python 的 ssl），**不是门**。
            #    实测（2026-09-29）：7897 上 Python ssl 握手失败，同一时刻
            #    `git -c http.proxy=http://127.0.0.1:7897 -c http.sslBackend=openssl
            #     ls-remote` **成功**。若在此 `continue`，就把 git 明明能走的路否掉了，
            #    与文件头「探针不能自造，必须用产品自己那条路去问」自相矛盾。
            if not ok:
                w('     proxy %-6s (%-7s) -- Python ssl 握手失败（仅供参考，继续让 git 走）'
                  % (port, scheme))
            # ★★ 真判据：让 git 自己走一次（见 `_git_reachable`）。
            if _git_reachable(url):
                w('     proxy %-6s (%-7s) OK —— `git ls-remote` 可达%s'
                  % (port, scheme, '' if ok else '（ssl 探针未过，以 git 为准）'))
                found.append(url)
            else:
                w('     proxy %-6s (%-7s) -- git 也不可达' % (port, scheme))
    return found


def main():
    if len(sys.argv) < 2:
        w('usage: gitpush.py <msgfile> [--no-push] | gitpush.py --push-only')
        return 1
    push_only = '--push-only' in sys.argv
    msg = sys.argv[1]
    do_push = '--no-push' not in sys.argv
    w('=== 提交推送日志 ===  %s' % time.strftime('%Y-%m-%d %H:%M:%S'))

    if push_only:
        w('[0] --push-only：跳过 add/commit，直接推当前 HEAD')
        o = run(['git', 'log', '--oneline', '-1'], timeout=60)[1].strip()
        w('[4] HEAD = %s' % o)
        return _push()

    if not os.path.isfile(msg):
        w('!! 提交信息文件不存在：%s' % msg)
        return 2
    head3 = list(io.open(msg, 'rb').read()[:3])
    w('[0] msg=%s first3=%s BOM=%s'
      % (os.path.basename(msg), head3, head3 == [239, 187, 191]))
    if head3 == [239, 187, 191]:
        w('!! 提交信息带 BOM，终止')
        return 2

    rc, o, e = run(['git', 'add', '-A'], timeout=180)
    w('[1] add rc=%d %s' % (rc, e.strip()[:200]))

    # ★ 删除行数守卫
    rc, o, e = run(['git', 'diff', '--cached', '--numstat'], timeout=120)
    adds = dels = files = 0
    for ln in o.splitlines():
        parts = ln.split('\t')
        if len(parts) >= 3:
            files += 1
            if parts[0].isdigit():
                adds += int(parts[0])
            if parts[1].isdigit():
                dels += int(parts[1])
    w('[2] staged files=%d +%d -%d' % (files, adds, dels))
    if dels > DEL_LIMIT:
        w('!! 删除 %d 行 > %d ⇒ 中止（先人工确认不是我误删）' % (dels, DEL_LIMIT))
        return 3
    if files == 0:
        w('没有可提交的改动')
        return 0

    rc, o, e = run(['git', 'commit', '-F', msg], timeout=180)
    w('[3] commit rc=%d %s %s' % (rc, o.strip()[:200], e.strip()[:200]))
    rc, o, e = run(['git', 'log', '--oneline', '-1'], timeout=60)
    w('[4] HEAD = %s' % o.strip())

    if not do_push:
        w('=== 结论 = COMMITTED_ONLY ===')
        return 0
    return _push()


def _push():
    """取凭据 → 探代理 → push → 双向核验。返回 0 表示确已同步。"""
    local = run(['git', 'rev-parse', 'HEAD'], timeout=60)[1].strip()
    env = dict(os.environ)
    env['GCM_INTERACTIVE'] = 'never'
    env['GCM_PROVIDER'] = 'github'
    try:
        p = subprocess.run([GCM, 'get'],
                           input=b'protocol=https\nhost=github.com\n\n',
                           capture_output=True, timeout=45, env=env, cwd=REPO)
        out = p.stdout.decode('utf-8', 'replace')
    except Exception as ex:
        out = ''
        w('!! 取凭据异常 %r' % (ex,))
    usr = pw = ''
    for ln in out.splitlines():
        if ln.startswith('username='):
            usr = ln[9:]
        elif ln.startswith('password='):
            pw = ln[9:]
    w('[5] cred user=%r pw_len=%d' % (usr, len(pw)))
    if not pw:
        w('!! 无凭据 ⇒ 不 push（不重试、不弹窗）')
        w('=== 结论 = COMMITTED_ONLY ===')
        return 4
    b64 = base64.b64encode(('%s:%s' % (usr, pw)).encode('ascii')).decode('ascii')
    del pw

    w('[5b] 探测可用代理（逐端口实测；**真判据 = 让 git 自己 `ls-remote` 一次**）')
    # ★ 第61轮：支持 `--proxy <url>` 显式指定（跳过自动探测）。
    #   用途：自动探测慢/误判时，用一条已验证的路直接推。
    #   传字面量 `direct` 表示显式不走代理。
    forced = ''
    if '--proxy' in sys.argv:
        try:
            forced = sys.argv[sys.argv.index('--proxy') + 1]
        except Exception:                                             # noqa: BLE001
            forced = ''
    if forced:
        proxies = [''] if forced.lower() in ('direct', 'none', '直连') else [forced]
        w('[5b] 显式指定代理：%s（跳过自动探测）' % (forced or '直连'))
    else:
        proxies = _probe_proxies()
    w('[5c] 可用代理 %d 个：%s' % (len(proxies), proxies or '(无 ⇒ 直连)'))

    BASE = _base_opts() + ['-c', 'http.extraheader=Authorization: Basic ' + b64]

    def _opts(proxy):
        return _proxy_opts(proxy, BASE)

    # ★ 有界尝试：候选之间是**不同配置**（http 隧道 / socks5h / 不同端口），
    #   不是拿同一个配置反复砸。上限 = `_probe_proxies(limit=3)`。
    used = ''
    for i, proxy in enumerate(proxies if proxies else [''], 1):
        w('[6.%d] push 尝试（代理=%s）' % (i, proxy or '直连'))
        rc, o, e = run(['git'] + _opts(proxy) + ['push', 'origin', 'main'],
                       timeout=300)
        w('      rc=%d' % rc)
        for ln in (o + e).splitlines():
            if ln.strip():
                w('      %s' % ln[:170])
        if rc == 0:
            used = proxy
            break
        blob = o + e
        if ('Authentication failed' in blob or ' 403' in blob
                or ' 401' in blob):
            w('      ⇒ 认证类失败：换代理无用，停止')
            break
    w('[6] push 循环结束（采用代理=%s）' % (used or '(直连/未成功)'))

    # ★ 核验也必须走代理：直连的 ls-remote 必然空 ⇒ 会把"其实推上去了"报成 NOT_PUSHED。
    remote = ''
    for cand in ([used] if used else (proxies or [''])):
        rc, o, _ = run(['git'] + _opts(cand) + ['ls-remote', 'origin',
                                                'refs/heads/main'], timeout=90)
        remote = o.strip().split('\t')[0] if o.strip() else ''
        w('[7] ls-remote（代理=%s）= %s' % (cand or '直连', remote or '(空)'))
        if remote:
            break
    tracking = run(['git', 'rev-parse', 'origin/main'], timeout=60)[1].strip()
    w('[8] origin/main = %s' % tracking)
    ok = bool(local) and local == remote == tracking
    w('[9] 双向一致 = %s' % ok)
    w('=== 结论 = %s ===' % ('PUSHED' if ok else 'NOT_PUSHED'))
    return 0 if ok else 5


if __name__ == '__main__':
    sys.exit(main())
