# -*- coding: utf-8 -*-
u"""第181轮 · 把 probe181 的原始指令解析成「门型 → 换房规则」（只读）。

输入：`D:\\_tmp181\\probe181.ch{1..5}.txt`（`probe181.csx` 产出）
输出：`_evidence/door_rules.tsv` 与屏显摘要

解析口径（**逐指令线性重建**，不做完整控制流分析）：
  · `room_goto(X)`      —— Call 前最近一个常量 push 即目标房间号
  · `room_goto_next`    —— 位移 +1
  · `room_goto_previous` —— 位移 −1
  · `room_next` / `room_previous` 连续 N 次 —— 位移 ±N
  · `room_goto(doorRoom)` 等变量形式 —— 记 `VAR`
  · 守卫：`PushBltn VAR=room` + `PushI N` + `Cmp` ⇒ `room==N`；
          `PushGlb VAR=plot` 等 ⇒ 记变量名，条件值一并记
  · `event_user(k)` —— 该事件可能转到别的对象（如 `obj_doorAny`），记 `event_user:k`

★ 判据不许建 `entrance` 数值（各章不同：ch1 是 1/2/4/5，ch2 起是 1/2/3/4）。
"""
import io
import json
import os
import re
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
WORK = os.environ.get('P181_WORK', r'D:\_tmp181')

CODE_HDR = re.compile(r'^### CODE (\S+)\s+ins=(\d+)\s*$')
INS = re.compile(r'^\s*\d+\s+(\w+)\|([^|]*)\|(.*)$')
OBJ_HDR = re.compile(r'^========== \[A\].*$')


def parse(path):
    u"""返回 {code_name: [ (kind, type, payload), ... ]}"""
    out = {}
    cur = None
    buf = []
    for line in io.open(path, encoding='utf-8'):
        line = line.rstrip(u'\n')
        m = CODE_HDR.match(line)
        if m:
            if cur:
                out[cur] = buf
            cur, buf = m.group(1), []
            continue
        if line.startswith(u'=========='):
            if cur:
                out[cur] = buf
            cur, buf = None, []
            continue
        if cur is not None:
            mi = INS.match(line)
            if mi:
                buf.append((mi.group(1), mi.group(2), mi.group(3)))
    if cur:
        out[cur] = buf
    return out


def val(ins):
    u"""从 payload 里取常量值（`V=...`）"""
    p = ins[2]
    if p.startswith(u'V='):
        try:
            return int(float(p[2:]))
        except ValueError:
            return None
    return None


def varname(ins):
    p = ins[2]
    if p.startswith(u'VAR='):
        return p[4:]
    if p.startswith(u'FN='):
        return u'FN:' + p[3:]
    return None


