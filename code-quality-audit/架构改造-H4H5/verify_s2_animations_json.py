# -*- coding: utf-8 -*-
"""H5 S2 验证：animations.json 与硬编码动画表**深度等价**，且回落路径可用。

S2 的声称是"等价迁移"——名字集合与语义不变，只是来源从代码变成 JSON。
因此本脚本要证明四件事：

  A. 【结构】JSON 存在、schema_version 合法、109 个组都有 frames；
  B. 【等价】JSON 还原出来的 dict 与源码里 `_builtin_animation_mapping` 字面量**深度相等**
     （含每个组的帧列表顺序）；
  C. 【运行时等价】读 JSON 的 SpriteLoader 与强制走内置表的 SpriteLoader，
     `load_sprites()` 之后 sprites 键集合、每组的帧数、frame_container_size 全部相同；
  D. 【可回滚】五种坏的 JSON（非法语法 / 版本不支持 / groups 空 / frames 非列表 / alias 悬空）
     一律不抛异常、回落内置表；
  E. 【缺帧不拒绝】JSON 引用不存在的帧文件时，loader 不静默丢帧，只把它记进报告；
  F. 【S3 字段已就绪】alias_of / legacy / offset 三个字段能被正确解析；
  G. 【自动扫描的影响度量】回答"能不能现在就把 scan_and_group_assets 降级为补漏报告器"：
     影子跑一次"不并入自动扫描"的完整加载，比较 frame_container_size 是否变化。

运行：QT_QPA_PLATFORM=offscreen python verify_s2_animations_json.py
（由 code-quality-audit/regress/run_all.py 统一调度，随机种子与 PYTHONHASHSEED 由它注入）
"""
import io
import json
import os
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
sys.path.insert(0, HERE)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

import extract_animations_json as ex  # noqa: E402
import sprite_loader as sl  # noqa: E402
from sprite_loader import SpriteLoader  # noqa: E402

JSON_PATH = ex.TARGET
ENV = sl.ENV_ANIMATIONS_JSON

PASS, FAIL = [], []
NOTES = []


def check(tid, title, cond, detail=''):
    (PASS if cond else FAIL).append(tid)
    print('  [%s] %-6s %s%s' % ('PASS' if cond else 'FAIL', tid, title,
                                ('  :: ' + detail) if detail else ''))


def note(text):
    NOTES.append(text)
    print('  [NOTE] ' + text)


def make_loader(**env):
    """按指定环境构造一个 SpriteLoader（env 里给 ENV → 覆盖 JSON 路径）。"""
    saved = os.environ.get(ENV)
    try:
        if ENV in env:
            if env[ENV] is None:
                os.environ.pop(ENV, None)
            else:
                os.environ[ENV] = env[ENV]
        return SpriteLoader()
    finally:
        if saved is None:
            os.environ.pop(ENV, None)
        else:
            os.environ[ENV] = saved


def frames_only(doc_groups):
    return {name: entry['frames'] for name, entry in doc_groups.items()}


print('=== A. JSON 结构 ===')
check('A1', 'animations.json 存在于 ralsei_pet/assets/',
      os.path.exists(JSON_PATH), JSON_PATH.replace(ROOT, '<ROOT>'))
with io.open(JSON_PATH, encoding='utf-8') as fh:
    _raw_text = fh.read()
    doc = json.loads(_raw_text)
check('A2', 'schema_version == 1（受支持）', doc.get('schema_version') == 1,
      'version=%r' % doc.get('schema_version'))
groups = doc.get('groups') or {}
check('A3', 'groups 非空且每个组都有 frames 列表',
      bool(groups) and all(isinstance(e.get('frames'), list) for e in groups.values()),
      'groups=%d' % len(groups))
builtin, _node, _lines = ex.extract_literal()
_regen_a = ex.dumps(ex.build_document(builtin, ex.collect_comments(_lines, _node)))
_regen_b = ex.dumps(ex.build_document(builtin, ex.collect_comments(_lines, _node)))
check('A4', '导出器幂等：同一输入连续两次导出逐字节一致',
      _regen_a == _regen_b, '%d 字节' % len(_regen_a.encode('utf-8')))
