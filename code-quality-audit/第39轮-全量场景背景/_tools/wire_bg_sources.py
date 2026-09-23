# -*- coding: utf-8 -*-
"""
第 39 轮 · Stage 1 接线：把"这张场景用哪张原作素材"写进场景 JSON。

为什么用**文本级逐行替换**而不是 `json.load` → `json.dump`：
场景 JSON 是 **CRLF + 1 空格缩进 + 无 BOM + 中文原样**（`_zone.*.json`）/
**CRLF + 4 空格缩进**（87 个锚点单独文件）。全量重序列化会顺带改掉缩进、
键顺序、行尾 —— 产出与"到底改了什么"无关的巨型 diff，把真正的改动埋掉。
逐行替换则保证**只有目标行发生变化**，其余字节完全不动。

写入字段（**全部是增量，不改既有键的语义**）：
  · `bg`        —— 相对 `assets/scenes/` 的路径（`bg/<scene_id 点换下划线>.png`）
  · `bg_source` —— 来源档次：`room.bg_layer` / `room.asset_layer`（真）
                  / `area_table` / `chapter_tiles` / `chapter_fallback`（近似）
                  / `none`（无）
  · `bg_asset`  —— **溯源**：原作里那个精灵资源名（`bg_xxx`）。没有它就只能靠
                  文件名猜，而文件名是我们自己起的。

同时修正 87 个锚点里**已过期**的 `_comment.why_bg_is_a_placeholder`
（它写"文件尚不存在"，而第 37 轮早已把文件生成了 —— 这是一句会误导后来人的假话）。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bg_common as C   # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(REPO, 'code-quality-audit', '第39轮-全量场景背景', '_evidence')

STALE_COMMENT = '第36轮写这个字段时背景文件确实还不存在（用户当时选 B 自行导出）。第37轮已按原作素材反编译生成并落盘到 bg/，第39轮起 bg_source 标注来源档次、bg_asset 标注原作用的是哪个精灵资源。'

L = []


def w(s=''):
    print(s)
    L.append(s)


def read_text(path):
    """按**原样字节 → str** 读（不做换行翻译，保住 CRLF）。"""
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write_text(path, text):
    """按文本写回，`newline=''` 禁止翻译 —— 文件里是什么换行就还是什么。"""
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def split_keepends(text):
    """切成"行 + 行尾"，兼容 CRLF / LF。"""
    return re.findall(r'[^\r\n]*(?:\r\n|\r|\n|$)', text)[:-1] or []


# ---------------------------------------------------------------------------
#  目标表
# ---------------------------------------------------------------------------

def build_targets():
    """→ `{scene_id: (bg_path, bg_source, bg_asset)}`，覆盖**全部 87 锚点 + 157 真背景**。

    锚点的 `how` 取第 37 轮**实际产出的映射表**（它才是那 87 张图的真实来源），
    而不是第 39 轮重算的结果 —— 重算只在真/近似分界上一致，细节可能不同步。
    """
    man = json.load(io.open(os.path.join(EV, '真背景导出清单.json'), encoding='utf-8'))
    old = C.load_round37_mapping(REPO)
    targets = {}
    # 1) 第 39 轮真背景（含 9 个锚点）
    for r in man['rows']:
        targets[r['scene_id']] = ('bg/' + r['file'], r['how'], r['asset'])
    # 2) 87 个锚点里第 37 轮用近似档填的那些 —— 也补上来源标注
    for sid, row in old.items():
        if sid in targets:
            continue
        targets[sid] = (row.get('file') and ('bg/' + row['file']) or None,
                        row.get('how') or 'none', row.get('asset'))
    return targets, old


# ---------------------------------------------------------------------------
#  区域分片：逐行替换
# ---------------------------------------------------------------------------

ENTRY_RE = re.compile(r'^\s*"([^"]+)":\s*\{\s*$')


def wire_zone(path, targets, stats):
    text = read_text(path)
    lines = split_keepends(text)
    out = []
    cur = None
    skip_src_none = False
    changed = 0
    for ln in lines:
        m = ENTRY_RE.match(ln)
        if m:
            # 进入一个新条目：`  "scene_id": {`
            cur = m.group(1)
            out.append(ln)
            continue
        if cur in targets:
            bg_path, how, asset = targets[cur]
            if re.match(r'^\s*"bg":\s*null\s*,\s*$', ln):
                indent = ln[:len(ln) - len(ln.lstrip())]
                nl = ln[len(ln.rstrip('\r\n')):]
                out.append('%s"bg": %s,%s' % (indent, json.dumps(bg_path, ensure_ascii=False), nl))
                out.append('%s"bg_source": %s,%s'
                           % (indent, json.dumps(how, ensure_ascii=False), nl))
                skip_src_none = True
                changed += 1
                continue
            if skip_src_none and re.match(r'^\s*"bg_source":\s*"none"\s*$', ln):
                indent = ln[:len(ln) - len(ln.lstrip())]
                nl = ln[len(ln.rstrip('\r\n')):]
                out.append('%s"bg_asset": %s%s'
                           % (indent, json.dumps(asset, ensure_ascii=False), nl))
                skip_src_none = False
                continue
        out.append(ln)
    if changed:
        write_text(path, ''.join(out))
    stats['zone_changed'] += changed
    return changed


# ---------------------------------------------------------------------------
#  锚点：逐行插入 / 替换
# ---------------------------------------------------------------------------

def wire_anchor(path, target, stats):
    sid, (bg_path, how, asset) = target
    text = read_text(path)
    lines = split_keepends(text)
    out = []
    done_bg = done_comment = False
    for ln in lines:
        if not done_bg and re.match(r'^\s*"bg":\s*', ln):
            indent = ln[:len(ln) - len(ln.lstrip())]
            nl = ln[len(ln.rstrip('\r\n')):]
            # 锚点的 bg 已经是对的（第37轮写好了）—— 只补两个来源标注。
            cur_val = ln.strip()[len('"bg":'):].strip().rstrip(',').strip()
            out.append('%s"bg": %s,%s' % (indent, cur_val, nl))
            out.append('%s"bg_source": %s,%s' % (indent, json.dumps(how, ensure_ascii=False), nl))
            out.append('%s"bg_asset": %s,%s' % (indent, json.dumps(asset, ensure_ascii=False), nl))
            done_bg = True
            continue
        if not done_comment and '"why_bg_is_a_placeholder":' in ln:
            indent = ln[:len(ln) - len(ln.lstrip())]
            nl = ln[len(ln.rstrip('\r\n')):]
            out.append('%s"why_bg_is_a_placeholder": %s,%s'
                       % (indent, json.dumps(STALE_COMMENT, ensure_ascii=False), nl))
            done_comment = True
            continue
        out.append(ln)
    if done_bg:
        write_text(path, ''.join(out))
        stats['anchor_wired'] += 1
    else:
        stats['anchor_no_bg_line'].append(sid)
    if done_comment:
        stats['anchor_comment_fixed'] += 1
    return done_bg


def main():
    dry = '--dry' in sys.argv
    targets, old = build_targets()
    stats = dict(zone_changed=0, anchor_wired=0, anchor_comment_fixed=0,
                 anchor_no_bg_line=[], zone_files=[])

    w('第 39 轮 · 场景背景字段接线  %s   %s'
      % (__import__('time').strftime('%Y-%m-%d %H:%M:%S'), '[DRY]' if dry else ''))
    w('=' * 78)
    w('目标条目 = %d（第39轮真背景 %d + 第37轮锚点补齐 %d）'
      % (len(targets), len(old) and sum(1 for _, v in targets.items() if v[1] in C.REAL_HOWS),
         len(old)))
    w('来源档次分布：%s' % dict((k, sum(1 for v in targets.values() if v[1] == k))
                              for k in sorted(set(v[1] for v in targets.values()))))
    w('')

    # ---- 先干跑校验：每个目标都必须能在对应的 JSON 里找到"落点" ----
    zone_ids = {}
    for sid in sorted(targets):
        p = os.path.join(SCENES, sid + '.json')
        if not os.path.isfile(p):
            ch, area = sid.split('.')[0], sid.split('.')[1]
            zone_ids.setdefault((ch, area), []).append(sid)

    plan = []
    for (ch, area), sids in sorted(zone_ids.items()):
        zo = os.path.join(SCENES, '_zone.%s.%s.json' % (ch, area))
        if not os.path.isfile(zo):
            w('❗ 找不到分片：%s（%d 个场景）' % (zo, len(sids)))
            continue
        txt = read_text(zo)
        miss = [s for s in sids if ('"%s": {' % s) not in txt]
        plan.append((zo, len(sids), miss))
    w('区域分片接线计划：')
    for zo, n, miss in plan:
        w('   %-46s %3d 个目标  %s'
          % (os.path.basename(zo), n, ('❗缺落点 %s' % miss if miss else 'OK')))
    w('')

    if not dry:
        for sid in sorted(targets):
            p = os.path.join(SCENES, sid + '.json')
            if os.path.isfile(p):
                wire_anchor(p, (sid, targets[sid]), stats)
        for zo, _n, _miss in plan:
            c = wire_zone(zo, targets, stats)
            stats['zone_files'].append((os.path.basename(zo), c))

    w('锚点：已接线 %d ｜ _comment 已修正 %d ｜ 无 bg 行的 %s'
      % (stats['anchor_wired'], stats['anchor_comment_fixed'],
         stats['anchor_no_bg_line'] or '无'))
    w('分片：改写条目 %d 个，涉及 %d 个分片文件'
      % (stats['zone_changed'], len(stats['zone_files'])))

    # ---- 落盘后复核 ----
    if not dry:
        w('')
        w('复核（重新读盘，不信内存）：')
        ok, bad = 0, []
        for sid, (bg, how, asset) in sorted(targets.items()):
            p = os.path.join(SCENES, sid + '.json')
            entry = None
            if os.path.isfile(p):
                entry = json.load(io.open(p, encoding='utf-8'))
            else:
                ch, area = sid.split('.')[0], sid.split('.')[1]
                zo = os.path.join(SCENES, '_zone.%s.%s.json' % (ch, area))
                entry = (json.load(io.open(zo, encoding='utf-8'))['scenes'] or {}).get(sid)
            if not entry:
                bad.append((sid, '条目丢失'))
                continue
            if entry.get('bg') != bg or entry.get('bg_source') != how \
                    or entry.get('bg_asset') != asset:
                bad.append((sid, 'got bg=%r src=%r asset=%r'
                            % (entry.get('bg'), entry.get('bg_source'), entry.get('bg_asset'))))
                continue
            ok += 1
        w('   字段一致 %d / %d' % (ok, len(targets)))
        for sid, why in bad[:10]:
            w('   ❗ %s  %s' % (sid, why))

    os.makedirs(EV, exist_ok=True)
    with io.open(os.path.join(EV, '背景字段接线清单.txt'), 'w', encoding='utf-8',
                 newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    with io.open(os.path.join(EV, '背景字段接线清单.json'), 'w', encoding='utf-8',
                 newline='\n') as f:
        json.dump(dict(generated_at=__import__('time').strftime('%Y-%m-%d %H:%M:%S'),
                       targets=dict((k, list(v)) for k, v in targets.items()),
                       stats=dict((k, v) for k, v in stats.items()
                                  if k != 'anchor_no_bg_line')),
                  f, ensure_ascii=False, indent=2)
    print('\n清单 -> _evidence/背景字段接线清单.txt')


if __name__ == '__main__':
    main()