def rule_of(body):
    u"""从一条代码的指令序列里抽出换房规则列表。

    返回 [ (cond, action, target_or_shift, evidence_index) ]
      cond   : u'room==N' / u'plot>N' / u''（无条件）
      action : u'goto' / u'next' / u'prev' / u'var' / u'event_user'
    """
    rules = []
    # 维护最近若干条 push 的常量，用于回溯
    for k, ins in enumerate(body):
        kind = ins[0]
        if kind != 'Call':
            continue
        fn = varname(ins) or u''
        if not fn.startswith(u'FN:'):
            continue
        fn = fn[3:]

        # ---- 条件：往回找最近的 room/plot/x/y 比较
        cond = u''
        for j in range(k - 1, max(-1, k - 12), -1):
            t = body[j]
            if t[0] == 'Cmp':
                # 比较的左值在更前面
                for m in range(j - 1, max(-1, j - 4), -1):
                    vn = varname(body[m])
                    if vn in (u'room', u'plot', u'x', u'y', u'chapter'):
                        rhs = None
                        for q in range(m + 1, j):
                            cv = val(body[q])
                            if cv is not None:
                                rhs = cv
                        op = u'=='
                        cond = u'%s%s%s' % (vn, op, rhs)
                        break
                if cond:
                    break
            if t[0] in ('Bf', 'Bt', 'B'):
                continue

        if fn == 'room_goto':
            # 目标：往回找最近的常量 push（跳过 Conv）
            tgt = None
            for j in range(k - 1, max(-1, k - 8), -1):
                cv = val(body[j])
                if cv is not None:
                    tgt = cv
                    break
                vn = varname(body[j])
                if vn and vn not in (u'room',):
                    tgt = u'VAR:' + vn
                    break
            rules.append((cond, u'goto', tgt, k))
        elif fn == 'room_goto_next':
            rules.append((cond, u'next', 1, k))
        elif fn == 'room_goto_previous':
            rules.append((cond, u'prev', -1, k))
        elif fn == 'room_next':
            # 计数连续 room_next：由后面累积，这里只记，最后统一折叠
            rules.append((cond, u'room_next', None, k))
        elif fn == 'room_previous':
            rules.append((cond, u'room_prev', None, k))
        elif fn == 'event_user':
            arg = None
            for j in range(k - 1, max(-1, k - 6), -1):
                cv = val(body[j])
                if cv is not None:
                    arg = cv
                    break
            rules.append((cond, u'event_user', arg, k))
    # 折叠 room_next / room_prev 连用：把 n 个 room_next 折成 goto(+n)
    folded = []
    i = 0
    while i < len(rules):
        r = rules[i]
        if r[1] in (u'room_next', u'room_prev'):
            n = 1
            while i + n < len(rules) and rules[i + n][1] == r[1]:
                n += 1
            shift = n if r[1] == u'room_next' else -n
            folded.append((r[0], u'shift', shift, r[3]))
            i += n
            continue
        folded.append(r)
        i += 1
    return folded


def main():
    os.makedirs(EV, exist_ok=True)
    rows = []
    kinds = collections.defaultdict(set)
    for ch in (1, 2, 3, 4, 5):
        p = os.path.join(WORK, 'probe181.ch%d.txt' % ch)
        if not os.path.exists(p):
            print(u'!! 缺 %s' % p)
            continue
        codes = parse(p)
        for cn, body in codes.items():
            m = re.match(r'^gml_Object_(.+?)_(Create_0|Alarm_\d+|Step_0|Other_\d+|Draw_0)$', cn)
            if not m:
                continue
            obj, ev = m.group(1), m.group(2)
            kinds[obj].add(ev)
            if ev not in ('Alarm_2', 'Alarm_3', 'Alarm_4', 'Step_0'):
                continue
            rs = rule_of(body)
            if not rs:
                continue
            for cond, act, tgt, idx in rs:
                rows.append((ch, obj, ev, cond, act, tgt, idx, len(body)))

    # 落表
    hdr = [u'章', u'门物件', u'事件', u'条件', u'动作', u'目标', u'指令位', u'事件长度']
    lines = [u'\t'.join(hdr)]
    for r in sorted(rows, key=lambda t: (t[0], t[1], t[2], t[6])):
        lines.append(u'\t'.join(u'' if x is None else str(x) for x in r))
    io.open(os.path.join(EV, 'door_rules.tsv'), 'w', encoding='utf-8', newline='\r\n').write(
        u'\n'.join(lines) + u'\n')

    print(u'=' * 92)
    print(u'门物件 × 事件（有换房规则的）')
    print(u'=' * 92)
    by_obj = collections.defaultdict(list)
    for r in rows:
        by_obj[r[1]].append(r)
    for obj in sorted(by_obj, key=lambda o: -len(by_obj[o])):
        rs = by_obj[obj]
        evs = sorted(set(x[2] for x in rs))
        chs = sorted(set(x[0] for x in rs))
        print(u'%-46s 规则 %3d 条  事件=%-20s 章=%s'
              % (obj, len(rs), ','.join(evs), ','.join('ch%d' % c for c in chs)))
    print(u'')
    print(u'产出：_evidence/door_rules.tsv（%d 行）' % len(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