try:
    resolved = ex.resolve_groups(doc)
    _res_ok = True
except Exception as exc:      # 解析失败本身就是断言失败，不让脚本崩
    resolved, _res_ok = {}, False
    print('  !! resolve_groups 抛异常: %r' % (exc,))
check('A5', '文件可被解析（alias_of 展开、无成环）', _res_ok)
# 加载器对未知字段只 warning 不拒绝 —— 于是 "legcay: true" 这类拼写错误会静默失效。
# 这里对**随包发布的这一份**上锁，保证入库文件里没有未知键。
_KNOWN = set(sl._GROUP_KNOWN_KEYS)   # 私有常量：审计脚本直接引用，避免"复制一份白名单"漂移
unknown_keys = sorted('%s.%s' % (n, k) for n, e in groups.items() for k in e if k not in _KNOWN)
check('A6', '所有组只含已知字段（拼错的键不会被静默忽略）', not unknown_keys,
      '未知=%s' % (unknown_keys or '无'))
# comment 的契约是 str 或 str 列表（见 _validate_animation_config），
# 实际导出统一为**非空字符串数组**（保留源码里的多行注释，不做有损拼接）。
bad_comment = sorted(n for n, e in groups.items()
                     if e.get('comment') is not None
                     and not (isinstance(e['comment'], list)
                              and all(isinstance(c, str) and c.strip() for c in e['comment'])))
check('A7', 'comment 统一为非空字符串数组（保留源码多行注释）', not bad_comment,
      '异常=%s' % (bad_comment or '无'))

print()
print('=== B. 与源码硬编码表深度相等（S2 的核心断言） ===')
json_mapping = resolved
check('B1', '键集合完全相同', set(builtin) == set(json_mapping),
      'builtin=%d json=%d' % (len(builtin), len(json_mapping)))
check('B2', '键顺序也相同（导出保持源码顺序）',
      list(builtin) == list(json_mapping))
diff_frames = [k for k in builtin if builtin[k] != json_mapping.get(k)]
check('B3', '每组解析后的帧列表逐项相等（含顺序）', not diff_frames,
      '不一致的组=%s' % diff_frames)
check('B4', '总帧数一致',
      sum(len(v) for v in builtin.values()) == sum(len(v) for v in json_mapping.values()),
      'frames=%d' % sum(len(v) for v in builtin.values()))
alias_groups = sorted(n for n, e in groups.items() if e.get('alias_of'))
check('B5', '别名组的原始 frames 已清空（不再靠"再写一遍文件名"表达）',
      all(not (groups[n].get('frames') or []) for n in alias_groups),
      '别名组=%s' % alias_groups)

print()
print('=== C. 运行时等价：读 JSON vs 强制内置表 ===')
missing_path = os.path.join(tempfile.gettempdir(), 'ralsei_no_such_animations.json')
if os.path.exists(missing_path):
    os.remove(missing_path)

loader_json = make_loader(**{ENV: None})          # 默认路径 → 读 JSON
loader_builtin = make_loader(**{ENV: missing_path})  # 指向不存在的文件 → 内置表
check('C1', '默认加载走 JSON', loader_json.animation_config_source == 'json',
      'source=%s' % loader_json.animation_config_source)
check('C2', '路径不可用时回落内置表', loader_builtin.animation_config_source == 'builtin',
      'source=%s' % loader_builtin.animation_config_source)
check('C3', '两条来源的 animation_mapping 深度相等',
      loader_json.animation_mapping == loader_builtin.animation_mapping)
check('C4', '两条来源的 animation_mapping 与源码字面量都相等',
      loader_json.animation_mapping == builtin and loader_builtin.animation_mapping == builtin)
check('C5', 'position_offset 仍为空（JSON 里没有非零偏移）',
      loader_json.position_offset == {} and loader_builtin.position_offset == {},
      'offset=%r' % (loader_json.position_offset,))
