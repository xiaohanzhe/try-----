# -*- coding: utf-8 -*-
u"""第113轮 · 训练期间的机器看护（温度读不到时的**可判**替代方案）。

先说结论（这条必须写清楚，不能含糊）
------------------------------------
本机**读不到 CPU 温度**，三个通道都试过：
  · `MSAcpi_ThermalZoneTemperature` ⇒ **拒绝访问**（需要管理员）；
  · `\\Thermal Zone Information(*)` 性能计数器 ⇒ 恒为 **0 K**（驱动没暴露）；
  · 联想 `root\\wmi:LENOVO_GAMEZONE_DATA` 的 `GetCPUTemp` ⇒ 类存在、方法存在，
    但**取不到实例**（`Get-CimInstance` 返回空）⇒ 调不到。
⇒ 任何声称"现在 CPU 82 度"的输出都是编的。本文件**不编**。

那还怎么保证"别把电脑干炸"
--------------------------
用三个**能真实取到**的量，并对它们下硬闸：

  1. **可用内存**（`psutil`）。7B 模型 + 18 核推理会把内存顶到很紧；
     实测只剩 4.5 GB。低于 `--mem-floor`（默认 600 MB）⇒ 立即停训练
     （OOM 时 Windows 会开始换页/杀进程，那才是真正的"卡死"体验）。
  2. **解码吞吐（tok/s）**。这是**最好的间接温度计**：这颗 CPU 没有频率浮动
     （`psutil.cpu_freq` 恒报 1200 MHz，min=max），一旦触发功耗/温度限制，
     最直接的表现就是同样的负载下 token 变慢。取最近 3 个角色、
     `Σeval_count / Σeval_duration`，与开局基线比：跌破 **55%** 连续 3 次
     ⇒ 判"疑似降频"⇒ 停训练 + 冷却。
  3. **CPU 占用**。只记录、不判定（高负载是预期的，不是异常）。

停训练的方式是 `terminate()` 而不是 `kill()`：训练是**断点续跑**的
（每完成一个角色就落一条 `raw/<id>.jsonl`），停掉只损失当前这个人。

用法
----
    python thermal113.py                    # 后台看护，直到训练结束或触发闸门
    python thermal113.py --watch 20         # 采样间隔（秒）
    python thermal113.py --once             # 只采一次（自检/人工查看）
"""
import argparse
import json
import os
import statistics
import sys
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common113 as C  # noqa: E402

CSV = os.path.join(C.EVID, 'thermal113.csv')
LOG = os.path.join(C.EVID, 'thermal113.log')

#: ★ 必须**显著低于** dialogue113 的等待闸（450MB）。
#: 训练在 450MB 只是"歇一会儿等内存回来"，此时它并不吃内存、杀了也救不了内存；
#: 看护该管的是"训练 + 模型一起把内存榨干"那种真濒死（<250MB 开始硬换页）。
MEM_FLOOR_MB = 250
TPS_FLOOR = 0.55            # 吞吐跌到基线 55% 以下
TPS_STRIKES = 3             # 连续 3 次才动手（避免一次抖动误判）
COOL_SECONDS = 180          # 触发后冷却时长


#: 受看护的脚本。第113轮的后半段是"态度评测"，它同样长时间打模型，
#: 不能只盯 `dialogue113.py`（盯漏了就等于这段时间没有保护）。
WATCHED = ('dialogue113.py', 'attitude113.py')


