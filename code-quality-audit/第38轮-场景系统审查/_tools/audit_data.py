# -*- coding: utf-8 -*-
"""第 38 轮：场景系统**只读**数据面审查。

目的（用户本轮要求）：确保已写代码"没错 + 贴合功能要求"。
本脚本只读，不改任何被审文件。

保真纪律（本项目踩过 4 次"探针不保真 = 报假问题"）：
  · 索引一律走**产品函数** `scene_system.load_index()`；
  · 路由一律走**产品函数** `scene_routing.load_routes()`；
  · 只对路由表**原始 JSON** 额外读一次 —— 为的是抓到产品加载器会忽略的字段
    （`load_routes` 只校验 `to`，其余条件字段它不看），这类字段写错
    = "规则永远匹配不上"，属于真正要报的东西。

输出：逐条 PASS/FAIL，落到 _evidence/。
"""
import io
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
MODULES = os.path.join(ROOT, 'ralsei_pet', 'modules')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
sys.path.insert(0, MODULES)

import scene_system as S      # noqa: E402
import scene_routing as R     # noqa: E402

out = []
RESULT = []


def w(s=''):
    out.append(str(s))
    print(s)


def check(name, ok, detail=''):
    RESULT.append((bool(ok), name, detail))
    w('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                   ('  <- ' + str(detail)) if detail else ''))


# ===========================================================================
#  0. 装载
# ===========================================================================
w('=== 第 38 轮 场景系统数据面只读审查 ===')
w('ROOT    = %s' % ROOT)
w('SCENES  = %s' % SCENES)
w('')

idx = S.load_index()
w('--- load_index() ---')
w('  ok=%r schema=%r default_scene=%r error=%r'
  % (idx.get('ok'), idx.get('schema_version'), idx.get('default_scene'),
     idx.get('error')))
scenes = idx.get('scenes') or {}
w('  扁平 scenes 条数 = %d' % len(scenes))
if scenes:
    k0 = sorted(scenes)[0]
    w('  样例 entry[%s] = %r' % (k0, scenes[k0]))

rt = R.load_routes()
w('--- load_routes() ---')
w('  ok=%r schema=%r routes=%d fallback=%r error=%r'
  % (rt.get('ok'), rt.get('schema_version'), len(rt.get('routes') or []),
     rt.get('fallback'), rt.get('error')))
w('')

raw_routes = {}
with io.open(os.path.join(SCENES, '_routes.json'), 'r', encoding='utf-8') as fh:
    raw_routes = json.load(fh)
raw_list = raw_routes.get('routes') or []

# ===========================================================================
#  1. 索引自洽
# ===========================================================================
w('--- 1. 索引自洽 ---')
check('1.1 load_index().ok 为真', idx.get('ok') is True, idx.get('error'))
check('1.2 schema_version == SCENE_SCHEMA_VERSION',
      idx.get('schema_version') == S.SCENE_SCHEMA_VERSION,
      '%r vs %r' % (idx.get('schema_version'), S.SCENE_SCHEMA_VERSION))

n_json = len([f for f in os.listdir(SCENES)
              if f.endswith('.json') and not f.startswith('_')])
check('1.3 非 _ 前缀 JSON 数 == 扁平 scenes 条数',
      n_json == len(scenes), '%d vs %d' % (n_json, len(scenes)))

check('1.4 default_scene 已登记在索引里',
      idx.get('default_scene') in scenes, repr(idx.get('default_scene')))

missing_file = []
for sid, ent in scenes.items():
    fn = (ent or {}).get('file') or (sid + '.json')
    if not os.path.isfile(os.path.join(SCENES, fn)):
        missing_file.append(sid)
check('1.5 索引里每个场景的 file 都真实存在',
      not missing_file, missing_file[:5])

# 反差：磁盘上有场景 JSON 但没登记
unregistered = []
for f in sorted(os.listdir(SCENES)):
    if f.endswith('.json') and not f.startswith('_'):
        sid = f[:-5]
        if sid not in scenes:
            unregistered.append(sid)
check('1.6 磁盘上没有"未登记"的场景 JSON',
      not unregistered, unregistered[:5])
w('')

# ===========================================================================
#  2. 三级命名空间：收集真实存在的 id
# ===========================================================================
w('--- 2. 三级命名空间 ---')
scene_ids = set(scenes.keys())
areas_global = set()
areas_by_chapter = {}
chapters = set()
for sid, ent in scenes.items():
    c = (ent or {}).get('chapter_id')
    a = (ent or {}).get('area_id')
    if c:
        chapters.add(c)
        areas_by_chapter.setdefault(c, set())
        if a:
            areas_by_chapter[c].add(a)
    if a:
        areas_global.add(a)
w('  chapters   = %s' % sorted(chapters))
w('  areas      = %s' % sorted(areas_global))
w('  场景数     = %d' % len(scene_ids))
w('')

# ===========================================================================
#  3. 路由表逐条体检（对着真实 id 集）
# ===========================================================================
w('--- 3. 路由表逐条体检 ---')
bad_to = []
bad_scene = []
bad_area = []
bad_chapter = []
no_cond = []
for i, r in enumerate(raw_list):
    tag = '#%d -> %s' % (i, r.get('to'))
    to = r.get('to')
    if to not in scene_ids:
        bad_to.append(tag)

    ws = r.get('when_scene')
    if ws is not None:
        vals = ws if isinstance(ws, list) else [ws]
        for v in vals:
            if v != '*' and v not in scene_ids:
                bad_scene.append('%s when_scene=%r' % (tag, v))

    wa = r.get('when_area')
    if wa is not None:
        vals = wa if isinstance(wa, list) else [wa]
        for v in vals:
            if v not in areas_global:
                bad_area.append('%s when_area=%r' % (tag, v))

    wc = r.get('when_chapter')
    if wc is not None:
        vals = wc if isinstance(wc, list) else [wc]
        for v in vals:
            if v not in chapters:
                bad_chapter.append('%s when_chapter=%r' % (tag, v))

    cond_keys = [k for k in r if k.startswith('when_')]
    if not cond_keys:
        no_cond.append(tag)

check('3.1 每条规则的 to 都指向已登记场景', not bad_to, bad_to)
check('3.2 每条规则的 when_scene 都指向已登记场景（"*" 除外）',
      not bad_scene, bad_scene)
check('3.3 每条规则的 when_area 都是真实存在的区域 id',
      not bad_area, bad_area)
check('3.4 每条规则的 when_chapter 都是真实存在的章节 id',
      not bad_chapter, bad_chapter)
check('3.5 没有"无条件规则"（只写 to+priority 会匹配一切，极危险）',
      not no_cond, no_cond)

fb = raw_routes.get('_fallback') or {}
check('3.6 _fallback.to 指向已登记场景',
      fb.get('to') in scene_ids, repr(fb.get('to')))

# 关键词规则必须有非空词表
bad_kw = []
for i, r in enumerate(raw_list):
    if 'when_keywords' in r:
        kws = r.get('when_keywords')
        if not isinstance(kws, list) or not [k for k in kws if isinstance(k, str) and k.strip()]:
            bad_kw.append('#%d -> %s' % (i, r.get('to')))
        elif any(k != k.strip().lower() or k == '' for k in kws):
            bad_kw.append('#%d 关键词未小写/含空白: %r' % (i, kws))
check('3.7 when_keywords 均为非空字符串列表且已小写去空白',
      not bad_kw, bad_kw)
w('')

# ===========================================================================
#  4. 规则可达性 —— 「一条规则是否永远轮不到」
# ===========================================================================
w('--- 4. 规则可达性（静态）---')
# 4a: 同一 (when_*) 条件组合下，高优先级规则是否把低优先级规则完全挡死
by_key = {}
for i, r in enumerate(raw_list):
    key = tuple(sorted((k, str(v)) for k, v in r.items() if k.startswith('when_')))
    by_key.setdefault(key, []).append((R._priority_of(r), i))
shadowed = []
for key, lst in by_key.items():
    if len(lst) > 1:
        lst.sort()
        # 同条件同优先级 = 后面的永远轮不到
        p0 = lst[0][0]
        for p, i in lst[1:]:
            if p == p0:
                shadowed.append('同条件同优先级: %r 第 %d 条被第 %d 条挡死'
                                % (key, i, lst[0][1]))
check('4.1 没有"同条件同优先级"的重复规则', not shadowed, shadowed)

# 4b: `when_scene: "*"` 这类兜底必须优先级最大
wild = [(R._priority_of(r), i, r.get('to')) for i, r in enumerate(raw_list)
        if r.get('when_scene') == '*' or set(r) - {'to', 'priority', 'reason'} == set()]
if wild:
    wild.sort()
    min_p = wild[0][0]
    others = [R._priority_of(r) for i, r in enumerate(raw_list)
              if r.get('when_scene') != '*']
    check('4.2 「任意场景」规则的最小 priority 比所有具体规则都大',
          min_p > max(others) if others else True,
          'wild=%s max具体=%s' % (min_p, max(others) if others else None))
w('')

# ===========================================================================
#  5. 场景素材声明 vs 磁盘
# ===========================================================================
w('--- 5. 场景 bg 声明 vs 磁盘 ---')
bg_missing = []
bg_notpng = []
n_bg = 0
n_null = 0
for sid in sorted(scene_ids):
    sc = S.load_scene(sid)
    if sc is None:
        bg_missing.append('%s: load_scene 返回 None' % sid)
        continue
    bg = getattr(sc, 'bg', None)
    if not bg:
        n_null += 1
        continue
    n_bg += 1
    names = bg if isinstance(bg, list) else [bg]
    for nm in names:
        if not isinstance(nm, str):
            continue
        fp = S.resolve_asset_path(nm, 'bg', getattr(sc, 'dir_path', None) or SCENES)
        if not os.path.isfile(fp):
            bg_missing.append('%s -> %s' % (sid, nm))
            continue
        with open(fp, 'rb') as fh:
            if fh.read(8) != b'\x89PNG\r\n\x1a\n':
                bg_notpng.append(sid)
w('  有 bg 的场景 = %d，bg 为 null 的场景 = %d' % (n_bg, n_null))
check('5.1 所有声明的 bg 都指向真实存在的文件', not bg_missing, bg_missing[:5])
check('5.2 所有 bg 都是真 PNG', not bg_notpng, bg_notpng[:5])
check('5.3 只有 desktop 一个场景的 bg 为 null（P0 零行为变化证明件）',
      n_null == 1 and 'desktop' in scenes, 'null 数=%d' % n_null)
w('')

# ===========================================================================
#  6. 控制器接线：产品路径是否真的初始化了场景系统
# ===========================================================================
w('--- 6. 产品路径接线（静态扫描 main.py）---')
main_py = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
with io.open(main_py, 'r', encoding='utf-8') as fh:
    main_src = fh.read()
import re
CALL = re.compile(r'self\.scene\.(\w+)\s*\(')
calls = sorted(set(CALL.findall(main_src)))
w('  main.py 里对 self.scene.<方法>() 的调用点 = %r' % calls)
check('6.1 main.py 已 import SceneController',
      'from modules.scene_controller import SceneController' in main_src)
check("6.2 'scene' 已登记进 _CONTROLLER_ATTRS",
      "'scene'" in re.findall(r'_CONTROLLER_ATTRS\s*=\s*\(([^)]*)\)', main_src)[0])
# 宿主预声明字段 vs 控制器实际读写的字段
declared = set(re.findall(r'self\.(_scene_\w+|_routes_loaded|current_scene|scene_objects)\s*=',
                          main_src))
used = set()
ctl_py = os.path.join(MODULES, 'scene_controller.py')
with io.open(ctl_py, 'r', encoding='utf-8') as fh:
    ctl_src = fh.read()
used |= set(re.findall(r"pet\.(\w+)\s*=", ctl_src))
used |= set(re.findall(r"pet\.__dict__\.get\('(\w+)'\)", ctl_src))
used |= set(re.findall(r"self\.p\.__dict__\.get\('(\w+)'\)", ctl_src))
used |= set(re.findall(r"self\.p\.(\w+)\s*=", ctl_src))
used = {u for u in used if u.startswith('_scene') or u in
        ('_routes_loaded', 'current_scene', 'scene_objects')}
undeclared = sorted(used - declared)
check('6.3 控制器用到的宿主字段全部已在 main.py 预声明',
      not undeclared, undeclared)
w('    控制器用到 = %s' % sorted(used))
w('    main 预声明 = %s' % sorted(declared))
w('')

# ===========================================================================
#  汇总
# ===========================================================================
fails = [r for r in RESULT if not r[0]]
w('=' * 60)
w('合计 %d 项：PASS=%d FAIL=%d' % (len(RESULT), len(RESULT) - len(fails), len(fails)))
for _, name, detail in fails:
    w('  FAIL: %s  %s' % (name, detail))

ev = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')
os.makedirs(ev, exist_ok=True)
p = os.path.join(ev, '数据面只读审查.txt')
with io.open(p, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('written:', p)
raise SystemExit(1 if fails else 0)