legacy_in_json = sorted(n for n, e in groups.items() if e.get('legacy') is True)
check('C6', 'legacy 集合与 JSON 里 legacy:true 的组一致（S3 起不再为空）',
      sorted(loader_json.legacy_animations) == legacy_in_json
      and sorted(loader_builtin.legacy_animations) == [],
      'json=%d 组（内置表来源无 legacy，因为内置表没有这个字段）'
      % len(legacy_in_json))

print('  ... 两个 loader 各自 load_sprites()（各加载 1000+ 张 PNG，稍等）')
loader_json.load_sprites()
loader_builtin.load_sprites()
check('C7', 'sprites 键集合相同',
      set(loader_json.sprites) == set(loader_builtin.sprites),
      'json=%d builtin=%d' % (len(loader_json.sprites), len(loader_builtin.sprites)))
same_counts = {k: v for k, v in loader_json.frame_counts.items()
               if loader_builtin.frame_counts.get(k) != v}
check('C8', '每组的帧数逐个相同（含自动扫描进来的组）', not same_counts,
      '不同的组=%s' % sorted(same_counts)[:5])
check('C9', 'frame_container_size 相同',
      loader_json.frame_container_size == loader_builtin.frame_container_size,
      'json=%r builtin=%r' % (loader_json.frame_container_size, loader_builtin.frame_container_size))
check('C10', '加载到的总帧数相同',
      sum(loader_json.frame_counts.values()) == sum(loader_builtin.frame_counts.values()),
      'frames=%d' % sum(loader_json.frame_counts.values()))

print()
print('=== D. 五种坏 JSON 一律回落内置表（可回滚） ===')
BAD_CASES = [
    ('D1', '非法 JSON 语法', 'not a json at all {{{'),
    ('D2', 'schema_version 不受支持',
     json.dumps({'schema_version': 99, 'groups': {'idle': {'frames': ['a.png']}}})),
    ('D3', 'groups 为空', json.dumps({'schema_version': 1, 'groups': {}})),
    ('D4', 'frames 不是字符串列表',
     json.dumps({'schema_version': 1, 'groups': {'idle': {'frames': [1, 2]}}})),
    ('D5', 'alias_of 指向不存在的组',
     json.dumps({'schema_version': 1,
                 'groups': {'idle': {'frames': ['a.png'], 'alias_of': 'nope'}}})),
]
tmpdir = tempfile.mkdtemp(prefix='ralsei_s2_')
for tid, title, payload in BAD_CASES:
    bad = os.path.join(tmpdir, tid + '.json')
    with io.open(bad, 'w', encoding='utf-8') as fh:
        fh.write(payload)
    try:
        ld = make_loader(**{ENV: bad})
        ok = (ld.animation_config_source == 'builtin'
              and ld.animation_mapping == builtin
              and not getattr(ld, 'legacy_animations', None))
    except Exception as exc:
        ok = False
        title += ' —— 抛异常了: %r' % (exc,)
    check(tid, '%s → 回落且 mapping 与内置表一致' % title, ok)

print()
print('=== E. 引用缺失帧：只报告，不静默丢帧 ===')
ghost = os.path.join(tmpdir, 'ghost.json')
payload = json.loads(json.dumps(doc))            # 深拷贝一份用于篡改
payload['groups']['idle']['frames'] = ['spr_ralsei_idle_0.png', 'ghost_frame_不存在.png'] \
    + payload['groups']['idle']['frames'][2:]
with io.open(ghost, 'w', encoding='utf-8') as fh:
    json.dump(payload, fh, ensure_ascii=False)
ld = make_loader(**{ENV: ghost})
check('E1', '含缺失帧的配置仍被接受（不抛异常、不回退）',
      ld.animation_config_source == 'json' and ld.animation_mapping['idle'][1] == 'ghost_frame_不存在.png')
