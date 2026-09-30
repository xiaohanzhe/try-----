# -*- coding: utf-8 -*-
"""第72轮 · 跨世界机制（第一批）：给 96 位 NPC 落"穿行域"。

用户口径（逐字）
----------------
「因为各个世界观里有重复的角色，我要求他们能够共存，而且，niko可自由穿行所有世界，
  其余ut及其同人的任务只能在非暗世界穿梭」
「对了做好不同世界的角色在不同世界的兼容性哦」

本轮只动**两件事**（其余"同名相认 / 无身份标识 / 对场景有反应 / 循序渐熟"登记在
`_crossworld.json` 并如实标 `spec_only`）：

  ① 跨作品 61 位的 `home_world`：`'dark'` → **`'foreign'`**
     —— 理由：`light/dark` 是 **Deltarune 语汇**（暗之泉那一侧）。UT 的地下世界、
        OneShot 的城市都不是"暗世界"；第66轮写 `dark` 是**借用**（当时世界模型只有两分），
        第72轮世界模型补了第三档 ⇒ 语义归位。
     ⚠️ 这不改变任何运行时行为：拦人的是 `escape_via_bubble`，不是 `home_world`
        （实证见第71轮 `_link.json` 与 `npc_system.world_gate` 的 docstring 第 4 条）。
  ② 给**全 96 条**加 `roam_scope`（显式，不靠兜底）：
     · `os_niko`                              → `'all'`       （「可自由穿行所有世界」）
     · 其余跨作品 60 位                        → `'non_dark'`  （「只能在非暗世界穿梭」）
     · Deltarune 侧 35 位                      → `'home'`      （第49/50轮原口径，零回归）

用法
----
    C:\\Python311\\python.exe build72.py            # dry（打印统计与抽样）
    C:\\Python311\\python.exe build72.py --write
"""
from __future__ import print_function

import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
AUD = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
REG = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_registry.json')

#: 跨作品作品的 id 前缀（= 该 NPC 属于"本作之外的世界"）
XWORK = ('ut', 'hy', 'ot', 'os')

#: 全域通行名单（只有他一个）—— 用户原话点名："niko可自由穿行所有世界"
ALL_ROAM_IDS = ('os_niko',)

SRC_OLD = u'；两作品 `home_world` 一律显式 `dark`（本项目世界模型只有两分），'
SRC_NEW = (u'。★ 第72轮：**世界模型补了第三档 `foreign`（本作之外的世界）** —— '
           u'原先把跨作品角色的 `home_world` 记成 `dark` 是**借用 Deltarune 的二分**'
           u'（暗之泉那一侧），语义上站不住：UT 的地下世界、OneShot 的城市都不是'
           u'"暗世界"。现已改为 `foreign`（来处由 `chapters` 的作品名承载），'
           u'并给**全 96 条**显式加 `roam_scope`（穿行域）：`os_niko=all`'
           u'（用户口径「niko可自由穿行所有世界」）、其余 60 位跨作品 `=non_dark`'
           u'（「其余ut及其同人的任务只能在非暗世界穿梭」）、Deltarune 侧 35 位 '
           u'`=home`（= 第49/50轮原口径，零回归）。契约与理由见 '
           u'`assets/npc/_crossworld.json`；门控实现见 `modules/npc_system.py` 的 '
           u'`RoamScope` 与 `world_gate` 暗世界分支。')


def scope_of(nid, work):
    if nid in ALL_ROAM_IDS:
        return 'all'
    if work in XWORK:
        return 'non_dark'
    return 'home'


def main():
    write = '--write' in sys.argv
    with io.open(REG, encoding='utf-8') as fh:
        reg = json.load(fh)

    stats = collections.Counter()
    changed_hw = []
    new_npcs = []
    for n in reg['npcs']:
        nid = n['id']
        work = nid.split('_')[0]
        scope = scope_of(nid, work)
        src_hw = n.get('home_world')
        foreign = work in XWORK
        # 重建（保序）：`roam_scope` 插在 `persona` 之后（没有就末尾），保持原字段序
        out = {}
        for k, v in n.items():
            if k == 'home_world':
                out[k] = 'foreign' if foreign else v
            else:
                out[k] = v
            if k == 'persona':
                out['roam_scope'] = scope
        if 'roam_scope' not in out:
            out['roam_scope'] = scope
        if foreign and src_hw != 'foreign':
            changed_hw.append(nid)
        stats[scope] += 1
        stats['foreign' if foreign else 'delta'] += 1
        new_npcs.append(out)
    reg['npcs'] = new_npcs

    # source 那句话必须同步（过期文档 = 项目最忌讳的那类坑）
    src = reg.get('source', '')
    if SRC_OLD in src:
        reg['source'] = src.replace(SRC_OLD, SRC_NEW)
        stats['source_updated'] += 1
    else:
        print('!! source 里找不到待替换的旧句，未改动（请人工核对）')

    print('== 第72轮 穿行域 ==')
    print('  总条数 = %d' % len(new_npcs))
    print('  scope 分布 = %s' % json.dumps(
        dict((k, stats[k]) for k in ('home', 'non_dark', 'all')), ensure_ascii=False))
    print('  home_world dark→foreign 改了 %d 条' % len(changed_hw))
    print('  其中 all（全域）= %s' % list(ALL_ROAM_IDS))
    print('  source 同步 = %s' % ('是' if stats['source_updated'] else '否'))
    smp = [n for n in new_npcs if n['id'] in ('os_niko', 'ut_toriel', 'ralsei')]
    for n in smp:
        print('  样本 %-10s home_world=%-8s roam_scope=%s'
              % (n['id'], n['home_world'], n['roam_scope']))
    if not write:
        print('  (dry run —— 加 --write 才落盘)')
        return 0
    with io.open(REG, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(reg, ensure_ascii=False, indent=1))
        fh.write(u'\n')
    print('-> %s (%d bytes)' % (REG, os.path.getsize(REG)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
