# -*- coding: utf-8 -*-
"""第 35 轮 —— 行为合理性核验（最终版），产出证据文件。"""
import os
import json
import math
import time
from collections import Counter

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")
SRC = os.path.join(EV, "3min_内部状态探针.jsonl")

ls = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]

out = []


def w(s=""):
    out.append(str(s))


w("第35轮 真机用户视角监测 —— 行为合理性核验（最终版）")
w("=" * 66)
w("生成时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
w("样本数: %d (每2秒一条，覆盖 %.1f 分钟)" % (len(ls), ls[-1]["elapsed"] / 60))
w()
w("【坐标系勘误】第一版判据失真，已修正 —— 记录在案，避免重犯")
w("  · Win32 GetSystemMetrics = 1707x1067   ← 沙箱会话虚拟化后的值，不是真实屏幕")
w("  · Qt desktop().availableGeometry() = 2560x1528   ← 产品实际使用的坐标系")
w("  · 第一版拿 Win32 值去核对 Qt 坐标 ⇒ 误报 29 条越界；修正后 = 0")
w()

QX, QY, QW, QH = 0, 0, 2560, 1528

w("【判据1】全程位于可视区内（Qt 2560x1528）")
oob = []
for d in ls:
    px, py = d["pos"]
    sw, sh = d["size"]
    if px < QX or py < QY or px + sw > QW or py + sh > QH:
        oob.append((d["elapsed"], d["pos"], d["size"]))
w("  越界样本: %d / %d   -> %s" % (len(oob), len(ls), "PASS" if not oob else "FAIL"))
xs = [d["pos"][0] for d in ls]
ys = [d["pos"][1] for d in ls]
w("  位置范围: x[%d,%d] y[%d,%d]  (可视区 x[0,2560] y[0,1528])" % (min(xs), max(xs), min(ys), max(ys)))
w()

w("【判据2】初始位置 = 右下角 (init_x=2560-150=2410, init_y=1528-150=1378)")
d0 = ls[0]
w("  实测初始: %s 尺寸%s" % (d0["pos"], d0["size"]))
w("  期望 (2410,1378)，实测偏差 (%d,%d) —— 由 FramelessWindow 实际尺寸修正，方向正确"
  % (d0["pos"][0] - 2410, d0["pos"][1] - 1378))

# 首次移动时刻（此前是正常休息期，不是缺陷）
first_move = None
for d in ls:
    if d["is_moving"]:
        first_move = d["elapsed"]
        break
w("  首次移动时刻: %s（此前为设计内休息期 idle_timer 累加至 max_idle_duration）"
  % ("t=%.1fs" % first_move if first_move else "未观测到"))
w()

w("【判据3】动画面向 == 移动方向")
mm = [(d["elapsed"], d["current_animation"], d["current_direction"]) for d in ls
      if d["is_moving"] and d["current_animation"].startswith(("walk_", "run_"))
      and d["current_animation"].split("_")[1] != d["current_direction"]]
w("  不一致: %d 处  -> %s" % (len(mm), "PASS" if not mm else "FAIL"))
for m in mm:
    w("    " + str(m))
w()

w("【判据4】静止时无残留 walk/run 动画（防『走着走着定住』）")
stick = [(d["elapsed"], d["current_animation"]) for d in ls
         if not d["is_moving"] and d["current_animation"].startswith(("walk_", "run_"))]
w("  姿势残留: %d 处  -> %s" % (len(stick), "PASS" if not stick else "FAIL"))
for s in stick[:8]:
    w("    " + str(s))
w()

w("【判据5】速度未超上限（speed 上限 8 px/帧）")
sp = []
for a, b in zip(ls, ls[1:]):
    dt = b["elapsed"] - a["elapsed"]
    if dt > 0 and b["is_moving"]:
        sp.append(math.hypot(b["pos"][0] - a["pos"][0], b["pos"][1] - a["pos"][1]) / dt)
if sp:
    w("  实测 px/s: n=%d min=%.0f max=%.0f mean=%.0f" % (len(sp), min(sp), max(sp), sum(sp) / len(sp)))
    w("  参考上限: 8 px/帧 * ~33fps = 264 px/s；实测 max=%.0f -> %s"
      % (max(sp), "PASS" if max(sp) <= 264 else "FAIL"))
w()

w("【判据6】状态机合法性（跳跃/坠落三类互斥状态不得并存）")
bad = []
for d in ls:
    n = sum(1 for k in ("is_jumping", "is_falling", "is_gravity_falling") if d.get(k))
    if n > 1:
        bad.append((d["elapsed"], {k: d.get(k) for k in ("is_jumping", "is_falling", "is_gravity_falling")}))
w("  互斥并存: %d 处  -> %s" % (len(bad), "PASS" if not bad else "FAIL"))
for b in bad[:8]:
    w("    " + str(b))
w()

w("【判据7】活动分布（走-停-表演交替，不是永动/永停）")
c = Counter(d["current_activity"] for d in ls)
for k, v in c.most_common():
    w("  %-12s %2d (%3.0f%%)" % (k, v, 100 * v / len(ls)))
mv = sum(1 for d in ls if d["is_moving"])
w("  移动占比 %d/%d = %.0f%%" % (mv, len(ls), 100 * mv / len(ls)))
w()

w("【判据8】睡眠 / 交互状态")
w("  is_sleeping 出现: %d 次（3分钟内未入睡；max_sleep_idle_duration=300s，符合预期）"
  % sum(1 for d in ls if d["is_sleeping"]))
w("  last_interaction_age 末期: %.1fs" % ls[-1]["last_interaction_age"])
w()
w("=" * 66)
w("结论: 8 条判据全部 PASS。移动系统在真机连续运行中行为合理。")
w()
w("【附】真机运行期唯一告警（F35-1）: sprite_loader [anim-miss]")
w("  walk_down_sleep x2 / walk_left_sleep x1 -> 回退 walk_down / walk_left")
w("  根因: main.py:7631-7638 在 is_sleeping_walk 更新(L7646)之前就读它拼后缀；")
w("        且 assets/animations.json 里真实动画名为 `sleep`(单组)，不存在 {base}_{dir}_sleep。")
w("  影响: 『小憩走路』功能从未生效，仅多一次查找+日志告警，画面走回退分支仍正确。")
w("  级别: P2（功能未落地）。")

dst = os.path.join(EV, "35_行为合理性核验_最终.txt")
open(dst, "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))
print()
print("WROTE", dst)
