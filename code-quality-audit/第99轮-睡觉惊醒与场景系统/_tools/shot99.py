# -*- coding: utf-8 -*-
u"""shot99.py —— 第99轮「睡觉后惊醒」录制的**分析端**。

读 `_evidence/rec99_frames.csv`（录制端每 250 ms 一行，列由**产品代码自己**填），
输出：
  1. `rec99_timeline.txt` —— 只列"发生变化的那些帧"（动画/睡眠/惊讶/迷糊计数），
     人眼一眼能读完；
  2. 断言块 —— 把 C3a/C3b 的两条口径（醒 + 受惊 + 画面落到 `surprised_down`）
     在**录像数据**上再证一次；
  3. 关键帧 PNG —— 从 `rec99_raw.avi` 取"睡着 / 第一拍 / 第二拍 / 变脸后"四帧，
     拼成一张对照图 `rec99_contact_sheet.png`（★ 走 `imencode` + 手写，
     `cv2.imwrite` 在中文路径下静默失败）。

★ 纪律：判据**只看产品字段**（`sleeping` / `spr` / `stir` / `anim`），
  不从像素里"猜"状态；像素只用来给人眼看。

★★ 第99轮修正（判据自伤记录）：`stir == 2` 是**瞬态值** —— 它在
  `self._sleep_stir_count = 2` 之后的**下一条语句**就被 `self.wake_up()`
  （内含 `delattr(self, '_sleep_stir_count')`）清掉了，250 ms 采样几乎抓不到。
  ⇒ **抓不到是"采样盲区"，不是产品缺陷**，该条已降级为"只打印、不判分"；
  真正的守卫改成"**第一拍之后、惊醒之前仍有帧在睡**" + 与
  `rec99_inject.txt` 的 poke#1/#2 时刻对账。
"""
import csv
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.environ.get('REC99_EVDIR') or os.path.join(ROUND, '_evidence')
CSV = os.path.join(EV, 'rec99_frames.csv')
RAW = os.path.join(EV, 'rec99_raw.avi')
OUT = os.path.join(EV, 'rec99_timeline.txt')
SHEET = os.path.join(EV, 'rec99_contact_sheet.png')


def _read_rows(path):
    """★ 字节忠实读取（`newline=''`）再逐格剥 `\r` ⇒ 换行风格变了也不会取不到键。"""
    rows = []
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            rows.append({(k or '').strip(): (v.strip() if isinstance(v, str) else v)
                         for k, v in r.items()})
    return rows


def _b(v):
    return str(v).strip().lower() in ('true', '1', 'yes')


