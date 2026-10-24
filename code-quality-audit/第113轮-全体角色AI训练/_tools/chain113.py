# -*- coding: utf-8 -*-
"""第113轮 · 收尾链：主训练退出 → 房间训练 → 两条纠正句复跑 → 出报告

## 为什么要有这个东西
主训练 77 人 × 36 轮要跑约 16 小时，会话不可能一直开着。但**后台进程能跨会话存活**
（实测：上一会话起的 `train30.py` 这一会话还在跑）。所以把剩下的步骤串成链，
让它在主训练自然退出之后自己往下走，不依赖"我还醒着"。

## 顺序
1. `train30.py --turns 36`（**已经在跑**，这里只等它，不重复启动）
2. `room113.py --train` —— 34 人有房间回忆，四档递减
3. `train30.py --turns 36 --only ralsei,susie --force` —— 这两条纠正句是本轮新写的，
   而正在跑的那个进程在启动时就把 `_index.json` 读进内存了，改索引它看不见
   ⇒ 必须单独重跑一次才生效。日志单独一份，别把主日志搅浑。
4. `report30.py` + `room113.py --report`

## 判据纪律
- **等的是 PID，不是命令行**：如果按 `'train30.py' in cmdline` 去等，第 3 步自己起的
  子进程会被当成交警，逻辑就绕回去了。启动时先把当前 train30 的 pid 快照下来，
  只等这几个 pid 消失。
- 任何一步失败都**不中断后面**（报告比"完美进度"更重要：没跑完的也要出报告），
  但每步的退出码都记进日志。
"""
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LOG = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'chain113.log'))


def say(msg):
    line = '[%s] %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    with io.open(LOG, 'a', encoding='utf-8', newline='\n') as f:
        f.write(line + '\n')


def main_pids():
    """当前正在跑的**主训练**进程（train30.py 且带 --turns）。"""
    try:
        import psutil
    except Exception:
        return set()
    out = set()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cl = ' '.join(p.info['cmdline'] or [])
        except Exception:
            continue
        if 'train30.py' in cl and '--turns' in cl:
            out.add(p.info['pid'])
    return out


def alive(pids):
    try:
        import psutil
    except Exception:
        return False
    for pid in pids:
        try:
            p = psutil.Process(pid)
            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                return True
        except Exception:
            continue
    return False


def done_count(target=36):
    """已完成 target 轮的人数（按 raw30 里 turns_n 判，不按文件存在判）。"""
    raw = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'raw30'))
    n = 0
    if not os.path.isdir(raw):
        return 0
    import json
    for f in os.listdir(raw):
        if not f.endswith('.jsonl'):
            continue
        try:
            for ln in io.open(os.path.join(raw, f), encoding='utf-8'):
                if not ln.strip():
                    continue
                r = json.loads(ln)
                if isinstance(r, dict) and r.get('turns_n') == target:
                    n += 1
                    break
        except Exception:
            continue
    return n


def wait_main(timeout_h=20.0):
    pids = main_pids()
    if not pids:
        say('没发现正在跑的主训练 ⇒ 直接往下走')
        return
    say('等主训练退出：pid=%s（已完成 %d 人）' % (sorted(pids), done_count()))
    t0 = time.time()
    last_beat = t0          # ★ 不是 0：用 0 会让第一圈就立刻打一条"已等 0.0 小时"的噪音
    while alive(pids):
        if time.time() - t0 > timeout_h * 3600:
            say('!! 等超过 %.0f 小时，放弃等待，直接往下走' % timeout_h)
            return
        if time.time() - last_beat > 600:
            last_beat = time.time()
            say('…还在跑，已完成 %d 人，已等 %.1f 小时' % (done_count(),
                                                        (time.time() - t0) / 3600))
        time.sleep(60)
    say('主训练已退出（完成 %d 人）' % done_count())


def step(title, args):
    say('=== %s ===' % title)
    say('  $ %s %s' % (os.path.basename(PY), ' '.join(args)))
    t0 = time.time()
    try:
        with io.open(LOG, 'a', encoding='utf-8', newline='\n') as f:
            p = subprocess.run([PY] + args, cwd=HERE, stdout=f,
                               stderr=subprocess.STDOUT)
        say('  rc=%d · %.1f 分钟' % (p.returncode, (time.time() - t0) / 60))
        return p.returncode
    except Exception as e:
        say('  !! 起不来：%r' % (e,))
        return -1


RAW30 = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'raw30'))