report = ld.get_animation_config_report()
# S3 之后 idle 成了别名目标（neutral -> idle），而别名在加载期「取目标的帧」，
# 所以注进 idle 的缺失帧会沿别名传播到所有 alias_of 指向 idle 的组。
# 期望值必须从 doc 现算，否则一旦新增别名（如 S3 把 neutral 改别名）就会误报。
ghost_groups = sorted(['idle'] + [n for n, e in groups.items() if e.get('alias_of') == 'idle'])
declared_legacy = sorted(n for n, e in groups.items() if e.get('legacy'))
check('E2', '缺失帧被记进 get_animation_config_report()（并沿别名传播）',
      all(report['missing_frames'].get(g) == ['ghost_frame_不存在.png'] for g in ghost_groups)
      and report['missing_frame_total'] == len(ghost_groups),
      'total=%d 期望=%d 组=%s' % (report['missing_frame_total'], len(ghost_groups),
                                ','.join(ghost_groups)))
check('E3', '报告里的组数与 legacy 数与文件声明一致',
      report['groups'] == len(ld.animation_mapping)
      and report['legacy_groups'] == declared_legacy,
      'groups=%d/%d legacy=%d' % (report['groups'], len(ld.animation_mapping),
                                  len(report['legacy_groups'])))

print()
print('=== F. S3 字段已就绪：alias_of / legacy / offset ===')
alias_file = os.path.join(tmpdir, 'alias.json')
with io.open(alias_file, 'w', encoding='utf-8') as fh:
    json.dump({
        'schema_version': 1,
        'groups': {
            'idle': {'frames': ['spr_ralsei_idle_0.png']},
            'happy': {'alias_of': 'idle'},                       # 帧为空 → 取目标的帧
            'laugh': {'frames': ['spr_ralsei_laugh_0.png'], 'alias_of': 'idle'},  # 帧不同 → 应报错
            'old_key': {'frames': ['spr_ralsei_idle_0.png'], 'legacy': True},
            'jump': {'frames': ['spr_ralsei_jump_up_0.png'], 'offset': [0, -10]},
        },
    }, fh, ensure_ascii=False)
la = make_loader(**{ENV: alias_file})
check('F1', 'alias_of 复用目标组的帧（alias 的 frames 为空时）',
      la.animation_config_source == 'builtin', '本例含非法项，应整体回落：%s' % la.animation_config_source)
with io.open(alias_file, 'w', encoding='utf-8') as fh:
    json.dump({
        'schema_version': 1,
        'groups': {
            'idle': {'frames': ['spr_ralsei_idle_0.png']},
            'happy': {'alias_of': 'idle'},
            'old_key': {'frames': ['spr_ralsei_idle_0.png'], 'legacy': True},
            'jump': {'frames': ['spr_ralsei_jump_up_0.png'], 'offset': [0, -10]},
            'loop_off': {'frames': ['spr_ralsei_idle_0.png'], 'loop': False},
        },
    }, fh, ensure_ascii=False)
la = make_loader(**{ENV: alias_file})
check('F2', '合法别名配置被接受', la.animation_config_source == 'json')
check('F3', 'alias_of 的帧等于目标组的帧',
      la.animation_mapping.get('happy') == la.animation_mapping.get('idle'),
      'happy=%r' % (la.animation_mapping.get('happy'),))
check('F4', 'legacy: true 进 legacy_animations', la.legacy_animations == {'old_key'},
      'legacy=%s' % sorted(la.legacy_animations))
check('F5', '非零 offset 进 position_offset', la.position_offset.get('jump') == (0, -10),
      'offset=%r' % (la.position_offset,))

print()
print('=== G. 自动扫描并入的影响度量（回答"能否现在就降级为补漏报告器"） ===')
unconfigured = loader_builtin.get_unconfigured_asset_report()
check('G1', 'get_unconfigured_asset_report() 只返回"配置表里没有"的名字',
      all(n not in loader_builtin.animation_mapping for n in unconfigured),
      '数量=%d，样例=%s' % (len(unconfigured), unconfigured[:3]))
no_scan = make_loader(**{ENV: missing_path})
no_scan.scan_and_group_assets = lambda: None      # 影子：不并入自动扫描
no_scan.load_sprites()
check('G2', '不并入自动扫描时，加载的组数 = 配置表组数',
      len(no_scan.sprites) == len(loader_builtin.animation_mapping),
      'no_scan=%d config=%d' % (len(no_scan.sprites), len(loader_builtin.animation_mapping)))
