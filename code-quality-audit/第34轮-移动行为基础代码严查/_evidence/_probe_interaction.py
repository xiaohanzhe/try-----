# -*- coding: utf-8 -*-
"""task#14 探针：pet_interaction 手势状态机疑点（全部调产品真类）"""
import os, sys, time, traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '19_交互手势探针.txt')
L = []
def log(s): L.append(s)
def flush(): open(OUT, 'w', encoding='utf-8').write("\n".join(L) + "\n")
def check(c, m): log(("[PASS] " if c else "[FAIL] ") + m)

try:
    from pet_interaction import (GestureTracker, _StrokeDetector, BodyPart, Gesture,
                                 PetInteractionTracker)

    # ---------- Y1: 长按不更新 last_click_time ----------
    log("========== Y1：长按是否会污染 consecutive_clicks ==========")
    g = GestureTracker()
    # 第一次：普通单击 ear（建立 last_click_time）
    g.on_press((10, 10), BodyPart.EAR); time.sleep(0.02)
    e1 = g.on_release((10, 10))
    log("单击1 -> %s  clicks=%d last_click_time=%.3f" % (e1.gesture if e1 else None,
        g.consecutive_clicks, g.last_click_time))
    # 第二次：长按（>=0.5s）ear → 走 PINCH 分支，不更新 last_click_time
    g.on_press((10, 10), BodyPart.EAR); time.sleep(0.55)
    e2 = g.on_release((10, 10))
    log("长按 -> %s  clicks=%d last_click_time=%.3f（应保持不变）" % (e2.gesture if e2 else None,
        g.consecutive_clicks, g.last_click_time))
    t_after_long = g.last_click_time
    # 立刻（<0.6s gap 仍在窗口内）再单击 ear → 会接续旧计数
    g.on_press((10, 10), BodyPart.EAR); time.sleep(0.02)
    e3 = g.on_release((10, 10))
    log("长按后立刻单击 -> %s  clicks=%d gap=%.3f（gap 是相对长按前那次算的）"
        % (e3.gesture if e3 else None, g.consecutive_clicks,
           time.time() - t_after_long))
    check(True, "Y1 观察：长按后 last_click_time 未被刷新（gap 会虚高，计数可能连号）")

    # ---------- Y2: 横/纵向共用 _last_dx_sign ----------
    log("")
    log("========== Y2：_StrokeDetector 横向/纵向符号是否串味 ==========")
    sd = _StrokeDetector()
    # 交替：右、上、左、下 —— 每次都是"方向变化"，应有 4 次变化
    seq = [(10, 0), (0, 10), (-10, 0), (0, -10)]
    changes = 0
    for dx, dy in seq:
        sd.feed(dx, dy, BodyPart.TORSO)
        log("  feed(dx=%+d, dy=%+d) -> direction_changes=%d last_sign=%s"
            % (dx, dy, sd._direction_changes, sd._last_dx_sign))
    n_changes = sd._direction_changes
    check(n_changes >= 3,
          "Y2a 交替横纵序列累计方向变化 >= 3（实测 %d，理论 4）" % n_changes)

    # 纯纵向往返：上、下、上、下 —— 也应产生方向变化
    sd2 = _StrokeDetector()
    for dy in (10, -10, 10, -10):
        sd2.feed(0, dy, BodyPart.TORSO)
    log("  纯纵向往返 (下/上/下/上) -> direction_changes=%d" % sd2._direction_changes)
    check(sd2._direction_changes >= 3,
          "Y2b 纯纵向往返也能累计（实测 %d）" % sd2._direction_changes)

    # 混合陷阱：横右 → 纵上 → 横右 → 纵上（水平方向**没变**，纵向在变）
    sd3 = _StrokeDetector()
    for dx, dy in [(10, 0), (0, 10), (10, 0), (0, 10)]:
        sd3.feed(dx, dy, BodyPart.TORSO)
    log("  横向恒右 + 纵向恒上 的交替 -> direction_changes=%d last_sign=%s"
        % (sd3._direction_changes, sd3._last_dx_sign))
    check(True, "Y2c 观察：横向恒右时，纵向步把符号翻来翻去（实测 changes=%d）"
          % sd3._direction_changes)

    # ---------- Y3: 抚摸在 drag/follow 下的行为 ----------
    log("")
    log("========== Y3：drag/follow 抑制 ==========")
    t = PetInteractionTracker()
    t.set_drag_active(True)
    r = t.handle_press((10, 10))
    log("drag 中 handle_press -> %r, is_pressing=%s" % (r, t.gesture.is_pressing))
    check(not t.gesture.is_pressing, "Y3a drag 中按下被忽略")
    r = t.handle_release((10, 10))
    check(r is None, "Y3b drag 中释放返回 None")
    t.set_drag_active(False)
    t.set_follow_active(True)
    t.handle_press((10, 10))
    log("follow 中 handle_press -> is_pressing=%s" % t.gesture.is_pressing)
    check(not t.gesture.is_pressing, "Y3c follow 中按下也被忽略")

    # ---------- Y4: 空精灵时 is_on_pet 回退 ----------
    log("")
    log("========== Y4：无精灵时的区域判定 ==========")
    from pet_interaction import BodyRegionMapper
    m = BodyRegionMapper()   # 没 set_sprite
    log("空 mapper: is_on_pet(10,10)=%s classify=%s" % (m.is_on_pet(10, 10), m.classify(10, 10)))
    check(m.classify(10, 10) == BodyPart.WHOLE_BODY,
          "Y4  空精灵 classify 返回 WHOLE_BODY（不越界）")

except Exception:
    log("!! 探针异常:\n" + traceback.format_exc())
finally:
    flush()
print("done ->", OUT)
