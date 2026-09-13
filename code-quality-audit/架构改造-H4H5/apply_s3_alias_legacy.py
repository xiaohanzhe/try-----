# -*- coding: utf-8 -*-
"""H5 S3 应用器：把别名与 legacy 显式化写进 assets/animations.json。

方案（`架构改造排期方案_H4-H5_2026-09-13.md` §4.2 S3）：
  1. **别名升为显式字段**：帧列表完全相同的组不再"再写一遍文件名"，改为 `alias_of`；
     被别名组的 `frames` 清空（加载器会用目标组的帧补齐）。
  2. **legacy 标注**：静态零引用、且**不在动态拼接可达集合**里的键，标 `legacy: true`。

三条必须守住的红线：
  - 标 legacy **只是打标，绝不删组**（删了就是行为变更，不在 S3 范围）；
  - 动态可达的键（walk_/run_/walk_tea_ 家族）**一律不许标 legacy**，误标会掩盖未来缺失；
  - 别名方向是**显式表**决定的，不靠名字排序猜；自动检测到的重复组若与显式表不符，
    脚本直接失败并要求人工决策（防止以后新增重复组被静默合并）。

用法：
  python apply_s3_alias_legacy.py            # 只分析 + 打印计划（dry-run）
  python apply_s3_alias_legacy.py --apply    # 写回 assets/animations.json
"""
import argparse
import ast
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
TARGET = os.path.join(PKG, 'assets', 'animations.json')

# 别名的**方向**由这张表决定（后者复用前者的帧）。键=别名，值=目标。
ALIAS_MAP = {
    'happy': 'laugh',        # 情绪别名：happy 用的就是 laugh 的两帧
    'neutral': 'idle',       # 中立情绪 = 待机
    'sad': 'cry_start',      # 难过 = 哭之前的那一帧
    'splat_mad': 'fall_mad',  # 生气摔 = fall_mad（main.py 用 "fall_mad" 做存在性判断）
}

# 动态拼接可达的家族（静态扫描看不见，见 animation_name_contract.txt 的 9 种模板）。
# 一律不许标 legacy。宁可少标，也不能把"运行时才会出现的名字"标成历史键。
DYNAMIC_PATTERNS = (
    re.compile(r'^walk(_|$)'),
    re.compile(r'^run(_|$)'),
    re.compile(r'^walk_tea_'),
)

# 配置表以外的东西：这些名字被 load_sprites 的 required_animations / 回退契约依赖，
# 即便当下零引用也不标 legacy（它们是对外承诺，不是历史残留）。
PROTECTED = {
    'idle', 'walk_down', 'walk_left', 'walk_right', 'walk_up',
    'laugh', 'cry', 'sing', 'pose',
}


def iter_py_files(root=PKG):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        for fn in filenames:
            if fn.endswith('.py'):
                yield os.path.join(dirpath, fn)


