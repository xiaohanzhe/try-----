# -*- coding: utf-8 -*-
u"""对 topo_build65.py 打三处补丁（都源自实测暴露的真问题）。

P1 marker 不是门：obj_marker* 是"落点"，当作边源会产出 587 条 no-rule 噪声
               ⇒ 单独收集为 marks[房][字母] = [(x,y)]，用于给边补 landing。
P2 doorA 的 uncond 是"例外分支"（else if (global.flag[7]==1) → room_castle_trueexit）
   若对所有含 doorA 的房间都加这条边，会凭空造出 ~139 条假边
               ⇒ 对象已有 struct 规则或有 SPECIAL 例外时，不再采用其 uncond。
P3 落点回填：目标房若有同字母 obj_marker，则写入 landing + landing_ok。
"""
import io, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'topo_build65.py')
s = io.open(P, encoding='utf-8').read()
orig = s

# ---- P1a: 在 per_by_obj 计算后插入 marker 收集 ----
A1 = "    struct = {}\n    for o, files in per_by_obj.items():"
N1 = ('''    # --- P1 落点（obj_marker*）不是门：单独收集 ---
    marks = {}
    for r in inst:
        for d in r.get('doors', []):
            o = d['obj']
            if not o.startswith('obj_marker'):
                continue
            let = o[len('obj_marker'):]
            marks.setdefault(r['index'], {}).setdefault(let, []).append([d['x'], d['y']])
    markers_total = sum(len(v) for v in marks.values())

    struct = {}
    for o, files in per_by_obj.items():''')
assert A1 in s, 'P1a 锚点缺失'
s = s.replace(A1, N1, 1)

# ---- P1b: 边循环里跳过 marker ----
A2 = "        for d in r.get('doors', []):\n            o = d['obj']\n            ccm = parse_cc(d.get('cc'))"
N2 = ("        for d in r.get('doors', []):\n            o = d['obj']\n"
      "            if o.startswith('obj_marker'):\n                continue  # P1\n"
      "            ccm = parse_cc(d.get('cc'))")
assert A2 in s, 'P1b 锚点缺失'
s = s.replace(A2, N2, 1)

# ---- P2: uncond 门控 ----
A3 = ("            canon = STRUCT_ALIAS.get(o, o)\n"
      "            off = struct_ok.get(canon, STRUCT_RULES.get(canon))\n"
      "            made = False\n")
N3 = ("            canon = STRUCT_ALIAS.get(o, o)\n"
      "            off = struct_ok.get(canon, STRUCT_RULES.get(canon))\n"
      "            # P2：对象若已有 struct 规则或 SPECIAL 例外，其 uncond 属'例外分支'，不得全局套用\n"
      "            skip_uncond = (off is not None) or ((rn, canon) in SPECIAL)\n"
      "            made = False\n")
assert A3 in s, 'P2a 锚点缺失'
s = s.replace(A3, N3, 1)
A3b = "                if v['uncond'] and rn not in v['cond']:"
N3b = "                if v['uncond'] and rn not in v['cond'] and not skip_uncond:"
assert A3b in s, 'P2b 锚点缺失'
s = s.replace(A3b, N3b, 1)

# ---- P3: 落点回填（在边去重前） ----
A4 = "    # 按 (from,to,via) 去重（同一房间里多个同类门可能指向同一目标）"
N4 = ('''    # --- P3 落点回填：目标房若有同字母 obj_marker，补 landing ---
    for e in edges:
        if e['to'] is None or e.get('landing'):
            continue
        via = e['via']
        let = via[len('obj_door'):] if via.startswith('obj_door') else None
        if not let:
            continue
        lm = marks.get(e['to'], {}).get(let)
        if lm:
            e['landing'] = lm[0]
            e['landing_ok'] = True

    # 按 (from,to,via) 去重（同一房间里多个同类门可能指向同一目标）''')
assert A4 in s, 'P3 锚点缺失'
s = s.replace(A4, N4, 1)

# ---- 统计里加 markers ----
A5 = "            'instances_raw': n_raw, 'instances_dedup': n_ded, 'instances_by_src': dict(srcs),"
N5 = ("            'instances_raw': n_raw, 'instances_dedup': n_ded, 'instances_by_src': dict(srcs),\n"
      "            'markers': markers_total, 'landing_ok': sum(1 for e in edges if e.get('landing_ok')),")
assert A5 in s, 'P5 锚点缺失'
s = s.replace(A5, N5, 1)

assert s != orig
io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('补丁已应用，%d -> %d 字节' % (len(orig.encode('utf-8')), len(s.encode('utf-8'))))
