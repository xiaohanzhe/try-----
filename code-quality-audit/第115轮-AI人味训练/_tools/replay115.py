# -*- coding: utf-8 -*-
"""
第115轮后续 · **逐项重放录像**（把既有的真机录像脚本全部真跑一遍并汇总）

用户口径：「把咱目前所有轮…所有轮的改动都**逐项录屏测试**，测试完没问题再推进」

★ 为什么重放既有脚本、而不是新写一堆：
  那些 `rec*.py` 是**当年照着真机行为**写出来的（`pet.show()` + 抓帧 + 断言），
  重跑它们 = 用它当年的判据复核**今天**的代码 ⇒ 这是最保真的"逐项录屏回归"。
  新写脚本反而会引入"我猜的 API"。

★★★ 第115轮补正（**原头部声明是错的，必须记下来**）：
  首版头部写的是「各 rec*.py 自带 `RALSEI_DATA_DIR`→mkdtemp + `vault_root=None`」。
  实测**不成立**：11 个 `rec*.py` 里**只有 `rec114.py` 有沙箱**，
  `rec96/105/106/107/109~113` 全是裸跑；而且 `rec114` 那套也**不完整**。
  后果：那次重放**确实写进了用户真实的 `E:\RalseiMemory\`**
  （实测 `npc_memory/*.json` mtime = 2026-10-16 03:57:48、`npc_life.json` 03:57:48）。
  ⇒ 本版起，**沙箱由重放器统一注入**（不改各轮历史脚本，保持它们当年的样子）：
     `RALSEI_MEMORY_DIR`（★ 真源头，优先级最高）/ `RALSEI_DATA_DIR` /
     `RALSEI_DESKTOP` / 外加 `QT_QPA_PLATFORM=windows`。
  ⇒ 并且**不信自称**：跑前/跑后用 `_shared/vault_guard.py` 拍指纹比对，
     有差异就**非零退出并落盘**（详见 `_evidence/VAULT_GUARD.json`）。
  ★ 为什么少一个闸就漏：`data_store` 只是**包装层**，路径真源在 `memory_store`；
     记忆系统**直接**用 `memory_store`，绕开了对 `data_store.vault_root` 的猴补丁；
     `memory_store.find_device_dir()` 里 `RALSEI_MEMORY_DIR` 才是最上一道。

★ 诚实的覆盖面（不许含糊）：
  · **有录像脚本可重放的**：第96轮（用户视角）+ 第105~114轮 ⇒ 本脚本全跑；
  · **更早的轮次（34~95）**当年做过真机巡行/10 分钟监测，但**没留下可重跑脚本** ⇒
    它们的可视面只能由"合并录像器"覆盖（下一步做），数据面由 105 个 headless 套件守。
    ★ 这条要写进报告，不能拿 headless 冒充录屏。

每项记录：退出码 / PASS / FAIL / PNG 帧数 / 耗时 / 输出尾部。
产物：`_evidence/REPLAY115.json` + `.md`

用法：
    C:\\Python311\\python.exe replay115.py                 # 全跑
    C:\\Python311\\python.exe replay115.py --only rec107   # 单个
    C:\\Python311\\python.exe replay115.py --timeout 600   # 单项超时（秒）
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CQA = os.path.join(ROOT, 'code-quality-audit')
EV = os.path.join(ROUND, '_evidence')
PY = sys.executable

#: 既有真机录像脚本（轮次目录, 脚本相对轮次目录的路径）
RECORDERS = [
    ('第96轮-用户视角录制复核', '_tools/rec96.py'),
    ('第105轮-OneShot房间连接', '_tools/rec105.py'),
    ('第106轮-非瞬移与全屏化', '_tools/rec106.py'),
    ('第107轮-全屏化与全局缩放', '_tools/rec107.py'),
    ('第109轮-场景过渡动画', '_tools/rec109.py'),
    ('第110轮-画面比例砍半', '_tools/rec110.py'),
    ('第111轮-Niko家彩蛋', '_tools/rec111.py'),
    ('第112轮-桌面门渐显', '_tools/rec112.py'),
    ('第113轮-灵魂视角差事', '_tools/rec113.py'),
    ('第114轮-差事世界门控与派发', '_tools/rec114.py'),
]

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def frames_before(rdir):
    """该项 _evidence 下已有多少 PNG（用来算"本次新增"）。"""
    ev = os.path.join(CQA, rdir, '_evidence')
    n = 0
    for base, _d, fs in os.walk(ev):
        n += sum(1 for f in fs if f.lower().endswith('.png'))
    return n


def main():
    args = sys.argv[1:]
    only = args[args.index('--only') + 1] if '--only' in args else None
    timeout = int(args[args.index('--timeout') + 1]) if '--timeout' in args else 600

    import tempfile
    say('第115轮后续 · 逐项重放录像')
    say('  ROOT = %s' % ROOT)
    say('  解释器 = %s' % PY)
    say('  ★ 真机：重放器向子进程显式注入 `QT_QPA_PLATFORM=windows`')
    say('  ★ 沙箱：重放器向子进程注入 `RALSEI_MEMORY_DIR` / `RALSEI_DATA_DIR` /')
    say('          `RALSEI_DESKTOP`（各轮 rec*.py 历史脚本**不改**，保持当年原样）')

    # ★★★ 外部尺子：跑前拍用户记忆库指纹（**不信任何脚本自称沙箱**）
    sys.path.insert(0, os.path.join(CQA, '_shared'))
    vg = None
    vault_before = None
    try:
        import vault_guard as vg
        vault_before = vg.snapshot()
        if vault_before is None:
            say('  ★ 记忆库根不存在（%s）⇒ 本次无法比对' % vg.DEFAULT_ROOT)
            vg = None
        else:
            say('  ★ 记忆库指纹已拍：%d 个文件（%s）'
                % (len(vault_before), vg.DEFAULT_ROOT))
    except Exception as e:
        say('  ★ 记忆库指纹拍摄失败（结尾会如实报错）: %r' % (e,))
    say('')

    results = []
    for rdir, rel in RECORDERS:
        rid = os.path.basename(rel)[:-3]
        if only and only not in rid:
            continue
        script = os.path.join(CQA, rdir, rel)
        if not os.path.isfile(script):
            say('--- %-12s [SKIP] 脚本不在盘: %s' % (rid, script))
            results.append({'id': rid, 'round': rdir, 'skip': 'missing script'})
            continue
        n_before = frames_before(rdir)
        t0 = time.time()
        # ★★★ 第115轮修（**重放器自己的保真缺陷**）：
        #   各 `rec*.py` 内部写的是 `os.environ.setdefault('QT_QPA_PLATFORM','offscreen')`
        #   —— 不动它就是**离屏**，PNG 全为 0 ⇒ **那不算"录屏"**。
        #   首版没覆盖，结果 `rec111` 在离屏下直接 **0xC0000005 崩溃**，
        #   而我单独用真机模式跑它却是 `PASS=15 FAIL=0 PNG=4`。
        #   ⇒ 必须显式把 `QT_QPA_PLATFORM=windows` 喂进子进程，
        #     才配叫"逐项**录屏**测试"。
        env = dict(os.environ)
        env['QT_QPA_PLATFORM'] = 'windows'
        # ★★★ 沙箱四闸（由重放器统一注入；各轮历史脚本**不动**）
        #   ⚠️ 只设 `RALSEI_DATA_DIR` + 猴补丁 `data_store.vault_root` 是**拦不住**的：
        #      `data_store` 只是包装层，路径真源是 `memory_store`；记忆系统**直接**用
        #      `memory_store`（绕过猴补丁），而 `find_device_dir()` 里
        #      **`RALSEI_MEMORY_DIR`（ENV_DIR）优先级最高** ⇒ 那才是真正的闸。
        _sb = tempfile.mkdtemp(prefix='replay115_%s_' % rid)
        for _sub in ('vault', 'staging', 'desktop'):
            os.makedirs(os.path.join(_sb, _sub), exist_ok=True)
        env['RALSEI_MEMORY_DIR'] = os.path.join(_sb, 'vault')
        env['RALSEI_DATA_DIR'] = os.path.join(_sb, 'staging')
        env['RALSEI_DESKTOP'] = os.path.join(_sb, 'desktop')
        try:
            p = subprocess.run([PY, rel], cwd=os.path.join(CQA, rdir), env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=timeout)
            rc, out = p.returncode, p.stdout.decode('utf-8', 'replace')
            timed_out = False
        except subprocess.TimeoutExpired as e:
            rc, out, timed_out = -9, (e.stdout or b'').decode('utf-8', 'replace'), True
        wall = round(time.time() - t0, 1)
        n_after = frames_before(rdir)
        np_ = len(re.findall(r'\[PASS\]', out))
        nf_ = len(re.findall(r'\[FAIL\]', out))
        png = max(0, n_after - n_before)
        rec = {'id': rid, 'round': rdir, 'rc': rc, 'pass': np_, 'fail': nf_,
               'png_new': png, 'png_total': n_after, 'wall_s': wall,
               'timed_out': timed_out, 'qpa': 'windows',
               'real_machine': ('real_machine=True' in out
                                or '真机=True' in out or 'qpa=windows' in out),
               'tail': [l for l in out.splitlines() if l.strip()][-6:]}
        results.append(rec)
        say('--- %-12s rc=%-3s PASS=%-4d FAIL=%-3d PNG新增=%-3d 总=%-4d %6.1fs%s'
            % (rid, rc, np_, nf_, png, n_after, wall, '  ★超时' if timed_out else ''))
        for l in rec['tail']:
            say('      | %s' % l[:150])

    # ★★★ 跑完：用**外部尺子**复核用户记忆库指纹 —— 不许自称"我沙箱了"
    guard_rc = None
    guard_note = 'skipped'
    if vg is not None and vault_before is not None:
        try:
            vault_after = vg.snapshot()
            a, rem, c = vg.compare(vault_before, vault_after)
            guard_rc = 0 if (not a and not rem and not c) else 1
            guard_note = (u'一致 ✓ %d 个文件未变（用户记忆库没被碰）'
                          % len(vault_after)) if guard_rc == 0 else \
                (u'★ 有差异 added=%d removed=%d changed=%d'
                 % (len(a), len(rem), len(c)))
            say('\n[vault_guard] %s' % guard_note)
            for k in a[:20]:
                say('   + 新增 %s' % k)
            for k in rem[:20]:
                say('   - 消失 %s' % k)
            for k, _o, _n in c[:20]:
                say('   ~ 变化 %s' % k)
            with io.open(os.path.join(EV, 'VAULT_GUARD.json'), 'w',
                         encoding='utf-8', newline='\n') as _f:
                json.dump({'root': getattr(vg, 'DEFAULT_ROOT', None),
                           'before_n': len(vault_before),
                           'after_n': len(vault_after) if vault_after else None,
                           'added': a, 'removed': rem,
                           'changed': [k for k, _o, _n in c],
                           'verdict': guard_note},
                          _f, ensure_ascii=False, indent=1)
        except Exception as e:
            guard_rc, guard_note = 2, u'★ 复核失败 %r' % (e,)
            say('\n[vault_guard] %s' % guard_note)

    say('\n' + '=' * 74)
    tot_p = sum(r.get('pass', 0) for r in results)
    tot_f = sum(r.get('fail', 0) for r in results)
    tot_png = sum(r.get('png_new', 0) for r in results)
    bad = [r['id'] for r in results
           if r.get('fail') or (r.get('rc') not in (0, None)) or r.get('timed_out')]
    if guard_rc:
        bad.append('vault_guard')
    say('合计：脚本 %d ｜ PASS=%d ｜ FAIL=%d ｜ PNG 新增=%d' % (len(results), tot_p, tot_f, tot_png))
    say('有问题的项：%r' % (bad,))
    say('★ 结论：%s' % ('全部通过' if not bad else '★ 见上面有问题的项'))

    with io.open(os.path.join(EV, 'REPLAY115.json'), 'w',
                 encoding='utf-8', newline='') as f:
        json.dump({'results': results, 'totals': {'pass': tot_p, 'fail': tot_f,
                                                  'png': tot_png, 'bad': bad},
                   'vault_guard': {'rc': guard_rc, 'note': guard_note}},
                  f, ensure_ascii=False, indent=1)
    return 0 if not bad else 1


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as e:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (e,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(os.path.join(EV, 'replay115_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
