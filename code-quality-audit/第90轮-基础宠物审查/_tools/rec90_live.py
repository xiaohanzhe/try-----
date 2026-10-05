# -*- coding: utf-8 -*-
u"""第90轮 · 真机录屏 + 逐帧对比（用户视角验收）

用户口径（逐字）：「你可以录视频然后通过对比前后帧这样的方法判定他的移动
这类的也就是用户视角的反馈」。

做法（全部走「屏幕自动化小助手」的原生能力 `recording.draft`，不绕过它）：
  1. `experience create` 建经验采集任务（小助手要求 project 必须先存在）
  2. `recording start` 开始录屏
  3. 录制期间**逐秒采样宠物窗口的屏幕矩形**（走 `window.list-visible`）
     —— 这是**绝对坐标锚点**，用来给后面的逐帧差分做标定
  4. `recording stop` 停止

产物：`C:\\Users\\23002\\Downloads\\_tmp\\rec90_rects.csv`（采样）+ stdout 的 stop JSON
     （含录制目录，交给 analyze90.py 去 export + 逐帧分析）

隐私：录屏必然包含用户的桌面 ⇒ 产物**一律落在 Downloads\\_tmp**（不进仓库、
      不进公开远端），只有「轨迹图 / 数值表」这类不含桌面的派生物才可能入库。
"""
import json
import os
import subprocess
import sys
import time

CLI = r'C:\Users\23002\AppData\Local\Programs\Xiaozs\ScreenAutomationHelper\ScreenAutomationHelper.exe'
TMP = r'C:\Users\23002\Downloads\_tmp'
OUT_CSV = os.path.join(TMP, 'rec90_rects.csv')
PROJECT = 'round90-jump-verify'
PET_TITLE = 'Ralsei Pet'


def cli(*args, timeout=60):
    p = subprocess.run([CLI, 'cli'] + list(args), capture_output=True, timeout=timeout)
    out = p.stdout.decode('utf-8', 'replace')
    return p.returncode, out


def jcli(*args, timeout=60):
    rc, out = cli(*args, timeout=timeout)
    try:
        return json.loads(out)
    except Exception:
        return {'_raw': out, '_rc': rc}


def pet_rect():
    d = jcli('window', 'list-visible')
    for w in d.get('windows', []):
        if w.get('title') == PET_TITLE:
            r = w['window_region']
            return (r[0], r[1], r[2], r[3], w.get('process_id'), w.get('z_order'))
    return None


def main():
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    os.makedirs(TMP, exist_ok=True)

    # 0. 宠物必须在跑
    t0 = time.time()
    r = pet_rect()
    if r is None:
        print('★ 没有找到 %r 窗口 —— 请先启动桌宠' % PET_TITLE)
        return 2
    print('宠物窗口 (l,t,r,b)=(%d,%d,%d,%d) pid=%s' % r[:5])
    print('检测耗时 %.2fs' % (time.time() - t0))

    # 1. 经验采集任务（小助手要求先建；同名已存在则忽略报错）
    exp = jcli('experience', 'create', '--name', PROJECT,
               '--goal', '验证桌宠跳跃的竖直抛物线在真机上已经修复',
               '--expected-result', '录像中出现完整跳跃；逐帧轨迹顶点高于起点且只变向一次',
               '--forbidden', '不要改动任何文件')
    print('[experience create] ok=%s %s' % (exp.get('ok'), exp.get('error', '')))

    # 2. 开始录制
    st = jcli('recording', 'start', '--project', PROJECT,
              '--purpose', 'handle_jump 抛物线真机验收（用户视角逐帧对比）')
    print('[recording start] %s' % json.dumps(st, ensure_ascii=False))
    if not st.get('ok'):
        print('★ 录制未启动，终止')
        return 3

    # 3. 逐秒采样
    rows = []
    print('采样 %d 秒 …' % secs)
    t_start = time.time()
    with open(OUT_CSV, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('t,x1,y1,x2,y2,pid,z\n')
        for i in range(secs):
            ts = time.time() - t_start
            rr = pet_rect()
            if rr:
                fh.write('%.3f,%d,%d,%d,%d,%s,%s\n' % (ts, rr[0], rr[1], rr[2], rr[3], rr[4], rr[5]))
                rows.append((ts, rr[0], rr[1], rr[2], rr[3]))
            else:
                fh.write('%.3f,,,,,,\n' % ts)
            fh.flush()
            time.sleep(1.0)

    # 4. 停止
    sp = jcli('recording', 'stop', timeout=120)
    print('[recording stop] %s' % json.dumps(sp, ensure_ascii=False, indent=2))

    # 5. 采样小结
    print('=' * 74)
    print('窗口矩形采样：%d 个点 / %d 秒' % (len(rows), secs))
    if rows:
        ys = [r[2] for r in rows]
        xs = [r[1] for r in rows]
        print('x 范围 [%d, %d]  跨度 %d px' % (min(xs), max(xs), max(xs) - min(xs)))
        print('y 范围 [%d, %d]  跨度 %d px' % (min(ys), max(ys), max(ys) - min(ys)))
        # 相邻采样的竖直位移（1Hz 粗粒度，只能看量级；精细判据交给逐帧差分）
        dy = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        print('相邻 1s 的 dy 序列（前 40 个）：%s' % dy[:40])
        print('最大上移 %d px / 最大下移 %d px' % (min(dy) if dy else 0, max(dy) if dy else 0))
    print('CSV = %s' % OUT_CSV)
    return 0


if __name__ == '__main__':
    sys.exit(main())