def _latest(target=36):
    """id → 最新一条 target 轮记录。"""
    import json
    out = {}
    if not os.path.isdir(RAW30):
        return out
    for f in os.listdir(RAW30):
        if not f.endswith('.jsonl'):
            continue
        try:
            for ln in io.open(os.path.join(RAW30, f), encoding='utf-8'):
                if not ln.strip():
                    continue
                r = json.loads(ln)
                if isinstance(r, dict) and r.get('turns_n') == target:
                    out[f[:-6]] = r          # 后面覆盖前面 ⇒ 留最新
        except Exception:
            continue
    return out


def cn_avg(rec):
    """一条记录的平均中文占比（**从 turns 现算**，不读存的 metrics：
    那些记录的 metrics 是加语言指标之前写的，读不到）。"""
    import re
    ts = rec.get('turns') or []
    if not ts:
        return 0.0
    tot = 0.0
    for t in ts:
        s = re.sub(r'\s', '', t.get('final') or '')
        if not s:
            tot += 1.0
            continue
        tot += len(re.findall(r'[\u4e00-\u9fff]', s)) / float(len(s))
    return tot / len(ts)


def low_lang(thresh=0.6, target=36):
    """中文占比低于阈值的角色（按占比升序）。"""
    rows = [(cn_avg(r), nid) for nid, r in _latest(target).items()]
    return [nid for c, nid in sorted(rows) if c < thresh]


def main():
    say('===== 收尾链启动 =====')
    wait_main()

    # ★ 带 `--force`：现存两份房间记录（ralsei / susie）是在**补丁修复之前**跑的，
    #   那时 `room_system` 还把纠正句丢掉 ⇒ 它们带着"没有纠正句"的毛病
    #   （ralsei 那句不存在的人名「凯斯恩」就是从这里来的）。34 人整跑本来也就 1 小时，
    #   与其只补两条、留下口径不一致，不如整体重跑一次。
    step('房间专属回忆（34 人 × 四档）', ['room113.py', '--train', '--force'])

    # ---- 语言修复的 A/B 探针（**先证伪再整批**）
    # 用户口径「尤其性格」：连语言都不对，性格无从谈起。系统提示里补了"用简体中文"
    # 之后，先在**两个最糟的**人身上验一次（0.41 / 0.54），生效才敢整批跑 4 小时；
    # 不生效就停在这里，别把 4 小时花在一个没起作用的修法上。
    probe = [nid for nid in ('hy_ed', 'hy_sousborg') if nid in _latest()]
    if probe:
        before = {n: round(cn_avg(_latest()[n]), 2) for n in probe}
        step('语言修复探针（%s，各 36 轮）' % ','.join(probe),
             ['train30.py', '--turns', '36', '--ctx', '12288',
              '--only', ','.join(probe), '--force',
              '--log', os.path.abspath(os.path.join(HERE, '..', '_evidence',
                                                    'train30_langprobe.log'))])
        after = {n: round(cn_avg(_latest()[n]), 2) for n in probe}
        say('  探针结果：%s → %s' % (before, after))
        ok = all(after[n] >= 0.8 for n in probe)
        if ok:
            say('  ✓ 语言修复生效（>=0.80） ⇒ 整批复跑低中文占比角色')
            todo = [n for n in low_lang() if n not in probe]
            if todo:
                say('  待复跑 %d 人：%s' % (len(todo), ','.join(todo)))
                step('低中文占比角色整批复跑（%d 人 × 36 轮）' % len(todo),
                     ['train30.py', '--turns', '36', '--ctx', '12288',
                      '--only', ','.join(todo), '--force',
                      '--log', os.path.abspath(os.path.join(HERE, '..', '_evidence',
                                                            'train30_langfix.log'))])
            else:
                say('  没有别的低占比角色了')
        else:
            say('  !! 语言修复**没生效** ⇒ 跳过整批复跑，留给人工判断（别再烧 4 小时）')

    # ---- 两条纠正句是本轮新写的，正在跑的那个进程看不见 ⇒ 单独重跑
    step('ralsei / susie 带新纠正句重跑（各 36 轮）',
         ['train30.py', '--turns', '36', '--ctx', '12288',
          '--only', 'ralsei,susie', '--force',
          '--log', os.path.abspath(os.path.join(HERE, '..', '_evidence',
                                                'train30_rerun.log'))])

    step('主报告', ['report30.py'])
    step('房间报告', ['room113.py', '--report'])
    say('===== 收尾链结束 =====')


if __name__ == '__main__':
    main()
