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


def main():
    say('===== 收尾链启动 =====')
    wait_main()

    # ★ 带 `--force`：现存的两份房间记录（ralsei / susie）是在**补丁修复之前**跑的，
    #   那时 `room_system` 还把纠正句丢掉 ⇒ 它们带着"没有纠正句"的毛病
    #   （ralsei 那句不存在的人名「凯斯恩」就是从这里来的）。34 人整跑本来也就 1 小时，
    #   与其只补两条、留下口径不一致，不如整体重跑一次。
    step('房间专属回忆（34 人 × 四档）', ['room113.py', '--train', '--force'])

    # 两条纠正句是**本轮新写的**，正在跑的那个进程看不见 ⇒ 单独重跑
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