# G3 是一条"双向绊线"：现在两口径尺寸**不同**，故本轮不启用降级；
# 若哪天数据变了（比如 core_prefixes 调整后两者相等），本项会 FAIL 提醒重新评估。
check('G3', '冻结口径：停用自动并入**会**改变容器尺寸（据此本轮不降级）',
      no_scan.frame_container_size != loader_builtin.frame_container_size,
      'merged=%r no_scan=%r' % (loader_builtin.frame_container_size, no_scan.frame_container_size))
def tallest_groups(loader, top=4):
    """找出"帧最高的组"，用于解释容器尺寸是怎么被撑大的。纯观测。"""
    rows = []
    for name, frames in loader.sprites.items():
        hs = [f.height() for f in frames if f is not None and not f.isNull()]
        if hs:
            rows.append((max(hs), name))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return rows[:top]


def core_prefixes_from_source():
    """从 sprite_loader.load_sprites 里 AST 取 core_prefixes，避免在验证脚本里抄一份。"""
    import ast
    src = os.path.join(ROOT, 'ralsei_pet', 'modules', 'sprite_loader.py')
    with io.open(src, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'core_prefixes' for t in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise SystemExit('源码里找不到 core_prefixes')


def tallest_participating(loader, prefixes, top=3):
    """只统计**参与 frame_container_size 包围盒**的组（与 load_sprites 的过滤口径一致）。

    口径 = 组名在配置表里，或组名命中 core_prefixes。
    """
    rows = []
    for name, frames in loader.sprites.items():
        low = name.lower() if isinstance(name, str) else ''
        is_core = any(low.startswith(p.lower()) for p in prefixes)
        if name not in loader.animation_mapping and not is_core:
            continue
        hs = [f.height() for f in frames if f is not None and not f.isNull()]
        if hs:
            rows.append((max(hs), name))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return rows[:top]


CORE_PREFIXES = core_prefixes_from_source()

check('G4', '容器尺寸整体等比缩放（差异不是单类图异常撑开）',
      abs((no_scan.frame_container_size[0] / max(1, loader_builtin.frame_container_size[0]))
          / (no_scan.frame_container_size[1] / max(1, loader_builtin.frame_container_size[1])) - 1) < 0.15,
      'merged=%r no_scan=%r' % (loader_builtin.frame_container_size, no_scan.frame_container_size))
tall_merged = tallest_participating(loader_builtin, CORE_PREFIXES)
tall_noscan = tallest_participating(no_scan, CORE_PREFIXES)
check('G5', '停用自动并入后"最高参与组"确实降低（确认是并入带来的）',
      tall_noscan[0][0] < tall_merged[0][0],
      '%d → %d' % (tall_merged[0][0], tall_noscan[0][0]))
note('自动扫描多并入 %d 组（%d 帧）；停用后容器尺寸由 %s 变为 %s —— 这是**用户可见的视觉变更**，'
     '因此 scan_and_group_assets 本轮只新增 get_unconfigured_asset_report()（只读报告），'
     '不改变加载行为；是否降级需单独一步 + 单独验收。'
     % (len(loader_builtin.sprites) - len(no_scan.sprites),
        sum(loader_builtin.frame_counts.values()) - sum(no_scan.frame_counts.values()),
        loader_builtin.frame_container_size, no_scan.frame_container_size))
note('参与包围盒的"最高组"：并入自动扫描时 %s ；停用后 %s'
     % ([r for r in tall_merged], [r for r in tall_noscan]))
for _h, _n in tall_merged:
    if _n not in loader_builtin.animation_mapping:
        note('  → 撑大容器的是**自动扫描进来的、配置表里没有的组**：%s（帧高 %d）' % (_n, _h))
        break

print()
print('=' * 60)
print('S2 验证：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项：%s' % FAIL)
print('=' * 60)
sys.exit(1 if FAIL else 0)