def find_train_pids():
    out = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cl = ' '.join(p.info.get('cmdline') or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if any(w in cl for w in WATCHED):
            out.append(p.info['pid'])
    return out


def ollama_rss_mb():
    tot = 0
    for p in psutil.process_iter(['name']):
        try:
            if p.info['name'] and 'ollama' in p.info['name'].lower():
                tot += p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return tot / 1e6


def recent_tps(n=3):
    """最近 n 个角色的解码吞吐（tok/s）。没有数据 ⇒ `None`（不参与判定）。"""
    if not os.path.isdir(C.RAW):
        return None
    files = []
    for fn in os.listdir(C.RAW):
        if fn.endswith('.jsonl'):
            p = os.path.join(C.RAW, fn)
            files.append((os.path.getmtime(p), p))
    files.sort(reverse=True)
    tok = 0.0
    sec = 0.0
    seen = 0
    for _, p in files:
        recs = C.read_jsonl(p)
        if not recs:
            continue
        rec = recs[-1]
        for t in rec.get('turns') or []:
            st = t.get('stats') or {}
            if st.get('eval_count') and st.get('eval_s'):
                tok += st['eval_count']
                sec += st['eval_s']
        seen += 1
        if seen >= n:
            break
    if sec <= 0:
        return None
    return round(tok / sec, 2)


def sample(label=''):
    vm = psutil.virtual_memory()
    load = psutil.cpu_percent(interval=None)
    per = psutil.cpu_percent(percpu=True)
    row = {
        'ts': time.strftime('%H:%M:%S'),
        'label': label,
        'cpu_pct': round(load, 1),
        'cpu_max_core': max(per) if per else None,
        'mem_avail_mb': round(vm.available / 1e6),
        'mem_pct': vm.percent,
        'ollama_rss_mb': round(ollama_rss_mb()),
        'tps': recent_tps(),
        'train_pids': find_train_pids(),
        'temp_supported': False,   # 读不到就是读不到，字段留着是为了别骗自己
    }
    return row


def write_csv(row):
    head = ['ts', 'label', 'cpu_pct', 'cpu_max_core', 'mem_avail_mb', 'mem_pct',
            'ollama_rss_mb', 'tps', 'train_pids', 'temp_supported']
    new = not os.path.isfile(CSV)
    d = os.path.dirname(CSV)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(CSV, 'a', encoding='utf-8', newline='') as fh:
        if new:
            fh.write(','.join(head) + '\n')
        fh.write(','.join('' if row.get(k) is None else str(row.get(k)).replace(',', '/')
                          for k in head) + '\n')


def log(msg):
    line = '[%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write(line + '\n')


def stop_training(pids, reason):
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            log('已发送 terminate 给训练进程 %d（%s）' % (pid, reason))
        except Exception as e:
            log('终止 %d 失败：%s' % (pid, e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--watch', type=int, default=20)
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--mem-floor', type=int, default=MEM_FLOOR_MB)
    args = ap.parse_args()

    log('看护启动：采样 %ds／内存下限 %dMB／吞吐下限 %.0f%%（温度：本机不可读，见文件头）'
        % (args.watch, args.mem_floor, TPS_FLOOR * 100))
    if args.once:
        r = sample('once')
        write_csv(r)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0

    psutil.cpu_percent(interval=None)
    baseline = []          # 开局 5 个采样的 tps 中位数
    strikes = 0
    last_tps = None
    while True:
        row = sample()
        write_csv(row)
        if row['tps'] is not None:
            if len(baseline) < 5:
                baseline.append(row['tps'])
                log('基线采样 %d/5：%.2f tok/s' % (len(baseline), row['tps']))
            else:
                base = statistics.median(baseline)
                if row['tps'] < base * TPS_FLOOR:
                    strikes += 1
                    log('⚠️ 吞吐 %.2f tok/s < 基线 %.2f 的 %.0f%%（第 %d 次）'
                        % (row['tps'], base, TPS_FLOOR * 100, strikes))
                else:
                    strikes = 0
            last_tps = row['tps']

        pids = row['train_pids']
        if row['mem_avail_mb'] < args.mem_floor:
            log('🛑 可用内存 %dMB < %dMB，停训练（防换页卡死）'
                % (row['mem_avail_mb'], args.mem_floor))
            stop_training(pids, 'mem')
            return 2
        if strikes >= TPS_STRIKES:
            log('🛑 连续 %d 次吞吐跌破 %.0f%%（%.2f tok/s），判为疑似降频/过热，停训练并冷却 %ds'
                % (TPS_STRIKES, TPS_FLOOR * 100, last_tps or -1, COOL_SECONDS))
            stop_training(pids, 'thermal')
            return 3
        if not pids:
            log('训练进程已不在（正常结束或被停），看护退出')
            return 0
        time.sleep(args.watch)


if __name__ == '__main__':
    sys.exit(main())
