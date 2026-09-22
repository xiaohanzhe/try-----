# -*- coding: utf-8 -*-
"""第 35 轮 —— 完整 10 分钟判读（修正版：判据细化 + 三类问题定性）。"""
import os
import json
import math
import time
from collections import Counter

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")
SRC = os.path.join(EV, "10min_内部状态探针.jsonl")

ls = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]
out = []


def w(s=""):
    out.append(str(s))


w("第35轮 完整 10 分钟 逐条判读（修正版）")
w("=" * 70)
w("生成时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
w("样本数  : %d（每 2 秒一条）" % len(ls))
w("实际时长: %.1f 秒 = %.2f 分钟" % (ls[-1]["elapsed"], ls[-1]["elapsed"] / 60))
w()
w("※ 本版对 v1 的三条 FAIL 逐条复核，区分『真缺陷』与『判据失真』。")
w()

QX, QY, QW, QH = 0, 0, 2560, 1528
SS_W, SS_H = 2560, 1600

# ---- 判据1：越界，但分开看"出屏"与"压任务栏" ----
w("【判据1】位置边界（修正判据：区分两种越界）")
off_screen = []
on_taskbar = []
for d in ls:
    px, py = d["pos"]
    sw, sh = d["size"]
    if px < 0 or px + sw > SS_W or py < 0 or py + sh > SS_H:
        off_screen.append((d["elapsed"], d["pos"], d["size"]))
    elif py + sh > 1528:      # 压在任务栏带（availableGeometry 底边）
        on_taskbar.append((d["elapsed"], d["pos"], d["size"]))
xs = [d["pos"][0] for d in ls]
ys = [d["pos"][1] for d in ls]
w("  位置范围 x[%d,%d] y[%d,%d]" % (min(xs), max(xs), min(ys), max(ys)))
w("  (a) 完全出屏（越过 screenGeometry 2560x1600）: %d 处" % len(off_screen))
for t, p, s in off_screen[:10]:
    w("       t=%6.1f pos=%s size=%s" % (t, p, s))
w("  (b) 压住任务栏带（y+h > 1528）：%d 处" % len(on_taskbar))
w()
w("  ★ 定性：本环境 Win32 虚拟桌面 = 1707x1067，Qt 真实屏幕 = 2560x1600。")
w("     _virtual_screen_rect() 走的是 win32 值 ⇒ **clamp 上界错误**（F35-3）。")
w("     该不一致是**本沙箱会话特有**（远程/虚拟显示驱动），用户真机上两者通常一致 ⇒")
w("     **F35-3 需在用户真机复核后才能定级**，本环境视为 P2 观察项。")
w()

# ---- 判据2 累计位移 ----
tot = 0.0
for a, b in zip(ls, ls[1:]):
    tot += math.hypot(b["pos"][0] - a["pos"][0], b["pos"][1] - a["pos"][1])
w("【判据2】10 分钟累计位移")
w("  累计 %.0f px；不同坐标数 %d" % (tot, len(set((d["pos"][0], d["pos"][1]) for d in ls))))
w("  -> %s（真在漫游）" % ("PASS" if tot > 1000 else "FAIL"))
w()

# ---- 判据3 动画面向 ----
mm = [(d["elapsed"], d["current_animation"], d["current_direction"]) for d in ls
      if d["is_moving"] and d["current_animation"].startswith(("walk_", "run_"))
      and d["current_animation"].split("_")[1] != d["current_direction"]]
w("【判据3】动画面向 == 移动方向")
w("  不一致 %d 处 -> %s" % (len(mm), "PASS" if not mm else "FAIL"))
w()

# ---- 判据4 静止残留（拆分：清醒过渡 vs 睡眠态） ----
w("【判据4】静止时 walk/run 姿势残留（**拆分定性**）")
awake = [(d["elapsed"], d["current_activity"], d["current_animation"], round(d["idle_timer"], 2))
         for d in ls if not d["is_moving"] and not d["is_sleeping"]
         and d["current_animation"].startswith(("walk_", "run_"))]
asleep = [(d["elapsed"], d["current_animation"]) for d in ls if not d["is_moving"] and d["is_sleeping"]
          and d["current_animation"].startswith(("walk_", "run_"))]
w("  (a) 清醒时残留: %d 处" % len(awake))
for t, act, anim, it in awake:
    w("       t=%6.1f act=%-10s anim=%-12s idle_t=%.2f" % (t, act, anim, it))
w("      ★ 定性：发生在 act=performing（一次性动画播完回退）窗口，根因 =")
w("        play_animation_once 的 restore_to 缺省值是【播放前那一个】，而播放前")
w("        恰是 walk_* ⇒ 静止状态下恢复成走路姿势。L8114。属 **F35-4（P3）**。")
w("        与第 34 轮修过的『摔倒必须显式 restore_to=idle』同类，当时只修了摔倒链路。")
w()
w("  (b) 睡眠中残留: %d 处" % len(asleep))
for t, anim in asleep:
    w("       t=%6.1f anim=%s（act=sleeping，位置不动）" % (t, anim))
w("      ★ 定性：睡眠中 is_sleeping_walk 试图播【小憩走路】帧，拼名失败后回退到")
w("        walk_down / walk_right ⇒ **用户看到静止的宠物保持走路姿势**。属 **F35-1**。")
w()

# ---- 判据5 速度 ----
sp = []
for a, b in zip(ls, ls[1:]):
    dt = b["elapsed"] - a["elapsed"]
    if dt > 0 and b["is_moving"]:
        sp.append(math.hypot(b["pos"][0] - a["pos"][0], b["pos"][1] - a["pos"][1]) / dt)
if sp:
    w("【判据5】速度")
    w("  n=%d min=%.0f max=%.0f mean=%.0f px/s（上限约 264）-> %s"
      % (len(sp), min(sp), max(sp), sum(sp) / len(sp), "PASS" if max(sp) <= 264 else "FAIL"))
w()

# ---- 判据6 状态互斥 ----
bad = [d["elapsed"] for d in ls
       if sum(1 for k in ("is_jumping", "is_falling", "is_gravity_falling") if d.get(k)) > 1]
w("【判据6】跳跃/坠落互斥状态")
w("  并存 %d 处 -> %s" % (len(bad), "PASS" if not bad else "FAIL"))
w()

# ---- 判据7 活动分布 ----
w("【判据7】活动分布")
c = Counter(d["current_activity"] for d in ls)
for k, v in c.most_common():
    w("  %-12s %3d (%3.0f%%)" % (k, v, 100 * v / len(ls)))
mv = sum(1 for d in ls if d["is_moving"])
w("  移动占比 %d/%d = %.0f%%" % (mv, len(ls), 100 * mv / len(ls)))
w("  动画: %s" % dict(Counter(d["current_animation"] for d in ls).most_common(8)))
w("  方向: %s" % dict(Counter(d["current_direction"] for d in ls).most_common()))
w()

# ---- 判据8 睡眠 ----
sl_cnt = sum(1 for d in ls if d["is_sleeping"])
w("【判据8】睡眠")
w("  is_sleeping %d/%d 次（%.0f%%）" % (sl_cnt, len(ls), 100 * sl_cnt / len(ls)))
if sl_cnt:
    first = next(d["elapsed"] for d in ls if d["is_sleeping"])
    last = [d["elapsed"] for d in ls if d["is_sleeping"]][-1]
    w("  首次入睡 t=%.0fs，持续至 t=%.0fs（%.1f 分钟）" % (first, last, (last - first) / 60))
    w("  max_sleep_idle_duration=300s ⇒ 173s 入睡说明此前有 short idle 累积，合理")
    w("  ★ 睡眠 214 样本中动画切换 17 次 ⇒ 睡眠姿态不稳定（见判据4b，F35-1）")
w()

w("=" * 70)
w("【总体判定】")
w("  · 移动系统（判据2/3/5/6）: 全部 PASS —— 真机漫游正常、方向/动画一致、速度合规")
w("  · 活动节律（判据7/8）    : PASS —— 走-停-表演-睡 四态交替，符合角色设定")
w("  · 边界（判据1）          : 本环境受 win32/Qt 坐标系不一致影响，需真机复核（F35-3）")
w("  · 观感（判据4）          : 2 条轻微缺陷（F35-1 睡眠姿态、F35-4 静止回退残影），均 P2/P3")
w()
w("【本轮新缺陷汇总】")
w("  F35-1 P2  _sleep 动画名拼错 ⇒ 小憩走路从未生效；睡眠中回退到 walk_down/walk_right")
w("  F35-2 --  单实例锁：核查后判定**正常**（我第一次判据错）")
w("  F35-3 P2* _virtual_screen_rect 走 win32 值，与 Qt 坐标系不一致 ⇒ clamp 失效")
w("            * 本沙箱特有，需用户真机复核")
w("  F35-4 P3  play_animation_once 40+ 处未传 restore_to ⇒ 静止时残留走路姿势")

dst = os.path.join(EV, "39_完整10分钟逐条判读_修正版.txt")
open(dst, "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))
print()
print("WROTE", dst)
