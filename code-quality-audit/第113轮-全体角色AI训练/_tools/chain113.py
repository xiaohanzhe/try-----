# -*- coding: utf-8 -*-
"""第113轮 · 收尾链：主训练退出 → 房间训练 → 两条纠正句复跑 → 出报告

## 为什么要有这个东西
主训练 77 人 × 48 轮（2026-10-25 起）要跑约 18 小时，会话不可能一直开着。但**后台进程能跨会话存活**
（实测：上一会话起的 `train30.py` 这一会话还在跑）。所以把剩下的步骤串成链，
让它在主训练自然退出之后自己往下走，不依赖"我还醒着"。

## 顺序
1. `train30.py --turns 48`（**已经在跑**，这里只等它，不重复启动）
2. `room113.py --train` —— 34 人有房间回忆，四档递减
3. `train30.py --turns 48 --only ralsei,susie --force` —— 这两条纠正句是本轮新写的，
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

#: 轮数与 ctx 一律取 train30 的真源，不再在本文件里写死。
#: ★ 2026-10-25 剧本从 36 扩到 48，如果这里还写 36，`done_count()` 会数出 0 人，
#:   完成度守卫直接判"训练没跑完"并把整条链中止 —— 而且日志说"没跑完"，
#:   看着像训练真的失败了。
sys.path.insert(0, HERE)
import train30 as T          # noqa: E402
TURNS = T.TURNS_DEFAULT
CTX = T.CTX30


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


def done_count(target=TURNS):
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


def _latest(target=TURNS):
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


def low_lang(thresh=0.6, target=TURNS):
    """中文占比低于阈值的角色（按占比升序）。

    ★ 第113轮起 `main()` **不再用它**（改成 `needs_rerun()`，语言 + 长度一起看）。
      保留作人工排查的小工具：想知道"纯语言维度"谁最糟时直接调它。
    """
    rows = [(cn_avg(r), nid) for nid, r in _latest(target).items()]
    return [nid for c, nid in sorted(rows) if c < thresh]


def js_len(s):
    """JS 的 `String.length` 口径（代理对计 2）。产品侧上限按这个数算。"""
    return len((s or '').encode('utf-16-le')) // 2


def over_rate(rec, limit=220):
    """超长率：回复长度 > limit 的轮次占比。产品 `AI_REPLY_MAX_CHARS=220`。"""
    ts = rec.get('turns') or []
    if not ts:
        return 0.0
    n = sum(1 for t in ts if js_len(t.get('final')) > limit)
    return n / float(len(ts))


def needs_rerun(lang_thresh=0.6, over_thresh=0.25, target=TURNS):
    """**体检**：哪些人必须用新规则重跑，以及为什么。

    ★ 为什么不能只看语言（第113轮实测）：
      `hy_martlet` 中文占比 0.9+（语言没问题），但 36 轮里 27 次超 220 字、
      均长 257（别人 37~163）—— 它的问题是**用长度冒充"话多"**，
      按 `low_lang` 的名单根本抓不到，会一直留在"及格"名单里。
    ★ 两类问题同一个根：`SPEAK_RULES` 里"一次只说 1~3 句"被理解成
      "1~3 个长句"，既撑出超长、又把中文挤成英文长句。新规则一次治两个。
    """
    rows = []
    for nid, r in _latest(target).items():
        c = cn_avg(r)
        o = over_rate(r)
        why = []
        if c < lang_thresh:
            why.append('中文占比 %.2f' % c)
        if o >= over_thresh:
            why.append('超长 %d%%（>220字）' % int(round(o * 100)))
        if why:
            rows.append((nid, '、'.join(why)))
    rows.sort()
    return rows


def main():
    say('===== 收尾链启动 =====')
    wait_main()

    # ★★★ 2026-10-25 02:15 实测：训练不是"跑完了"，是**被 OOM 杀掉的**
    #   （可用内存只剩 174MB，系统终止了 python），而链子的判据只有"PID 没了"
    #   ⇒ 它兴冲冲地开始跑房间训练，顺序完全错（主训练还差 32 人）。
    #   "进程消失" ≠ "任务完成"，这是"文件在=已完成"那个老坑的孪生版本。
    #   ⇒ 退出后先看完成人数，不满就**停在这里**，把判断交给人。
    done = done_count()
    total = len([f for f in os.listdir(RAW30) if f.endswith('.jsonl')]) if os.path.isdir(RAW30) else 0
    roster_total = 77          # 77 人有人设（第113轮口径，`knight` 缺口）
    if done < roster_total:
        say('!! 主训练**没跑完**就退出了：%d / %d 人（raw 文件 %d 份）'
            % (done, roster_total, total))
        say('   常见原因：内存不足被系统杀掉 / 手动终止。')
        say('   ⇒ 不往下走（房间训练必须等主训练跑完），交给人工重新拉起。')
        say('===== 收尾链中止 =====')
        return 2
    say('主训练确认跑完（%d/%d 人）⇒ 继续' % (done, roster_total))

    # ---- ① 个体复跑：**先修人设对话，再做房间专属回忆**
    # ★ 顺序为什么反过来了：房间回忆是把该角色的人设对话当作上下文的一部分延续的，
    #   人设对话本身要是"整段英文 / 257 字长回复"，房间档只会继承同一个毛病。
    # ★ 名单**数据驱动**，不是我预先点名：`needs_rerun()` 从 raw30 现算
    #   （中文占比 <0.60 或 超 220 字的轮次 ≥25%）。预先点名的名单永远会漏人 ——
    #   上一版只点语言，`hy_martlet`（中文 0.9+，但 27/36 轮超长）就被漏掉了。
    # ★ ralsei / susie 另外**强制**加入：它们的 `patches` 是本轮新写的，
    #   而体检判据只看语言/长度，抓不到"纠正句变了"。
    FORCE = ('ralsei', 'susie')
    rows = needs_rerun()
    names = [nid for nid, _ in rows]
    for nid in FORCE:
        if nid not in names and nid in _latest():
            names.append(nid)
            rows.append((nid, '纠正句是本轮新写的'))
    if names:
        say('体检：%d 人需用新说话规则重跑' % len(names))
        for nid, why in rows:
            say('   %-22s %s' % (nid, why))
        step('体检不合格角色整批复跑（%d 人 × %d 轮）' % (len(names), TURNS),
             ['train30.py', '--turns', str(TURNS), '--ctx', str(CTX),
              '--only', ','.join(names), '--force',
              '--log', os.path.abspath(os.path.join(HERE, '..', '_evidence',
                                                    'train30_fixbatch.log'))])
        # ---- ② 复检：复跑**不一定**真的修好。没有这一步，"跑过了"会被当成"修好了"。
        after = needs_rerun()
        left = [n for n, _ in after if n not in FORCE]
        if left:
            say('!! 复跑后仍有 %d 人不合格：%s' % (len(left), ','.join(left)))
            for nid, why in after:
                say('   %-22s %s' % (nid, why))
            say('   ⇒ 说明问题不在"说话规则"，得看具体原文（别再整批重跑）')
        else:
            say('✓ 复检通过：语言与长度两类问题都已消失')
    else:
        say('体检通过：没有人需要重跑（语言与长度都在闸内）')

    # ---- ③ 房间专属回忆（34 人 × 四档）
    # ★ 带 `--force`：现存两份房间记录（ralsei / susie）是在**补丁修复之前**跑的，
    #   那时 `room_system` 还把纠正句丢掉 ⇒ 它们带着"没有纠正句"的毛病
    #   （ralsei 那句不存在的人名「凯斯恩」就是从这里来的）。34 人整跑本来也就 1 小时，
    #   与其只补两条、留下口径不一致，不如整体重跑一次。
    step('房间专属回忆（34 人 × 四档）', ['room113.py', '--train', '--force'])

    step('主报告', ['report30.py'])
    step('房间报告', ['room113.py', '--report'])
    say('===== 收尾链结束 =====')


if __name__ == '__main__':
    main()
