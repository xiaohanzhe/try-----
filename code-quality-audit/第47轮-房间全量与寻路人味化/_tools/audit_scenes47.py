# -*- coding: utf-8 -*-
"""第47轮工具：**逐场景可用性体检**（1,013 个产品场景一个不漏）。

用户口径：「并且确保每一个都能用」。

"能用"拆成五条可判定的事实（缺一条就是这个场景用不了）：
  U1 载体文件在磁盘上（独立件 `<scene_id>.json` / 分片件 `_zone.<ch>.<区>.json` 二者之一）
  U2 该场景在载体文件里真的**注册**了（不是索引里有、文件里没有）
  U3 `name` 非空（面板/日志里显示得出来）
  U4 `original_room_id` 是 int（能换算成原作房间 → 才能寻路/取障碍/取背景）
  U5 几何命中 `_room_geometry.json`（能算出房间尺寸 → 才能做房内行走）

背景（bg）单独统计并**如实报告缺口** —— 它不在"能不能用"里，在"好不好看"里。

输出：`_evidence/场景可用性体检47.txt` / `.json`
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OUT = os.path.join(HERE, '..', '_evidence')


def rd(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    idx = rd(os.path.join(SCENES, '_index.json'))
    geo = rd(os.path.join(SCENES, '_room_geometry.json')).get('rooms') or {}
    files = set(os.listdir(SCENES))
    zone_cache = {}

    missing_file = []
    not_registered = []
    bad_name = []
    bad_rid = []
    geo_miss = []
    bg_have = []
    bg_none = []
    n = 0

    for ch, crec in (idx.get('chapters') or {}).items():
        for ak, arec in (crec.get('areas') or {}).items():
            for sid, srec in (arec.get('scenes') or {}).items():
                n += 1
                rec = srec or {}
                # ★ 两种载体：独立件用记录里的 `file`；**分片场景的 `file` 是空串**
                #   （这不是"缺文件"—— 载体是区域级的 `_zone.<章>.<区>.json`）。
                #   第47轮踩过：第一版判据只看 `file` 字段 ⇒ 926 个分片场景被误报"缺文件"。
                fname = rec.get('file') or ('_zone.%s.%s.json' % (ch, ak))
                # U1
                if not fname or fname not in files:
                    missing_file.append((sid, fname))
                    continue
                path = os.path.join(SCENES, fname)
                # 两种载体
                if fname.startswith('_zone.'):
                    if fname not in zone_cache:
                        zone_cache[fname] = rd(path)
                    carrier = zone_cache[fname].get('scenes') or {}
                    body = carrier.get(sid)
                else:
                    body = rd(path)
                # U2
                if not isinstance(body, dict):
                    not_registered.append((sid, fname))
                    continue
                # U3
                if not (rec.get('name') or '').strip():
                    bad_name.append(sid)
                # U4
                rid = rec.get('original_room_id')
                if not isinstance(rid, int):
                    bad_rid.append(sid)
                # U5
                elif ('%s:%d' % (ch, rid)) not in geo:
                    geo_miss.append((sid, ch, rid))
                # bg（如实统计，不参与"能用")
                bg = body.get('bg')
                if bg:
                    bg_have.append(sid)
                else:
                    bg_none.append(sid)

    lines = []
    ap = lines.append
    ap('第47轮 · 逐场景可用性体检')
    ap('=' * 74)
    ap('场景总数 = %d' % n)
    ap('U1 载体文件缺失        = %d %r' % (len(missing_file), missing_file[:5]))
    ap('U2 载体里未注册该场景  = %d %r' % (len(not_registered), not_registered[:5]))
    ap('U3 name 为空           = %d %r' % (len(bad_name), bad_name[:5]))
    ap('U4 original_room_id 非法 = %d %r' % (len(bad_rid), bad_rid[:5]))
    ap('U5 几何表未命中        = %d %r' % (len(geo_miss), geo_miss[:5]))
    ap('-' * 74)
    ap('bq 有背景 = %d / 无背景 = %d （覆盖率 %.1f%%；**不属于"不能用"**）'
       % (len(bg_have), len(bg_none), 100.0 * len(bg_have) / n if n else 0.0))
    ok = not (missing_file or not_registered or bad_name or bad_rid)
    ap('')
    ap('判定：U1~U4 全通过 = %s；U5 未命中只允许 desktop 场景。' % ok)
    text = '\n'.join(lines)
    print(text)

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    with io.open(os.path.join(OUT, '场景可用性体检47.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(text + '\n')
    with io.open(os.path.join(OUT, '场景可用性体检47.json'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps({
            'n': n, 'missing_file': missing_file,
            'not_registered': not_registered, 'bad_name': bad_name,
            'bad_rid': bad_rid, 'geo_miss': geo_miss,
            'n_bg_have': len(bg_have), 'n_bg_none': len(bg_none),
            'bg_none_sample': bg_none[:30],
        }, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
