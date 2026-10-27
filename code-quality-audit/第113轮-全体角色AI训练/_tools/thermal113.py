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
import urllib.request

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
#: 第113轮b 加了 `train30.py`（77 人 × 30 轮 ≈ 11 小时满载，是最需要看护的一档）。
WATCHED = ('dialogue113.py', 'attitude113.py', 'train30.py')


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


#: 内存吃紧时"先卸载模型再复查"的次数（每次之间等 UNLOAD_WAIT 秒）
UNLOAD_TRIES = 2
UNLOAD_WAIT = 10
#: 卸载后要恢复到下限的多少倍才算"缓解"（刚好过线 ⇒ 下一秒又撞闸，白折腾）
UNLOAD_OK_FACTOR = 4


def mem_avail_mb():
    return psutil.virtual_memory().available / 1048576.0


def unload_model(timeout=180):
    """让 ollama **主动释放推理进程**（`keep_alive=0`），返回是否成功。

    ★★★ 为什么需要这个（2026-10-28 事故实证）：
      `llama-server` 的 RSS 会随训练**持续增长** —— 21:54 时 5.9 GB，06:30 时 **11.7 GB**，
      可用内存被压到 **17 MB**，看护于是直接 terminate 了正在跑 39/75 的训练。
      但实测：调一次 `keep_alive=0` 卸载，可用内存 **1.21 GB → 13.56 GB（回收 12.35 GB）**，
      `llama-server` 整个进程退出。
      ⇒ **内存压力几乎全在推理进程里，卸载就能解**，"杀训练"应该是最后手段而不是第一步。
      代价只是下一轮要冷加载（实测 4.52 s）+ 重建 prompt 缓存。
    """
    try:
        body = json.dumps({'model': C.MODEL, 'keep_alive': 0}).encode('utf-8')
        req = urllib.request.Request(C.OLLAMA + '/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception as e:                                  # noqa: BLE001
        log('  卸载模型失败：%s: %s' % (type(e).__name__, e))
        return False


def relieve_mem(floor_mb, read_mem=None, do_unload=None, tries=None, wait=None):
    """内存吃紧时**先卸载模型再复查**。返回 `'ok'`（已缓解，可继续跑）/ `'still_low'`（真不足）。

    ★★ 为什么抽成函数：这条分支的**正面路径在真机上复现不出来** ——
      "卸载前低于下限、卸载后回到下限 4 倍以上" 只有在 `llama-server` 长时间涨到 11 GB
      之后才会出现（见 `unload_model` 的注释）。不抽出来就**只能靠读代码相信它**。
      参数可注入 ⇒ 三种组合都能用假件跑一遍。
    """
    read_mem = read_mem or mem_avail_mb
    do_unload = do_unload or unload_model
    tries = UNLOAD_TRIES if tries is None else tries
    wait = UNLOAD_WAIT if wait is None else wait
    for k in range(tries):
        ok = do_unload()
        if wait:
            time.sleep(wait)
        free = read_mem()
        log('  第 %d 次卸载%s ⇒ 可用 %.0fMB'
            % (k + 1, '成功' if ok else '失败', free))
        if free >= floor_mb * UNLOAD_OK_FACTOR:
            return 'ok'
    # 没到"宽裕"档，但只要已经越过下限就继续跑 —— 刚好过线也比杀训练强
    return 'ok' if read_mem() >= floor_mb else 'still_low'


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
    seen_pids = set()
    while True:
        row = sample()
        write_csv(row)
        if row['tps'] is None:
            # ★★★ 第113轮b 修的真 bug（教训：**两种不同的原因不能共用一个计数器**）
            #   `tps is None` = 这段时间**没有产出**：冷 prefill（实测每个角色切换
            #   要 100~230s！）、内存闸等待、角色之间的冷却。这些都不是"降频"。
            #   原实现只在 `tps is not None` 分支里动 strikes ⇒ 冷 prefill 期间
            #   strikes 原样攒着，攒够 3 次就把正在跑 12 小时的训练 terminate 掉。
            #   实测代价：一次 36 轮验证跑（17:xx）就是这样被误杀的。
            if strikes:
                log('吞吐无产出（prefill/等待/冷却）⇒ 判定计数清零（原 %d 次）' % strikes)
            strikes = 0
        elif len(baseline) < 5:
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
        if row['tps'] is not None:
            last_tps = row['tps']

        pids = row['train_pids']
        # 训练进程变了（重启/续跑）⇒ 新进程第一轮必然是冷 prefill，旧基线不适用
        if set(pids) != seen_pids:
            seen_pids = set(pids)
            if strikes:
                log('训练进程集合变化 ⇒ 判定计数清零')
            strikes = 0

        pids = row['train_pids']
        if row['mem_avail_mb'] < args.mem_floor:
            # ★★★ 第113轮q 修（2026-10-28 事故）：原来这里是"一见低内存就 terminate"，
            #   结果在 39/75 处把训练杀了，而**同一时刻卸载模型能立刻回收 12.35 GB**。
            #   顺序改成：先卸 → 复查 → 仍不足才杀。杀之前必须先把"能自己解的"解掉。
            log('⚠️ 可用内存 %dMB < %dMB，先卸载模型试试（不急着杀训练）'
                % (row['mem_avail_mb'], args.mem_floor))
            if relieve_mem(args.mem_floor) == 'still_low':
                log('🛑 卸载后仍不足 %dMB，停训练（防换页卡死）' % args.mem_floor)
                stop_training(pids, 'mem')
                return 2
            log('  内存已缓解 ⇒ 继续跑（下一个角色会冷加载模型，首轮 prefill 会慢）')
            time.sleep(args.watch)
            continue
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