# 生产代码 = src/ 与 modules/ 的顶层 .py；定义动画表的那个文件自身当然不算"引用"。
PROD_DIRS = (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules'))
SELF_FILES = {'sprite_loader.py'}

# 与 _evidence/animation_name_contract.txt 同一套 API 调用点正则（保持口径可比）
API = re.compile(r'(?<![A-Za-z_])(?:change_animation|play_animation_once|play_animation|'
                 r'current_animation\s*==|animation\s*==|is_own_animation)\s*\(?\s*[\'"]'
                 r'([A-Za-z0-9_]+)[\'"]')


def iter_prod_files():
    for d in PROD_DIRS:
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.py') and fn not in SELF_FILES:
                yield os.path.join(d, fn)


def collect_references(names):
    """返回 (口径A: API 调用点字面量, 口径B: 任何字符串字面量, f-string 模板)。

    两个口径都算，是因为"某个名字被间接传入"这种事静态看不全：
      - 口径 A（API 调用点）与既有 evidence 一致，数量小、精度高；
      - 口径 B（任何字符串字面量出现）是**保守超集**，宁可少标 legacy 也不误标。
    legacy 判定用口径 B —— 误标 legacy 会掩盖未来的真实缺失，代价比多留一个标签大得多。
    """
    api_refs, literal_refs, templates = set(), set(), set()
    for path in iter_prod_files():
        with io.open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
        for m in API.finditer(text):
            api_refs.add(m.group(1))
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literal_refs.add(node.value)
            elif isinstance(node, ast.JoinedStr):
                parts = []
                for v in node.values:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        parts.append(v.value)
                    else:
                        parts.append('\x00')
                joined = ''.join(parts)
                if '\x00' not in joined:
                    literal_refs.add(joined)
                elif joined.count('\x00') >= 1 and len(joined) > 1:
                    templates.add(joined.replace('\x00', '{}'))
    return api_refs, literal_refs & names, templates


def find_duplicate_groups(groups):
    """帧列表完全相同的组。已声明 alias_of 的组（frames 为空）自然被跳过。"""
    by_frames = {}
    for name, entry in groups.items():
        if entry.get('alias_of'):
            continue
        key = tuple(entry.get('frames') or ())
        if len(key) == 0:
            continue
        by_frames.setdefault(key, []).append(name)
    return {k: v for k, v in by_frames.items() if len(v) > 1}


def analyze(doc):
    """分析出别名计划与 legacy 计划。**唯一的规则实现处**（apply 与 verify 共用）。

    返回 dict：aliases / legacy / api_named / literal_named / dynamic / zero_ref /
    protected / name_like / templates
    """
    groups = doc['groups']
    api_refs, literal_refs, templates = collect_references(set(groups))

    # 别名计划：文件已标注（有 alias_of）时只校验方向，不再靠"帧重复"反推 ——
    # 否则标注完 aliases 的 frames 被清空，"重复组"就消失了，本函数会自己判自己不一致。
    dups = find_duplicate_groups(groups)
    declared = {n: e['alias_of'] for n, e in groups.items() if e.get('alias_of')}
    aliases = {}
    if declared:
        for alias, target in sorted(declared.items()):
            if ALIAS_MAP.get(alias) != target:
                raise SystemExit('已标注的别名 %s → %s 与 ALIAS_MAP 不符' % (alias, target))
            if not (groups.get(target, {}).get('frames') or []):
                raise SystemExit('别名目标 %s 的 frames 为空' % target)
        aliases = dict(sorted(declared.items()))
        if aliases != dict(ALIAS_MAP):
            raise SystemExit('已标注的别名集合 %s 与 ALIAS_MAP %s 不一致' % (aliases, ALIAS_MAP))
    else:
        for frames, names in sorted(dups.items(), key=lambda kv: kv[1]):
            if len(names) != 2:
                raise SystemExit('出现 %d 个同名帧组，需人工决定别名方向：%s' % (len(names), names))
            a, b = names
            target = ALIAS_MAP.get(a) or ALIAS_MAP.get(b)
            if target is None:
                raise SystemExit('新出现的重复组 %s 不在 ALIAS_MAP 里，请人工决定别名方向' % names)
            alias = b if target == a else a
            if ALIAS_MAP.get(alias) != target:
                raise SystemExit('ALIAS_MAP 方向与检测结果冲突：%s' % names)
            aliases[alias] = target
        if aliases != dict(ALIAS_MAP):
            raise SystemExit('检测到的别名对 %s 与 ALIAS_MAP %s 不一致，请人工确认后再执行'
                             % (aliases, ALIAS_MAP))

    name_like = []
    for tpl in templates:
        if not re.fullmatch(r'[A-Za-z0-9_{}]*', tpl) or tpl.startswith('{'):
            continue
        if tpl.count('{}') > 2 or '{}' not in tpl:
            continue
        rx = re.compile('^%s$' % re.escape(tpl).replace(r'\{\}', '.*'))
        hits = [n for n in groups if rx.match(n)]
        if hits:
            name_like.append((tpl, sorted(hits)))

    dynamic = {n for n in groups if any(p.match(n) for p in DYNAMIC_PATTERNS)}
    dynamic |= {n for _t, hits in name_like for n in hits}
    protected = PROTECTED | set(aliases.values())
    literal_named = {n for n in groups if n in literal_refs}
    zero_ref = set(groups) - literal_named
    legacy = sorted(n for n in zero_ref if n not in dynamic and n not in protected)

    return {
        'aliases': aliases,
        'legacy': legacy,
        'api_named': {n for n in groups if n in api_refs},
        'literal_named': literal_named,
        'dynamic': dynamic,
        'zero_ref': zero_ref,
        'protected': protected,
        'name_like': name_like,
        'templates': templates,
        'dups': dups,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写回 JSON（默认只分析）')
    args = ap.parse_args()

    with io.open(TARGET, encoding='utf-8') as fh:
        doc = json.load(fh)
    groups = doc['groups']
    plan = analyze(doc)
    detected_pairs = plan['aliases']
    legacy = plan['legacy']

    print('=== 1. 别名（帧列表完全相同的组）===')
    if plan['dups']:
        for frames, names in sorted(plan['dups'].items(), key=lambda kv: kv[1]):
            print('  %s  ← 帧完全相同（%d 帧）' % (names, len(frames)))
    else:
        print('  已无"帧重复但未标注"的组（文件已完成 S3 标注，下面按已有 alias_of 校验）')
    for alias, target in sorted(detected_pairs.items()):
        print('  → %s.alias_of = %s（frames 已清空）' % (alias, target))

    print()
    print('=== 2. legacy（静态零引用 且 非动态可达）===')
    print('  口径A（API 调用点字面量）被引用：%d 个' % len(plan['api_named']))
    print('  口径B（任何字符串字面量出现）被引用：%d 个  ← legacy 判定采用此口径（保守）'
          % len(plan['literal_named']))
    print('  groups=%d  口径B零引用=%d  动态可达=%d  受保护=%d'
          % (len(groups), len(plan['zero_ref']), len(plan['dynamic']), len(plan['protected'])))
    print('  f-string 模板共 %d 种，其中"形状像动画名且命中现有组"的 %d 种：'
          % (len(plan['templates']), len(plan['name_like'])))
    for tpl, hits in plan['name_like']:
        print('    f"%s"  →  %s' % (tpl, hits))
    overlap = sorted(plan['zero_ref'] & plan['dynamic'])
    print('  零引用但**动态可达**（不许标 legacy，共 %d 个）：%s' % (len(overlap), overlap))
    print('  legacy 计划（%d 个）：' % len(legacy))
    for i in range(0, len(legacy), 6):
        print('    ' + ', '.join(legacy[i:i + 6]))
    stale = sorted(plan['zero_ref'] - plan['dynamic'] - plan['protected'] - set(legacy))
    if stale:
        print('  !! 异常：以下零引用键既没标 legacy 也不在保护/动态集合里：%s' % stale)

    print()
    print('=== 3. 结论 ===')
    print('  别名 %d 个，legacy %d 个；legacy 一律**保留组**，只打标。'
          % (len(detected_pairs), len(legacy)))

    if not args.apply:
        print('  （dry-run，未写文件；加 --apply 才会写回）')
        return 0

    for alias, target in detected_pairs.items():
        entry = groups[alias]
        entry['alias_of'] = target
        entry['frames'] = []
    for name in legacy:
        groups[name]['legacy'] = True
    with io.open(TARGET, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(dumps(doc, groups))
    print('  已写回 %s' % TARGET)
    return 0


def dumps(doc, groups):
    """与 extract_animations_json.dumps 同格式（组内键序固定），保证 diff 可读。"""
    lines = ['{', '  "schema_version": %d,' % doc['schema_version'], '  "meta": {']
    meta = doc['meta']
    keys = ['generated_by', 'source', 'note']
    for i, key in enumerate(keys):
        tail = ',' if i < len(keys) - 1 else ''
        lines.append('    %s: %s%s' % (json.dumps(key), json.dumps(meta[key], ensure_ascii=False), tail))
    lines.append('  },')
    lines.append('  "groups": {')
    entries = list(groups.items())
    for idx, (name, entry) in enumerate(entries):
        tail = ',' if idx < len(entries) - 1 else ''
        lines.append('    %s: {' % json.dumps(name, ensure_ascii=False))
        order = [k for k in ('frames', 'comment', 'loop', 'offset', 'alias_of', 'legacy') if k in entry]
        for j, k in enumerate(order):
            comma = ',' if j < len(order) - 1 else ''
            val = entry[k]
            if k == 'frames':
                body = '[%s]' % ', '.join(json.dumps(f) for f in val)
                if len(body) > 160:
                    inner = ',\n'.join('        %s' % json.dumps(f) for f in val)
                    body = '[\n%s\n      ]' % inner
                lines.append('      "frames": %s%s' % (body, comma))
            else:
                lines.append('      %s: %s%s' % (json.dumps(k), json.dumps(val, ensure_ascii=False), comma))
        lines.append('    }%s' % tail)
    lines.append('  }')
    lines.append('}')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    sys.exit(main())