def main():
    if not os.path.isfile(CSV):
        print('[shot99] 缺 %s' % CSV)
        return 2
    rows = _read_rows(CSV)
    print('[shot99] 帧数 = %d' % len(rows))
    if not rows:
        return 2

    # ---- 1. 变化帧时间线 ----
    keys = ('anim', 'sleeping', 'spr', 'stir', 'dir', 'p1o')
    prev = None
    lines = []
    for r in rows:
        cur = tuple(r.get(k) for k in keys)
        if cur != prev:
            lines.append('f=%-5s t=%-8s anim=%-18s dir=%-6s sleeping=%-6s spr=%-6s '
                         'stir=%-5s p1o=%-6s pos=(%s,%s) %sx%s'
                         % (r.get('frame'), r.get('t'), r.get('anim'), r.get('dir'),
                            r.get('sleeping'), r.get('spr'), r.get('stir'),
                            r.get('p1o'), r.get('wx'), r.get('wy'),
                            r.get('ww'), r.get('wh')))
            prev = cur
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(u'=== rec99 变化帧时间线（列：frame/t/anim/dir/sleeping/spr/stir/p1o/pos/size）===\n')
        fh.write(u'\n'.join(lines) + u'\n')
    print('[shot99] 变化帧 %d 行 -> %s' % (len(lines), OUT))
    for ln in lines:
        print('  ' + ln)

    # ---- 2. 断言块（只看产品字段）----
    n_pass = 0
    n_fail = 0

    def ck(desc, cond, detail=''):
        nonlocal n_pass, n_fail
        if cond:
            n_pass += 1
            print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
        else:
            n_fail += 1
            print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))

    # ---- 先定位三个关键索引（后面多条判据共用）----
    first_stir_i = next((i for i, r in enumerate(rows)
                         if str(r.get('stir')) in ('1', '2')), None)
    first_spr_i = next((i for i, r in enumerate(rows) if _b(r.get('spr'))), None)
    # ★ "第一拍之后首次不睡" —— 只认 `stir` 之后，避免被起手的 `walk_down`(sleeping=False) 骗到
    first_wake_after_stir = None
    if first_stir_i is not None:
        for i in range(first_stir_i + 1, len(rows)):
            if not _b(rows[i].get('sleeping')):
                first_wake_after_stir = i
                break

    slept = [r for r in rows if _b(r.get('sleeping'))]
    ck('录像里出现了"睡着"段（否则这段录像没测到东西）', len(slept) > 0,
       'sleeping=True 帧数=%d' % len(slept))

    stirs = [r for r in rows if str(r.get('stir')) == '1']
    ck('录像里出现了"第一拍"（`_sleep_stir_count == 1`）', len(stirs) > 0,
       '帧数=%d' % len(stirs))

    # ★★ 第99轮修正：`_sleep_stir_count == 2` 是**瞬态**——它与 `wake_up()`（内含
    #    `delattr(self,'_sleep_stir_count')`）在**同一 tick 内**完成，250 ms 采样几乎
    #    不可能抓到。**抓不到是"采样盲区"，不是产品缺陷** ⇒ 此条**只打印、不判分**，
    #    真正的守卫是下面那条"第一拍之后仍在睡"（它是首版真缺陷的直接守卫）。
    stirs2 = [r for r in rows if str(r.get('stir')) == '2']
    print('[shot99] 提示：`stir == 2` 帧数=%d'
          '（瞬态值，与 wake_up() 同 tick 被清 ⇒ 采样盲区，不作判据）' % len(stirs2))

    # ★★★ 真守卫（防"两拍塌成一拍"）：第一拍之后、首次惊醒之前，**必须仍有帧在睡**。
    #    首版真缺陷正是"碰一下当帧就醒"（`elif` 没判"又发生了一次互动"）—— 此条直接守住它。
    still_asleep = ([rows[i] for i in range(first_stir_i + 1, first_wake_after_stir)
                     if _b(rows[i].get('sleeping'))]
                    if (first_stir_i is not None and first_wake_after_stir is not None) else [])
    ck('★★★ 真守卫（防"两拍塌一拍"）：第一拍之后、惊醒之前**仍有帧在睡**'
       ' —— 首版真缺陷正是"碰一下当帧就醒"',
       len(still_asleep) > 0,
       '第一拍后仍在睡帧数=%d（first_stir_i=%s first_wake=%s）'
       % (len(still_asleep), first_stir_i, first_wake_after_stir))

    # ★ C3a：第二拍之后必须"醒了且受惊"（`is_sleeping=False` 且 `is_surprised=True`）
    woke_surprised = [r for r in rows if (not _b(r.get('sleeping'))) and _b(r.get('spr'))]
    ck('★★★ C3a 录像上复现"醒了且受惊"（sleeping=False 且 spr=True）',
       len(woke_surprised) > 0, '帧数=%d' % len(woke_surprised))

    # ★ C3b：画面必须真的落到 `surprised_down`
    face = [r for r in rows if r.get('anim') == 'surprised_down']
    ck('★★★ C3b 画面**真落到** `surprised_down`（不是只置标志）',
       len(face) > 0, '帧数=%d' % len(face))

    # ★ 负控制：惊讶段之前不能出现 surprised_down（否则"醒来就有"就说不清了）
    ck('★负控制：`spr=True` 之前**从未**出现 `surprised_down`'
       '（证明那一段脸确实由"第二拍"引发，不是默认值）',
       first_spr_i is not None
       and all(r.get('anim') != 'surprised_down' for r in rows[:first_spr_i]),
       'first_spr_i=%s' % first_spr_i)

    # ★ 顺序：第一拍（look_up）必须排在惊讶段之前（否则"先醒后惊"的顺序无从谈起）
    ck('★顺序：第一拍（stir=1）出现在惊讶（spr=True）之前（先迷糊、后惊醒）',
       first_stir_i is not None and first_spr_i is not None
       and first_stir_i < first_spr_i,
       'first_stir_i=%s first_spr_i=%s' % (first_stir_i, first_spr_i))

    # ---- 2b. 与"注入时刻"对账（poke#1 / poke#2 的绝对秒）----
    #   ★ 这两条把"录像里的状态跃迁"钉死在"产品真的被点了两次"上，
    #     而不是"录着录着自己变的"。
    inj = {}
    INJ = os.path.join(EV, 'rec99_inject.txt')
    if os.path.isfile(INJ):
        with io.open(INJ, 'r', encoding='utf-8') as fh:
            for ln in fh:
                m = re.search(r't=([0-9.]+)', ln)
                if not m:
                    continue
                if 'poke#1' in ln:
                    inj['p1'] = float(m.group(1))
                elif 'poke#2' in ln:
                    inj['p2'] = float(m.group(1))
    print('[shot99] 注入时刻：poke1=%s poke2=%s' % (inj.get('p1'), inj.get('p2')))

    t_stir1 = float(rows[first_stir_i].get('t')) if first_stir_i is not None else None
    t_spr = float(rows[first_spr_i].get('t')) if first_spr_i is not None else None

    ck('★★★ 对账：第一拍（stir 首帧）**不早于** poke#1'
       '（先被点，才迷糊 —— 排除"自己醒的"）',
       t_stir1 is not None and inj.get('p1') is not None and t_stir1 >= inj['p1'],
       't_stir1=%s poke1=%s' % (t_stir1, inj.get('p1')))

    ck('★★★ 对账：`spr` 首帧**晚于** poke#1（不是碰第一下就惊）',
       t_spr is not None and inj.get('p1') is not None and t_spr > inj['p1'],
       't_spr=%s poke1=%s' % (t_spr, inj.get('p1')))

    ck('★★★ 对账：`spr` 首帧**不早于** poke#2，且在惊讶窗口（+2.0 s）内'
       '（正是"第二次互动"触发，且没有无限拖后）',
       t_spr is not None and inj.get('p2') is not None
       and inj['p2'] <= t_spr <= inj['p2'] + 2.0,
       't_spr=%s poke2=%s（差 %.3f s）'
       % (t_spr, inj.get('p2'),
          (t_spr - inj['p2']) if (t_spr is not None and inj.get('p2') is not None) else -1))

    # ---- 3. 关键帧对照图 ----
    try:
        import cv2
        import numpy as np
    except Exception as e:
        print('[shot99] 无 cv2/numpy，跳过对照图：%r' % (e,))
        print('[shot99] 结果：PASS=%d FAIL=%d' % (n_pass, n_fail))
        return 0 if n_fail == 0 else 1

    cap = cv2.VideoCapture(RAW)
    if not cap.isOpened():
        print('[shot99] 打不开录像 %s' % RAW)
        print('[shot99] 结果：PASS=%d FAIL=%d' % (n_pass, n_fail))
        return 0 if n_fail == 0 else 1
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    def grab(idx):
        if idx < 0 or (total and idx >= total):
            return None
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        return fr if ok else None

    def crop(fr, r):
        if fr is None:
            return None
        pad = 30
        x = int(float(r.get('wx') or 0))
        y = int(float(r.get('wy') or 0))
        w = int(float(r.get('ww') or 0))
        h = int(float(r.get('wh') or 0))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(fr.shape[1], x + w + pad)
        y1 = min(fr.shape[0], y + h + pad)
        return fr[y0:y1, x0:x1]

    # 四个时刻：睡着 / 第一拍(look_up) / 第二拍那一刻 / 变脸后
    idx_sleep = next((i for i, r in enumerate(rows) if _b(r.get('sleeping'))), None)
    idx_stir = next((i for i, r in enumerate(rows)
                     if str(r.get('stir')) == '1'), None)
    # ★ `stir=2` 是瞬态、采样抓不到 ⇒ 第三格改用"第一拍之后仍在睡"那一帧，
    #   它才是"两拍没有被塌成一拍"的**可视**证据。
    idx_gap = None
    if first_wake_after_stir is not None and first_stir_i is not None:
        _g = first_wake_after_stir - 1
        if _g > first_stir_i:
            idx_gap = _g
    idx_face = next((i for i, r in enumerate(rows)
                     if r.get('anim') == 'surprised_down'), None)

    picks = []
    for _tag, _i in ((u'sleep', idx_sleep), (u'stir#1 look_up', idx_stir),
                     (u'still asleep', idx_gap),
                     (u'woken: surprised_down', idx_face)):
        print('[shot99] 关键时刻 %-24s idx=%s' % (_tag, _i))
        picks.append((_tag, _i))

    # 光看 idx 行不够 —— 直接按 CSV 行号取样（rec99 每 TICK 一帧，序号即帧号）
    tiles = []
    for _tag, _i in picks:
        if _i is None:
            continue
        r = rows[_i]
        fr = grab(int(r.get('frame') or _i))
        c = crop(fr, r)
        if c is None or not c.size:
            continue
        c = cv2.resize(c, (max(1, c.shape[1]), max(1, c.shape[0])))
        # 顶部留白写标签（ASCII 标签，避免 cv2 无中文字体）
        band = np.zeros((26, c.shape[1], 3), np.uint8)
        cv2.putText(band, '%s  f=%s t=%ss spr=%s stir=%s' % (_tag, r.get('frame'),
                    r.get('t'), r.get('spr'), r.get('stir')), (4, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(np.vstack([band, c]))
    cap.release()

    if tiles:
        hmax = max(t.shape[0] for t in tiles)
        padded = []
        for t in tiles:
            if t.shape[0] < hmax:
                pad = np.zeros((hmax - t.shape[0], t.shape[1], 3), np.uint8)
                t = np.vstack([t, pad])
            padded.append(t)
        gap = np.full((hmax, 10, 3), 40, np.uint8)
        merged = padded[0]
        for t in padded[1:]:
            merged = np.hstack([merged, gap, t])
        _ok, _buf = cv2.imencode('.png', merged)
        if _ok:
            with open(SHEET, 'wb') as fh:
                fh.write(_buf.tobytes())
            print('[shot99] 对照图 -> %s (%dx%d)' % (SHEET, merged.shape[1], merged.shape[0]))
        else:
            print('[shot99] imencode 失败')
    else:
        print('[shot99] 没有可用对照帧')

    print('[shot99] 结果：PASS=%d FAIL=%d' % (n_pass, n_fail))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
